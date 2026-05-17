# AI Chat API — FastAPI + Anthropic streaming, Chainlit UI

A minimal FastAPI service that streams chat responses from the Anthropic
Messages API over Server-Sent Events, with a Chainlit chat UI on top.

## Architecture
- **Backend** (`./`) — FastAPI app exposing `POST /chat/stream` (SSE) and `GET /health`.
- **UI** (`./chainlit_ui`) — Chainlit app that talks to the backend over HTTP and streams tokens into the chat view.

Both run as separate containers via `docker compose`.

## Files
- `main.py` — FastAPI application + lifespan hook to close the shared HTTP client
- `routers/chat.py` — `/chat/stream` async SSE endpoint
- `schemas/chat.py` — Pydantic request/response models
- `services/llm.py` — async Anthropic Messages streaming client
- `requirements.txt` — backend dependencies
- `chainlit_ui/app.py` — Chainlit chat UI that consumes `/chat/stream`
- `chainlit_ui/Dockerfile` — UI container image
- `Dockerfile` — backend container image
- `docker-compose.yml` — wires the two services together
- `.env.example` — environment variable template

## Setup

1. Copy the env template and fill in your Anthropic key:
   ```bash
   cp .env.example .env
   # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
   ```

2. Run with Docker:
   ```bash
   docker compose up --build
   ```

3. Open the UI:
   - Chat UI:  http://127.0.0.1:8001
   - Backend:  http://127.0.0.1:8000
   - API docs: http://127.0.0.1:8000/docs

To stop:
```bash
docker compose down
```

## Local development (no Docker)

Backend:
```bash
python3 -m pip install -r requirements.txt
uvicorn main:app --reload
```

UI (in a second terminal):
```bash
python3 -m pip install -r chainlit_ui/requirements.txt
BACKEND_URL=http://127.0.0.1:8000 chainlit run chainlit_ui/app.py --port 8001
```

## Example direct API call
```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-5",
    "system_prompt": "You are a helpful assistant.",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Configuration

Backend (`.env`):
- `ANTHROPIC_API_KEY` (required)
- `ANTHROPIC_DEFAULT_MODEL` (default: `claude-sonnet-4-5`)

UI (set in `docker-compose.yml` or your shell):
- `BACKEND_URL` (default: `http://127.0.0.1:8000`, compose uses `http://backend:8000`)
- `CHAT_MODEL`, `CHAT_SYSTEM_PROMPT`, `CHAT_TEMPERATURE`, `CHAT_MAX_TOKENS`
