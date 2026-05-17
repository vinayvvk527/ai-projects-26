"""Async Anthropic streaming client used by the /chat/stream endpoint."""

from __future__ import annotations

import json
import os
from typing import AsyncIterator, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_DEFAULT_MODEL = os.getenv("ANTHROPIC_DEFAULT_MODEL", "claude-sonnet-4-5")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY must be set in the environment (.env).")

# One client per process keeps TCP/TLS connections warm and shaves first-token
# latency on subsequent requests.
_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=180.0, write=30.0, pool=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
                "accept": "text/event-stream",
            },
        )
    return _client


async def aclose() -> None:
    """Called on FastAPI shutdown to release the shared client."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def _split_system_and_messages(
    messages: List[Dict[str, str]],
) -> Tuple[str, List[Dict[str, str]]]:
    """Anthropic Messages API takes `system` as a top-level field and only
    user/assistant entries in `messages`."""
    system_text = ""
    convo: List[Dict[str, str]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            if not system_text:
                system_text = content
            continue
        if role in ("user", "assistant") and content:
            convo.append({"role": role, "content": content})
    return system_text, convo


def _resolve_model(model: Optional[str]) -> str:
    if model and model.lower().startswith("claude"):
        return model
    return ANTHROPIC_DEFAULT_MODEL


async def stream_chat_response(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 1000,
) -> AsyncIterator[str]:
    """Async generator yielding text deltas from Anthropic's streaming API."""
    system_text, convo = _split_system_and_messages(messages)
    if not convo:
        raise RuntimeError("No user/assistant messages to send to Anthropic.")

    payload: Dict = {
        "model": _resolve_model(model),
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
        "messages": convo,
        "stream": True,
    }
    if system_text:
        payload["system"] = system_text

    client = _get_client()
    async with client.stream("POST", ANTHROPIC_API_URL, json=payload) as resp:
        if resp.status_code >= 400:
            body = await resp.aread()
            raise RuntimeError(
                f"Anthropic API error {resp.status_code}: {body.decode(errors='replace')}"
            )

        current_event: Optional[str] = None
        async for raw in resp.aiter_lines():
            line = raw.strip() if raw else raw
            if not line:
                current_event = None
                continue
            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
                continue
            if not line.startswith("data:"):
                continue

            data_str = line[len("data:"):].strip()
            if not data_str:
                continue
            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = current_event or data.get("type")
            if event_type == "content_block_delta":
                delta = data.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        yield text
            elif event_type == "message_stop":
                return
            elif event_type == "error":
                raise RuntimeError(f"Anthropic stream error: {data.get('error') or data}")
