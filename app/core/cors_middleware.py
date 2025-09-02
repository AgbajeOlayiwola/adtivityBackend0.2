"""Custom CORS middleware for handling different origin policies."""

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse


class CustomCORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware that allows all origins for SDK endpoints."""
    
    def __init__(self, app, restricted_origins: list, sdk_paths: list = None):
        super().__init__(app)
        self.restricted_origins = restricted_origins
        self.sdk_paths = sdk_paths or ["/sdk/", "/sdk/event", "/sdk/events"]
    
    async def dispatch(self, request: Request, call_next):
        """Handle CORS based on the endpoint."""
        
        # Check if this is an SDK endpoint
        is_sdk_endpoint = any(request.url.path.startswith(path) for path in self.sdk_paths)
        
        # Check if this is a Swagger/OpenAPI endpoint
        is_swagger_endpoint = any(request.url.path.startswith(path) for path in ["/docs", "/openapi.json", "/redoc"])
        
        # For SDK endpoints, allow all origins
        if is_sdk_endpoint:
            return await self._handle_sdk_cors(request, call_next)
        
        # For Swagger endpoints, allow all origins (for development)
        if is_swagger_endpoint:
            return await self._handle_swagger_cors(request, call_next)
        
        # For other endpoints, use restricted origins
        return await self._handle_restricted_cors(request, call_next)
    
    async def _handle_swagger_cors(self, request: Request, call_next):
        """Handle CORS for Swagger/OpenAPI endpoints - allow all origins."""
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = StarletteResponse()
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Authorization, Content-Language, Content-Type, X-API-Key, X-Requested-With, authorization, content-type, x-api-key"
            response.headers["Access-Control-Max-Age"] = "600"
            return response
        
        # Handle actual requests
        response = await call_next(request)
        
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
    
    async def _handle_sdk_cors(self, request: Request, call_next):
        """Handle CORS for SDK endpoints - allow all origins."""
        origin = request.headers.get("origin")
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = StarletteResponse()
            if origin:
                response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Authorization, Content-Language, Content-Type, X-API-Key, X-Requested-With, authorization, content-type, x-api-key"
            response.headers["Access-Control-Max-Age"] = "600"
            return response
        
        # Handle actual requests
        response = await call_next(request)
        
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
    
    async def _handle_restricted_cors(self, request: Request, call_next):
        """Handle CORS for restricted endpoints."""
        origin = request.headers.get("origin")
        
        # Allow same-origin requests (no origin header or same host)
        if not origin or origin == str(request.base_url).rstrip('/'):
            return await call_next(request)
        
        # Check if origin is allowed
        if origin not in self.restricted_origins:
            return StarletteResponse(
                content="Disallowed CORS origin",
                status_code=400,
                headers={"Content-Type": "text/plain"}
            )
        
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = StarletteResponse()
            if origin and origin in self.restricted_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Accept, Accept-Language, Authorization, Content-Language, Content-Type, X-API-Key, X-Requested-With, authorization, content-type, user-role"
            response.headers["Access-Control-Max-Age"] = "600"
            return response
        
        # Handle actual requests
        response = await call_next(request)
        
        if origin and origin in self.restricted_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        
        return response
