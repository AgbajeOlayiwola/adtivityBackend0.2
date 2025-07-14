# main.py
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from . import models, schemas, crud
from .database import SessionLocal, engine
from typing import List, Optional

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Adtivity Analytics API",
    description="Unified Web2/Web3 analytics platform",
    version="0.1.0"
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post(
    "/users/", 
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    tags=["Users"]
)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user with either:
    - Traditional email/password (Web2)
    - Wallet authentication (Web3)
    """
    # Check for existing email
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check for existing wallet
    if user.wallet_address and crud.get_user_by_wallet(db, wallet_address=user.wallet_address):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wallet already registered"
        )
    
    return crud.create_user(
        db=db,
        email=user.email,
        hashed_password=user.password,  # In production, hash this first!
        name=user.name,
        country=user.country,
        wallet_address=user.wallet_address,
        wallet_type=user.wallet_type
    )

@app.get(
    "/users/{user_id}", 
    response_model=schemas.User,
    summary="Get user details",
    tags=["Users"]
)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user

@app.post(
    "/metrics/", 
    response_model=schemas.PlatformMetrics,
    status_code=status.HTTP_201_CREATED,
    summary="Record platform metrics",
    tags=["Analytics"]
)
def create_metrics(metrics: schemas.MetricsCreate, db: Session = Depends(get_db)):
    return crud.create_platform_metric(
        db=db,
        total_users=metrics.total_users,
        active_sessions=metrics.active_sessions,
        conversion_rate=metrics.conversion_rate,
        revenue_usd=float(metrics.revenue_usd),
        total_value_locked=float(metrics.total_value_locked),
        active_wallets=metrics.active_wallets,
        transaction_volume_24h=float(metrics.transaction_volume_24h),
        new_contracts=metrics.new_contracts,
        daily_page_views=metrics.daily_page_views,
        sales_count=metrics.sales_count,
        platform=metrics.platform,
        source=metrics.source,
        chain_id=metrics.chain_id,
        contract_address=metrics.contract_address
    )

@app.get(
    "/analytics/", 
    response_model=List[schemas.PlatformMetrics],
    summary="Get analytics data",
    tags=["Analytics"]
)
def get_analytics(
    start_date: datetime,
    end_date: datetime = datetime.utcnow(),
    platform: schemas.PlatformType = schemas.PlatformType.BOTH,
    chain_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    return crud.get_metrics_by_timeframe(
        db=db,
        start=start_date,
        end=end_date,
        platform=platform.value,
        chain_id=chain_id
    )

@app.get(
    "/analytics/growth-rate/",
    response_model=float,
    summary="Calculate growth percentage",
    tags=["Analytics"]
)
def get_growth_rate(
    days: int = 30,
    db: Session = Depends(get_db)
):
    return crud.calculate_growth_rate(db, days=days)

@app.get(
    "/health",
    summary="Service health check",
    tags=["System"]
)
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": app.version
    }