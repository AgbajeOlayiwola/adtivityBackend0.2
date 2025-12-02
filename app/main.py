"""Main FastAPI application entry point."""

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from contextlib import asynccontextmanager
import secrets

from .core.config import settings
from .core.database import init_db, close_db
from .core.security_middleware import security_middleware_handler
from .core.cors_middleware import CustomCORSMiddleware
from .core.startup_tasks import startup_tasks
from .api import (
    auth_router,
    dashboard_router,
    sdk_router,
    analytics_router,
    system_router,
    imports_router,
    twitter_router,
    aggregation_router,
    wallets_router,
    user_engagement_router,
    team_router,
)
from .api.payments import router as payments_router
from .api.wallet_sync import router as wallet_sync_router
# Web3 analytics are now integrated into the main dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    init_db()
    
    # Start background tasks
    async with startup_tasks():
        yield
    
    # Shutdown
    close_db()


# Disable FastAPI's automatic docs endpoints so we can protect them with Basic Auth
app = FastAPI(
    title=settings.APP_NAME,
    description="API for Adtivity - A multi-tenant analytics platform for Web2 and Web3 applications.",
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Basic auth for docs
security = HTTPBasic()

def verify_docs_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic auth credentials for docs access."""
    correct_username = secrets.compare_digest(credentials.username, settings.DOCS_BASIC_USER)
    correct_password = secrets.compare_digest(credentials.password, settings.DOCS_BASIC_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Override default docs endpoints with authentication
@app.get("/docs", include_in_schema=False)
async def get_docs(username: str = Depends(verify_docs_credentials)):
    """Protected docs endpoint."""
    return RedirectResponse(url="/docs/", status_code=307)

@app.get("/docs/", include_in_schema=False)
async def get_docs_page(username: str = Depends(verify_docs_credentials)):
    """Protected docs page."""
    # This will serve the actual docs page after authentication
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Docs")

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_json(username: str = Depends(verify_docs_credentials)):
    """Protected OpenAPI JSON."""
    return app.openapi()

@app.get("/redoc", include_in_schema=False)
async def get_redoc(username: str = Depends(verify_docs_credentials)):
    """Protected ReDoc endpoint."""
    from fastapi.openapi.docs import get_redoc_html
    return get_redoc_html(openapi_url="/openapi.json", title="API Docs")

# Add custom CORS middleware
# SDK endpoints allow all origins, other endpoints are restricted
app.add_middleware(
    CustomCORSMiddleware,
    restricted_origins=[
        "https://adtivity.vercel.app",  # Your Vercel frontend
        "https://adtivity.xyz",         # Your new frontend domain
        "http://localhost:3000",        # Local development
        "http://localhost:3001",        # Local development
        "http://localhost:8080",        # Local development
        "http://localhost:9999",        # Local development
        "http://localhost:3002",        # Local development
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
        "https://adtivity.xyz",
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
app.include_router(wallets_router, prefix="/wallets", tags=["wallets"])
app.include_router(wallet_sync_router, tags=["wallet-sync"])
app.include_router(user_engagement_router)
app.include_router(payments_router, tags=["payments"])
app.include_router(team_router)
# Web3 analytics are now integrated into the main dashboard


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint."""
    return {
        "message": "Welcome to Adtivity API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/system/health"
    }
