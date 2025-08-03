"""
FastAPI application factory and configuration.
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config.logging import setup_logging
from .core.config.settings import get_settings
from .core.database.db import db_manager
from .core.agent import get_assistant
from .routes import chat, health, sessions

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    setup_logging()
    logger.info("🚀 Starting the assistant API...")

    try:
        await db_manager.initialize()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

    # Initialize memory manager and assistant
    try:
        await get_assistant()
        logger.info("✅ Memory-enabled assistant initialized successfully")
        logger.info("🚀 Assistant API is ready to use at http://localhost:4000")
    except Exception as e:
        logger.error(f"❌ Failed to initialize memory-enabled assistant: {e}")
        raise

    yield

    logger.info("🛑 Shutting down the assistant API...")

settings = get_settings()

app = FastAPI(
    title="Assistant API",
    description="A general conversational AI assistant",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])

if settings.DEBUG:
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": "Assistant API",
            "version": "0.1.0",
            "docs": "/docs"
        }
