from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from routers.chat import router as chat_router
from services.llm import aclose as close_llm_client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_llm_client()


app = FastAPI(
    title="AI Chat API",
    description="FastAPI service that streams Anthropic chat responses via SSE.",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(chat_router)


@app.get("/health", tags=["meta"])
async def health_check():
    return {"status": "ok", "project": "AI Chat API"}
