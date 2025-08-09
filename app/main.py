from __future__ import annotations

# --- Pydantic and Python Standard Library Imports ---
from fastapi import FastAPI, Depends, HTTPException, status, APIRouter, Header, Request, Response, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging

# --- Local Imports ---
from . import models, schemas, crud
from .database import SessionLocal, engine
from .config import settings

# --- Database Setup ---
# Create all database tables based on the models.
models.Base.metadata.create_all(bind=engine)

# This is an extra app instance from the original code,
# which can be removed to avoid confusion. The app below is the main one.
# app = FastAPI() 

# Database Dependency
def get_db():
    """
    Generator function that provides a database session for each request.
    Ensures the session is properly closed after the request is completed.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Security and Authentication Configuration ---
# Password hashing context (bcrypt is a very strong way to scramble passwords).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT access token creation helper.
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Creates a new JWT access token with an optional expiration time."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # Use the default expiration time from the settings object.
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    # Use the secret key and algorithm from the settings object.
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

# Security guard dependencies
# HTTPBearer is a standard way to get a token from the Authorization: Bearer header.
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_platform_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> models.PlatformUser:
    """
    Dependency to validate a PlatformUser's JWT and return their user object.
    This is for dashboard users.
    """
    if not credentials or credentials.scheme != "Bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme or missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        # Use the secret key and algorithm from the settings object.
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials: No user ID in token.")
        
        platform_user = crud.get_platform_user_by_id(db, user_id=user_id)
        if platform_user is None or not platform_user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials: Platform User not found or inactive.")
        
        return platform_user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials: Invalid JWT.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_client_company(x_api_key: str = Header(None), db: Session = Depends(get_db)) -> models.ClientCompany:
    """
    Dependency to authenticate a client company via its API key in the 'X-API-Key' header.
    This is used for SDK endpoints.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header missing",
        )
    
    company = crud.get_client_company_by_api_key(db, api_key=x_api_key)
    if not company or not company.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive SDK API Key.",
        )
    return company

# --- FastAPI App and Router Initialization ---
app = FastAPI(
    title="Adtivity API",
    description="API for Adtivity - A multi-tenant analytics platform for Web2 and Web3 applications.",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {"Hello": "World"}


# Initialize APIRouters to group related endpoints
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard Management"])
sdk_router = APIRouter(prefix="/sdk", tags=["SDK Events"])
analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])
system_router = APIRouter(prefix="/system", tags=["System"])


# --- CORS Middleware Configuration ---
# --- FIX: Updated origins to allow any client to call the API.
# This resolves CORS errors while keeping the API secure via API keys and JWTs.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Router Endpoints ---

# AUTH Router: Endpoints for PlatformUser login and registration.
@auth_router.post("/register", response_model=schemas.PlatformUser, status_code=status.HTTP_201_CREATED)
def register_platform_user_endpoint(user_input: schemas.PlatformUserCreate, db: Session = Depends(get_db)):
    """Registers a new platform user for the Adtivity dashboard."""
    existing_user = crud.get_platform_user_by_email(db, email=user_input.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Platform user with this email already exists")
    
    # We now call crud.get_password_hash which is defined in crud.py
    hashed_password = crud.get_password_hash(user_input.password)
    db_user = crud.create_platform_user(
        db=db,
        email=user_input.email,
        hashed_password=hashed_password,
        name=user_input.name,
        phone_number=user_input.phone_number
    )
    # The `client_companies` field is not filled yet, so we return a new object with the correct fields.
    # The schemas.PlatformUser model will handle this properly.
    return db_user

@auth_router.post("/token", response_model=schemas.Token)
def login_for_access_token(user: schemas.PlatformUserLogin, db: Session = Depends(get_db)):
    """Authenticates a PlatformUser and returns a JWT access token."""
    platform_user = crud.authenticate_platform_user(db, user.email, user.password)
    if not platform_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(platform_user.id)}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# DASHBOARD Router: Endpoints for managing client companies and fetching their data.
