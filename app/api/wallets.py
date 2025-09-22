"""API endpoints for wallet connections and Web3 analytics."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from datetime import datetime, timedelta

from ..core.database import get_db
from ..core.security import get_current_platform_user
from ..models import PlatformUser
from ..schemas import (
    WalletConnectionCreate,
    WalletConnectionUpdate,
    WalletConnectionResponse,
    WalletActivityResponse,
    WalletVerificationRequest,
    WalletVerificationResponse,
    WalletAnalyticsResponse
)
from ..crud.companies import get_client_company_by_id
from ..crud.wallets import wallet_crud, wallet_activity_crud

router = APIRouter()


@router.post("/connections/", response_model=WalletConnectionResponse)
async def create_wallet_connection(
    wallet_data: WalletConnectionCreate,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Connect a wallet to a company for Web3 analytics."""
    try:
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet_data.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Check if wallet already exists for this company
        existing_wallet = wallet_crud.get_wallet_connection_by_address(
            db, wallet_data.company_id, wallet_data.wallet_address
        )
        if existing_wallet:
            raise HTTPException(
                status_code=400, 
                detail="Wallet already connected to this company"
            )
        
        # Create wallet connection
        wallet_connection = wallet_crud.create_wallet_connection(db, wallet_data)
        
        return WalletConnectionResponse.from_orm(wallet_connection)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating wallet connection: {str(e)}"
        )


@router.get("/connections/", response_model=List[WalletConnectionResponse])
async def get_company_wallets(
    company_id: str = Query(..., description="Company ID"),
    active_only: bool = Query(True, description="Show only active wallets"),
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get all wallet connections for a company."""
    try:
        # Verify user owns the company
        company = get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Company not found")
        
        wallets = wallet_crud.get_company_wallets(
            db, UUID(company_id), active_only=active_only
        )
        
        return [WalletConnectionResponse.from_orm(wallet) for wallet in wallets]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching wallet connections: {str(e)}"
        )


@router.get("/connections/{wallet_id}", response_model=WalletConnectionResponse)
async def get_wallet_connection(
    wallet_id: UUID,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get a specific wallet connection."""
    try:
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        return WalletConnectionResponse.from_orm(wallet)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching wallet connection: {str(e)}"
        )


