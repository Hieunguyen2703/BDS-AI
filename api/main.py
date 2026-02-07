"""
FastAPI Main Application.
BDS Agent - Hệ thống tìm kiếm bất động sản tự động.
"""

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger

from api.routes import search, listings, analytics, chat, valuation
from storage.database import init_db, close_db, get_session
from storage.vector_db import VectorDB
from scheduler.jobs import get_scheduler, setup_jobs
from config import settings

# Fix for Windows: Set event loop policy to support subprocess (Playwright)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# Configure logging




class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware để log requests."""

    async def dispatch(self, request: Request, call_next):
        logger.info(
            f"request_started: method={request.method}, url={str(request.url)}, "
            f"client={request.client.host if request.client else 'unknown'}"
        )

        response = await call_next(request)

        logger.info(
            f"request_completed: method={request.method}, url={str(request.url)}, status_code={response.status_code}"
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.
    Khởi tạo và cleanup resources.
    """
    logger.info("🚀 Starting BDS Agent API...")

    # Initialize database
    try:
        await init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.warning("⚠️ Database init skipped (tables may already exist)", error=str(e))

    # Initialize vector database
    try:
        vector_db = VectorDB()
        app.state.vector_db = vector_db
        logger.info("✅ Vector database initialized")
    except Exception as e:
        logger.error(f"⚠️ Vector DB init failed: {e}")
        app.state.vector_db = None

    # Setup scheduler
    try:
        scheduler = get_scheduler()
        setup_jobs()
        scheduler.start()
        app.state.scheduler = scheduler
        logger.info("✅ Scheduler started")
    except Exception as e:
        logger.error("⚠️ Scheduler setup failed (continuing)", error=str(e))
        app.state.scheduler = None

    logger.info("🎉 BDS Agent API ready!")

    yield

    # Cleanup
    logger.info("🛑 Shutting down BDS Agent API...")

    if hasattr(app.state, "scheduler") and app.state.scheduler:
        app.state.scheduler.shutdown(wait=False)
        logger.info("✅ Scheduler stopped")

    await close_db()
    logger.info("✅ Database closed")

    logger.info("👋 Goodbye!")


# Create FastAPI app
app = FastAPI(
    title="BDS Agent API",
    description="""
## Hệ thống tìm kiếm và quản lý tin bất động sản tự động

### Tính năng:
- 🔍 **Tìm kiếm thông minh**: Agent AI tự động tìm kiếm trên nhiều nền tảng
- 📊 **Phân tích thị trường**: Thống kê giá theo quận/huyện
- 🎯 **Semantic Search**: Tìm kiếm ngữ nghĩa với ChromaDB
- 📱 **Real-time Updates**: WebSocket cho updates real-time
- 🔔 **Thông báo**: Telegram notifications cho tin mới

### Tech Stack:
- 🤖 Ollama (qwen2.5:14b) - LLM local
- 🌐 Browser-use - Web automation
- 🗃️ PostgreSQL + ChromaDB - Storage
- ⚡ FastAPI - Backend
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:5173", 
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging middleware
app.add_middleware(LoggingMiddleware)


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        url=str(request.url),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An error occurred",
        },
    )


# Include routers
app.include_router(search.router, prefix="/api/v1")
app.include_router(listings.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(valuation.router, prefix="/api/v1")


# Health check
@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Kiểm tra trạng thái hệ thống.
    """
    health = {
        "status": "healthy",
        "services": {},
    }

    # Check database
    try:
        from sqlalchemy import text
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        health["services"]["database"] = "ok"
    except Exception as e:
        health["services"]["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check vector db
    if hasattr(app.state, "vector_db") and app.state.vector_db:
        try:
            count = app.state.vector_db.collection.count()
            health["services"]["vector_db"] = f"ok ({count} vectors)"
        except Exception as e:
            health["services"]["vector_db"] = f"error: {str(e)}"
    else:
        health["services"]["vector_db"] = "not initialized"

    # Check scheduler
    if hasattr(app.state, "scheduler") and app.state.scheduler:
        try:
            jobs = app.state.scheduler.get_jobs()
            health["services"]["scheduler"] = f"ok ({len(jobs)} jobs)"
        except Exception as e:
            health["services"]["scheduler"] = f"error: {str(e)}"
    else:
        health["services"]["scheduler"] = "not initialized"

    return health


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "BDS Agent API",
        "version": "1.0.0",
        "description": "Hệ thống tìm kiếm bất động sản tự động",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/api/v1/districts")
async def get_districts():
    """
    Lấy danh sách quận/huyện và giá tham khảo.
    """
    from config import DISTRICT_PRICE_RANGES

    districts = []
    for name, (min_price, max_price) in DISTRICT_PRICE_RANGES.items():
        districts.append({
            "name": name,
            "price_range_per_m2": {
                "min": min_price * 1_000_000,
                "max": max_price * 1_000_000,
                "display": f"{min_price}-{max_price} triệu/m²",
            },
        })

    return {"districts": districts}


@app.get("/api/v1/property-types")
async def get_property_types():
    """
    Lấy danh sách loại BĐS.
    """
    from config import PROPERTY_TYPES

    return {"property_types": PROPERTY_TYPES}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