@dashboard_router.get("/me", response_model=schemas.PlatformUser)
def get_my_profile(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the profile information and all associated client companies for the
    currently authenticated platform user.
    """
    return current_user

@dashboard_router.post("/client-companies/", response_model=schemas.ClientCompanyCreateResponse, status_code=status.HTTP_201_CREATED)
def create_company_for_current_user(
    company_input: schemas.ClientCompanyRegisterInput,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new client company for the authenticated platform user.
    Returns the raw API key which is only shown once.
    """
    existing_company_name = crud.get_client_company_by_name(db, name=company_input.name)
    if existing_company_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Client company with this name already exists")
    
    new_company, raw_api_key = crud.create_client_company_with_api_key(
        db=db,
        name=company_input.name,
        platform_user_id=current_user.id
    )
    
    return schemas.ClientCompanyCreateResponse(
        id=new_company.id,
        name=new_company.name,
        created_at=new_company.created_at,
        is_active=new_company.is_active,
        platform_user_id=new_company.platform_user_id,
        api_key=raw_api_key
    )

@dashboard_router.get("/client-companies/", response_model=List[schemas.ClientCompany])
def get_my_client_companies(
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Retrieves all client companies owned by the authenticated platform user."""
    return crud.get_client_companies_by_platform_user(db, platform_user_id=current_user.id)

@dashboard_router.get("/client-companies/{company_id}/events", response_model=List[schemas.Event])
def get_client_company_events_endpoint(
    company_id: int,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
    event_type: Optional[schemas.SDKEventType] = Query(None, description="Filter events by type, e.g., 'page_visit'"),
):
    """
    Retrieves all standard (Web2) events for a specific client company, accessible only by the owner.
    """
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view events for this company.")
    
    return crud.get_events_for_client_company(
        db,
        client_company_id=company_id,
        event_type=event_type  # Pass the new parameter to the CRUD function
    )

@dashboard_router.get("/client-companies/{company_id}/web3-events", response_model=List[schemas.Web3Event])
def get_client_company_web3_events_endpoint(
    company_id: int,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """
    NEW: Retrieves all Web3 events for a specific client company, accessible only by the owner.
    """
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company or company.platform_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view events for this company.")
    
    return crud.get_web3_events_for_client_company(db, client_company_id=company_id)

@dashboard_router.post(
    "/client-companies/{company_id}/regenerate-api-key",
    response_model=schemas.ClientCompanyRegenerateAPIKeyResponse,
)
def regenerate_api_key_for_company(
    company_id: int,
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db),
):
    """
    Regenerates a new API key for a specific client company.
    The new API key is returned to the user *one time only*.
    """
    # 1. Verify the company exists and belongs to the current user
    company = crud.get_client_company_by_id(db, company_id=company_id)
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client company not found"
        )
    if company.platform_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to regenerate this company's API key",
        )

    # 2. Call the CRUD function to generate a new key and update the database
    new_company, raw_api_key = crud.regenerate_client_company_api_key(db, company)

    # 3. Return the new, plain-text API key to the user (one time only)
    return schemas.ClientCompanyRegenerateAPIKeyResponse(
        id=new_company.id,
        name=new_company.name,
        created_at=new_company.created_at,
        is_active=new_company.is_active,
        platform_user_id=new_company.platform_user_id,
        api_key=raw_api_key, # This is the crucial part: we return the raw key here.
    )

# SDK Router: Endpoints for client SDKs to send data.
@sdk_router.post("/event", status_code=status.HTTP_202_ACCEPTED)
def receive_sdk_event(
    payloads: List[schemas.SDKEventPayload],
    company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
):
    """
    Receives a batch of events from the client-side SDK. The request is authenticated
    via the X-API-Key header. Events are now routed to the correct handler based on content.
    """
    try:
        for payload in payloads:
            # IMPROVED: We now first check if the event type is explicitly 'tx'
            # to robustly identify Web3 events. We also keep the original check for
            # Web3-specific fields for backward compatibility.
            is_web3_event = (payload.type == schemas.SDKEventType.TX) or any([
                payload.wallet_address,
                payload.chain_id,
                payload.properties.get("wallet_address"),
                payload.properties.get("chain_id")
            ])
            
            if is_web3_event:
                # Handle as a Web3 event.
                crud.handle_web3_sdk_event(db, company.id, payload)
            else:
                # Handle as a standard Web2 event.
                crud.handle_sdk_event(db, company.id, payload)
        return {"message": f"{len(payloads)} events received successfully"}
    except Exception as e:
        # Log the full exception for debugging
        logging.error(f"Error processing SDK events: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid event payload in batch")


# ANALYTICS Router: Endpoints for platform analytics data.
@analytics_router.post("/metrics/", response_model=schemas.PlatformMetrics, status_code=status.HTTP_201_CREATED)
def create_metrics_endpoint(
    metrics: schemas.MetricsCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
):
    """Records platform metrics for a specific client company (authenticated by API key)."""
    return crud.create_platform_metric(
        db=db,
        client_company_id=current_company.id,
        **metrics.model_dump()
    )

@analytics_router.get("/metrics/", response_model=List[schemas.PlatformMetrics])
def get_analytics_endpoint(
    start_date: datetime,
    end_date: datetime = datetime.utcnow(),
    platform: schemas.PlatformType = schemas.PlatformType.BOTH,
    chain_id: Optional[str] = None, # UPDATED: Changed chain_id type to str
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Gets analytics data for all companies owned by the authenticated platform user."""
    company_ids = [c.id for c in crud.get_client_companies_by_platform_user(db, current_user.id)]
    if not company_ids:
        return []
    
    return crud.get_metrics_by_timeframe_for_companies(
        db=db,
        company_ids=company_ids,
        start=start_date,
        end=end_date,
        platform=platform.value,
        chain_id=chain_id
    )


# SYSTEM Router: Health check and other system endpoints.
@system_router.get("/health", summary="Service health check")
def health_check():
    """Checks the health and status of the API."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": app.version
    }


# --- Register Routers with the main app ---
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(sdk_router)
app.include_router(analytics_router)
app.include_router(system_router)