@router.put("/connections/{wallet_id}", response_model=WalletConnectionResponse)
async def update_wallet_connection(
    wallet_id: UUID,
    wallet_data: WalletConnectionUpdate,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Update a wallet connection."""
    try:
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        updated_wallet = wallet_crud.update_wallet_connection(db, wallet_id, wallet_data)
        return WalletConnectionResponse.from_orm(updated_wallet)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating wallet connection: {str(e)}"
        )


@router.delete("/connections/{wallet_id}")
async def delete_wallet_connection(
    wallet_id: UUID,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Delete a wallet connection."""
    try:
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = wallet_crud.delete_wallet_connection(db, wallet_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete wallet connection")
        
        return {"message": "Wallet connection deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting wallet connection: {str(e)}"
        )


@router.post("/verify", response_model=WalletVerificationResponse)
async def verify_wallet_connection(
    verification_data: WalletVerificationRequest,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Verify wallet ownership through signature."""
    try:
        # Find wallet connection by address AND company owned by current user
        # Note: This is a simplified verification - in production, you'd verify the signature
        from ..models import WalletConnection, ClientCompany
        # Find wallet connection by exact address match (case-sensitive)
        wallet = db.query(WalletConnection).join(
            ClientCompany
        ).filter(
            WalletConnection.wallet_address == verification_data.wallet_address,
            ClientCompany.platform_user_id == current_user.id
        ).first()
        
        if not wallet:
            return WalletVerificationResponse(
                verified=False,
                message="Wallet connection not found for your company",
                wallet_connection_id=None
            )
        
        # Multi-chain signature verification implementation
        from ..core.multi_chain_signature_verification import verify_wallet_ownership_multi_chain
        
        # Verify wallet ownership with cryptographic signature verification (supports multiple chains)
        is_valid, error_message = verify_wallet_ownership_multi_chain(
            wallet_address=verification_data.wallet_address,
            message=verification_data.message,
            signature=verification_data.signature,
            expected_company=str(wallet.company_id)
        )
        
        if is_valid:
            # Mark wallet as verified in database
            verified_wallet = wallet_crud.verify_wallet_connection(db, wallet.id)
            if verified_wallet:
                # Trigger initial sync for the newly verified wallet
                try:
                    from ..core.wallet_sync_service import wallet_sync_service
                    # Start initial sync in background
                    import asyncio
                    asyncio.create_task(wallet_sync_service.sync_wallet_on_connect(str(verified_wallet.id)))
                except Exception as sync_error:
                    # Log sync error but don't fail the verification
                    print(f"Warning: Failed to trigger initial sync: {sync_error}")
                
                return WalletVerificationResponse(
                    verified=True,
                    message="Wallet verified successfully",
                    wallet_connection_id=str(verified_wallet.id)
                )
            else:
                return WalletVerificationResponse(
                    verified=False,
                    message="Failed to verify wallet connection",
                    wallet_connection_id=str(wallet.id)
                )
        else:
            return WalletVerificationResponse(
                verified=False,
                message=f"Verification failed: {error_message}",
                wallet_connection_id=str(wallet.id)
            )
        
    except Exception as e:
        return WalletVerificationResponse(
            verified=False,
            message=f"Verification error: {str(e)}",
            wallet_connection_id=None
        )


@router.get("/connections/{wallet_id}/activities", response_model=List[WalletActivityResponse])
async def get_wallet_activities(
    wallet_id: UUID,
    limit: int = Query(100, ge=1, le=1000, description="Number of activities to return"),
    offset: int = Query(0, ge=0, description="Number of activities to skip"),
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get wallet activities for a specific wallet connection."""
    try:
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        activities = wallet_activity_crud.get_wallet_activities(
            db, wallet_id, limit=limit, offset=offset
        )
        
        return [WalletActivityResponse.from_orm(activity) for activity in activities]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching wallet activities: {str(e)}"
        )


@router.get("/connections/{wallet_id}/analytics", response_model=WalletAnalyticsResponse)
async def get_wallet_analytics(
    wallet_id: UUID,
    start_date: Optional[datetime] = Query(None, description="Start date for analytics"),
    end_date: Optional[datetime] = Query(None, description="End date for analytics"),
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get analytics for a specific wallet connection."""
    try:
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        analytics = wallet_activity_crud.get_wallet_analytics(
            db, wallet_id, start_date=start_date, end_date=end_date
        )
        
        # Add wallet address to response
        analytics["wallet_address"] = wallet.wallet_address
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching wallet analytics: {str(e)}"
        )


@router.get("/connections/{wallet_id}/recent", response_model=List[WalletActivityResponse])
async def get_recent_wallet_activities(
    wallet_id: UUID,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get recent wallet activities within specified hours."""
    try:
        wallet = wallet_crud.get_wallet_connection(db, wallet_id)
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet connection not found")
        
        # Verify user owns the company
        company = get_client_company_by_id(db, str(wallet.company_id))
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        activities = wallet_activity_crud.get_recent_activities(
            db, wallet_id, hours=hours
        )
        
        return [WalletActivityResponse.from_orm(activity) for activity in activities]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching recent wallet activities: {str(e)}"
        )


@router.get("/company/{company_id}/overview")
async def get_company_wallet_overview(
    company_id: str,
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Get wallet overview for a company."""
    try:
        # Verify user owns the company
        company = get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Company not found")
        
        wallets = wallet_crud.get_company_wallets(db, UUID(company_id))
        
        total_wallets = len(wallets)
        verified_wallets = len([w for w in wallets if w.is_verified])
        active_wallets = len([w for w in wallets if w.is_active])
        
        # Get total transactions across all wallets
        total_transactions = 0
        total_volume_usd = 0
        networks = set()
        
        for wallet in wallets:
            analytics = wallet_activity_crud.get_wallet_analytics(db, wallet.id)
            total_transactions += analytics["total_transactions"]
            total_volume_usd += float(analytics["total_volume_usd"])
            networks.update(analytics["networks"])
        
        return {
            "company_id": company_id,
            "total_wallets": total_wallets,
            "verified_wallets": verified_wallets,
            "active_wallets": active_wallets,
            "total_transactions": total_transactions,
            "total_volume_usd": total_volume_usd,
            "networks": list(networks),
            "wallets": [
                {
                    "id": str(wallet.id),
                    "wallet_address": wallet.wallet_address,
                    "wallet_type": wallet.wallet_type,
                    "network": wallet.network,
                    "is_verified": wallet.is_verified,
                    "is_active": wallet.is_active,
                    "last_activity": wallet.last_activity
                }
                for wallet in wallets
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching company wallet overview: {str(e)}"
        )
