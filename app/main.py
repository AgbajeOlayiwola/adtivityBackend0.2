"""Main FastAPI application entry point."""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    imports_router,
    twitter_router,
    aggregation_router
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
        "http://localhost:3002", 
    ],
    sdk_paths=["/sdk/", "/sdk/event", "/sdk/events"]
)

# Global exception handler to ensure CORS headers are always set
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that ensures CORS headers are set even on errors."""
    origin = request.headers.get("origin")
    
    # Create error response
    if isinstance(exc, HTTPException):
        response = JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    else:
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )
    
    # Set CORS headers
    if origin and origin in [
        "https://adtivity.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001", 
        "http://localhost:8080",
        "http://localhost:9999",
        "http://localhost:3002"
    ]:
        response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Credentials"] = "true"
    
    return response

# Include API routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(sdk_router)
app.include_router(analytics_router)
app.include_router(system_router)
app.include_router(imports_router)
app.include_router(twitter_router)
app.include_router(aggregation_router)


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Welcome to Adtivity API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/system/health"
    }
