"""Main FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import settings
from .core.database import init_db, close_db
from .core.security_middleware import security_middleware_handler
from .core.cors_middleware import CustomCORSMiddleware
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

# Add security middleware (must be first) - TEMPORARILY DISABLED
# app.middleware("http")(security_middleware_handler)

# Add custom CORS middleware
# SDK endpoints allow all origins, other endpoints are restricted
app.add_middleware(
    CustomCORSMiddleware,
    restricted_origins=[
        "https://adtivity.vercel.app",  # Your Vercel frontend
        "http://localhost:3000",        # Local development
        "http://localhost:3001",        # Local development
        "http://localhost:8080",        # Local development
        "http://localhost:9999",        # Local development
    ],
    sdk_paths=["/sdk/", "/sdk/event", "/sdk/events"]
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
