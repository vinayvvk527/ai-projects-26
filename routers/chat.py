from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from schemas.chat import ChatError, ChatRequest
from services.llm import stream_chat_response

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse(data: str) -> str:
    # SSE spec: payloads with embedded newlines must be emitted as multiple
    # `data:` lines, one per line of content, followed by a blank-line
    # terminator. Naively wrapping the whole chunk in a single `data: ...`
    # loses every line after the first.
    return "".join(f"data: {part}\n" for part in data.split("\n")) + "\n"


@router.post(
    "/stream",
    response_class=StreamingResponse,
    responses={400: {"model": ChatError}},
)
async def stream_chat(request: ChatRequest):
    if not request.messages:
        raise HTTPException(status_code=400, detail="At least one user message is required.")

    messages = [{"role": "system", "content": request.system_prompt}] + [
        m.dict() for m in request.messages
    ]

    async def event_stream():
        try:
            async for chunk in stream_chat_response(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            ):
                yield _sse(chunk)
        except Exception as exc:
            yield _sse(f"[ERROR] {exc}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
