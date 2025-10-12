"""API endpoints for wallet activity syncing."""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from uuid import UUID

from ..core.database import get_db
from ..core.security import get_current_platform_user
from ..core.wallet_sync_service import wallet_sync_service
from ..core.wallet_activity_fetcher import wallet_activity_fetcher
from ..models import PlatformUser
from ..crud import get_client_company_by_id

router = APIRouter(prefix="/wallets/sync", tags=["wallet-sync"])


@router.post("/start")
async def start_wallet_sync(
    background_tasks: BackgroundTasks,
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Start automatic wallet activity syncing."""
    try:
        if wallet_sync_service.is_running:
            return {
                "success": True,
                "message": "Wallet sync is already running",
                "status": "running"
            }
        
        # Start sync service in background
        background_tasks.add_task(wallet_sync_service.start_auto_sync)
        
        return {
            "success": True,
            "message": "Wallet sync service started",
            "status": "started"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error starting wallet sync: {str(e)}"
        )


@router.post("/stop")
async def stop_wallet_sync(
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Stop automatic wallet activity syncing."""
    try:
        wallet_sync_service.stop_auto_sync()
        
        return {
            "success": True,
            "message": "Wallet sync service stopped",
            "status": "stopped"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error stopping wallet sync: {str(e)}"
        )


@router.get("/status")
async def get_sync_status(
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get wallet sync service status."""
    try:
        status = await wallet_sync_service.get_sync_status()
        
        return {
            "success": True,
            "status": status
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting sync status: {str(e)}"
        )


@router.post("/wallet/{wallet_id}")
async def sync_wallet_activities(
    wallet_id: UUID,
    days_back: int = 30,
    force_refresh: bool = False,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Sync activities for a specific wallet."""
    try:
        # Verify user has access to this wallet
        from ..crud.wallets import wallet_crud
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Check if user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Fetch wallet activities
        result = await wallet_activity_fetcher.fetch_wallet_activities(
            str(wallet_id),
            days_back=days_back,
            force_refresh=force_refresh
        )
        
        return {
            "success": result['success'],
            "message": result.get('message', ''),
            "transactions_fetched": result.get('transactions_fetched', 0),
            "transactions_stored": result.get('transactions_stored', 0),
            "wallet_address": result.get('wallet_address', ''),
            "network": result.get('network', ''),
            "error": result.get('error')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing wallet activities: {str(e)}"
        )


@router.post("/company/{company_id}")
async def sync_company_wallets(
    company_id: str,
    days_back: int = 30,
    force_refresh: bool = False,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Sync activities for all wallets in a company."""
    try:
        # Verify user owns the company
        company = get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Sync all company wallets
        result = await wallet_sync_service.sync_company_wallets(company_id)
        
        return {
            "success": result['success'],
            "message": result.get('message', ''),
            "wallets_processed": result.get('wallets_processed', 0),
            "successful_wallets": result.get('successful_wallets', 0),
            "failed_wallets": result.get('failed_wallets', 0),
            "total_transactions": result.get('total_transactions', 0),
            "error": result.get('error')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error syncing company wallets: {str(e)}"
        )

@router.post("/company/{company_id}/ytd")
async def sync_company_wallets_ytd(
    company_id: str,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Sync all wallets for a company from the start of the current year (YTD)."""
    try:
        # Verify user owns the company
        company = get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        start_of_year = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc)
        result = await wallet_activity_fetcher.fetch_all_wallet_activities(
            company_id=company_id,
            force_refresh=True,
            start_date=start_of_year,
            end_date=datetime.now(timezone.utc)
        )
        return {
            "success": result.get("success", False),
            "wallets_processed": result.get("wallets_processed", 0),
            "total_transactions": result.get("total_transactions", 0),
            "start_date": start_of_year.isoformat(),
            "end_date": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing YTD company wallets: {str(e)}")


@router.post("/wallet/{wallet_id}/ytd")
async def sync_wallet_ytd(
    wallet_id: UUID,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Sync a single wallet from the start of the current year (YTD)."""
    try:
        # Verify user has access to this wallet
        from ..crud.wallets import wallet_crud
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

        start_of_year = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc)
        result = await wallet_activity_fetcher.fetch_wallet_activities(
            str(wallet_id),
            force_refresh=True,
            start_date=start_of_year,
            end_date=datetime.now(timezone.utc)
        )
        return {
            "success": result.get("success", False),
            "transactions_fetched": result.get("transactions_fetched", 0),
            "transactions_stored": result.get("transactions_stored", 0),
            "start_date": start_of_year.isoformat(),
            "end_date": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error syncing YTD wallet: {str(e)}")


@router.get("/wallet/{wallet_id}/summary")
async def get_wallet_activity_summary(
    wallet_id: UUID,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get wallet activity summary."""
    try:
        # Verify user has access to this wallet
        from ..crud.wallets import wallet_crud
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Check if user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get activity summary
        summary = await wallet_activity_fetcher.get_wallet_activity_summary(str(wallet_id))
        
        return {
            "success": True,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting wallet activity summary: {str(e)}"
        )


@router.post("/trigger/on-connect/{wallet_id}")
async def trigger_initial_sync(
    wallet_id: UUID,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Trigger initial sync for a newly connected wallet."""
    try:
        # Verify user has access to this wallet
        from ..crud.wallets import wallet_crud
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Check if user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Trigger initial sync
        result = await wallet_sync_service.sync_wallet_on_connect(str(wallet_id))
        
        return {
            "success": result['success'],
            "message": result.get('message', ''),
            "transactions_fetched": result.get('transactions_fetched', 0),
            "transactions_stored": result.get('transactions_stored', 0),
            "error": result.get('error')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering initial sync: {str(e)}"
        )
