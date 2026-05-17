"""Chainlit UI for the AI Chat API.

Streams the FastAPI backend's /chat/stream SSE response into the Chainlit
message view, preserving per-session conversation history.
"""

from __future__ import annotations

import os
from typing import List, Optional

import chainlit as cl
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-4-5")
SYSTEM_PROMPT = os.getenv("CHAT_SYSTEM_PROMPT", "You are a helpful assistant.")
TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("CHAT_MAX_TOKENS", "1000"))

# One shared HTTP client across messages keeps the TCP connection to the
# backend warm — noticeably snappier first token on each new message.
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=BACKEND_URL,
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            headers={"Accept": "text/event-stream"},
        )
    return _client


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set("history", [])


@cl.set_starters
async def starters():
    return [
        cl.Starter(
            label="Explain a concept",
            message="Explain how Server-Sent Events work in one short paragraph.",
        ),
        cl.Starter(
            label="Write code",
            message="Write a Python function that reverses words in a sentence.",
        ),
        cl.Starter(
            label="Brainstorm",
            message="Give me five small project ideas for learning FastAPI.",
        ),
    ]


@cl.on_message
async def on_message(message: cl.Message) -> None:
    history: List[dict] = cl.user_session.get("history") or []
    history.append({"role": "user", "content": message.content})

    payload = {
        "model": CHAT_MODEL,
        "system_prompt": SYSTEM_PROMPT,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "messages": history,
    }

    reply = cl.Message(content="")
    await reply.send()

    assistant_text_parts: List[str] = []
    client = _get_client()

    try:
        async with client.stream("POST", "/chat/stream", json=payload) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise RuntimeError(
                    f"Backend returned {resp.status_code}: {body.decode(errors='replace')}"
                )

            # Buffer all `data:` lines belonging to a single SSE event, then
            # join them with \n on the blank-line terminator. Required by the
            # SSE spec so payloads containing newlines (code blocks, etc.)
            # round-trip intact.
            event_lines: List[str] = []

            async def flush() -> None:
                """Emit the buffered SSE event to the Chainlit message."""
                if not event_lines:
                    return
                chunk = "\n".join(event_lines)
                event_lines.clear()
                if not chunk:
                    return
                if chunk.startswith("[ERROR]"):
                    raise RuntimeError(chunk[len("[ERROR]"):].strip())
                await reply.stream_token(chunk)
                assistant_text_parts.append(chunk)

            async for line in resp.aiter_lines():
                if line == "":
                    await flush()
                    continue
                if not line.startswith("data:"):
                    continue
                # Per SSE spec strip exactly one leading space — preserves
                # meaningful spaces in token deltas like " world".
                value = line[len("data:"):]
                if value.startswith(" "):
                    value = value[1:]
                event_lines.append(value)
            # End-of-stream: flush any trailing buffered event.
            await flush()
    except Exception as exc:
        reply.content = (reply.content or "") + f"\n\n_error: {exc}_"
        await reply.update()
        # Don't keep the bad turn in history.
        history.pop()
        cl.user_session.set("history", history)
        return

    await reply.update()
    history.append({"role": "assistant", "content": "".join(assistant_text_parts)})
    cl.user_session.set("history", history)
