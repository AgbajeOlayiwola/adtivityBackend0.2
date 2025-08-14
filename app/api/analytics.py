"""Analytics endpoints for platform metrics."""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_platform_user, get_current_client_company
from .. import crud, schemas, models

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.post("/metrics/", response_model=schemas.PlatformMetrics, status_code=status.HTTP_201_CREATED)
async def create_metrics(
    metrics: schemas.MetricsCreate,
    current_company: models.ClientCompany = Depends(get_current_client_company),
    db: Session = Depends(get_db)
) -> schemas.PlatformMetrics:
    """Record platform metrics for a specific client company."""
    return crud.create_platform_metric(
        db=db,
        client_company_id=current_company.id,
        **metrics.model_dump()
    )


@router.get("/metrics/", response_model=List[schemas.PlatformMetrics])
async def get_analytics(
    start_date: datetime = Query(..., description="Start date for analytics"),
    end_date: datetime = Query(default_factory=datetime.utcnow, description="End date for analytics"),
    platform: schemas.PlatformType = Query(default=schemas.PlatformType.BOTH, description="Platform type filter"),
    chain_id: Optional[str] = Query(None, description="Blockchain chain ID filter"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> List[schemas.PlatformMetrics]:
    """Get analytics data for all companies owned by the authenticated platform user."""
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