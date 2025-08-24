"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .core.database import init_db, close_db
from .api import (
    auth_router,
    dashboard_router,
    sdk_router,
    analytics_router,
    system_router,
    imports_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    init_db()
    yield
    # Shutdown
    close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="API for Adtivity - A multi-tenant analytics platform for Web2 and Web3 applications.",
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(sdk_router)
app.include_router(analytics_router)
app.include_router(system_router)
app.include_router(imports_router)


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Welcome to Adtivity API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/system/health"
    }
