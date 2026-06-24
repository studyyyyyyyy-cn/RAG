"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.models.database import init_db
from app.api.v1 import knowledge, document, chat, agent, shortcut, llm_provider
from app.mcp.server import router as mcp_router
from app.utils.webpage_publisher import ensure_published_pages_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if not settings.DEBUG else ["*"],
    allow_credentials=True if not settings.DEBUG else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge.router, prefix=settings.API_PREFIX, tags=["Knowledge Base"])
app.include_router(document.router, prefix=settings.API_PREFIX, tags=["Documents"])
app.include_router(chat.router, prefix=settings.API_PREFIX, tags=["Chat"])
app.include_router(agent.router, prefix=settings.API_PREFIX, tags=["Agents"])
app.include_router(shortcut.router, prefix=settings.API_PREFIX, tags=["Shortcuts"])
app.include_router(llm_provider.router, prefix=settings.API_PREFIX, tags=["LLM Providers"])
app.include_router(mcp_router, prefix="/mcp", tags=["MCP"])
app.mount("/published-pages", StaticFiles(directory=str(ensure_published_pages_dir())), name="published-pages")


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
