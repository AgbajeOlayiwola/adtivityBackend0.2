"""CSV import endpoints for enriching wallet and user data."""

import csv
import io
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_platform_user
from app import models, schemas, crud
from app.crud import users as crud_users
from app.crud import companies as crud_companies

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/wallets/", response_model=schemas.ImportResult)
async def import_wallets_csv(
    file: UploadFile = File(..., description="CSV file with wallet data"),
    company_id: Optional[str] = Form(None, description="Company ID to associate wallets with"),
    update_existing: bool = Form(False, description="Update existing wallets if found"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.ImportResult:
    """
    Import wallets from CSV file to enrich user data.
    
    Expected CSV columns:
    - wallet_address (required): The wallet address
    - wallet_type (optional): Type of wallet (e.g., 'metamask', 'walletconnect')
    - user_id (optional): Associated user ID
    - email (optional): User email
    - name (optional): User name
    - country (optional): Country code
    - region (optional): Region/state
    - city (optional): City
    - tags (optional): Comma-separated tags
    """
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    # Verify company ownership if company_id provided
    company = None
    if company_id:
        company = crud_companies.get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found or access denied"
            )
    
    try:
        # Read CSV content
        content = await file.read()
        csv_text = content.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        imported_count = 0
        updated_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because row 1 is header
            try:
                # Validate required fields
                if not row.get('wallet_address'):
                    errors.append(f"Row {row_num}: Missing wallet_address")
                    continue
                
                wallet_address = row['wallet_address'].strip()
                if not wallet_address:
                    errors.append(f"Row {row_num}: Empty wallet_address")
                    continue
                
                # Check if wallet already exists
                existing_wallet = crud_users.get_user_by_wallet_address(db, wallet_address)
                
                if existing_wallet and not update_existing:
                    errors.append(f"Row {row_num}: Wallet {wallet_address} already exists (use update_existing=true)")
                    continue
                
                # Prepare wallet data
                wallet_data = {
                    'wallet_address': wallet_address,
                    'wallet_type': row.get('wallet_type', '').strip() or None,
                    'country': row.get('country', '').strip() or None,
                    'region': row.get('region', '').strip() or None,
                    'city': row.get('city', '').strip() or None,
                }
                
                # Handle tags
                tags = row.get('tags', '').strip()
                if tags:
                    wallet_data['tags'] = [tag.strip() for tag in tags.split(',') if tag.strip()]
                
                if existing_wallet and update_existing:
                    # Update existing wallet
                    crud_users.update_user_wallet_info(db, existing_wallet.id, wallet_data)
                    updated_count += 1
                else:
                    # Create new wallet entry
                    wallet_data['company_id'] = company.id if company else None
                    wallet_data['platform_user_id'] = current_user.id
                    
                    # Handle user association
                    if row.get('user_id'):
                        wallet_data['user_id'] = row['user_id'].strip()
                    elif row.get('email'):
                        # Try to find user by email
                        user = crud_users.get_user_by_email(db, row['email'].strip())
                        if user:
                            wallet_data['user_id'] = str(user.id)
                    
                    # Create wallet user
                    crud_users.create_wallet_user(db, wallet_data)
                    imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                logger.error(f"Error processing row {row_num}: {e}")
        
        return schemas.ImportResult(
            success=True,
            imported_count=imported_count,
            updated_count=updated_count,
            total_rows=len(list(csv.DictReader(io.StringIO(csv_text)))),
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )

@router.post("/users/", response_model=schemas.ImportResult)
async def import_users_csv(
    file: UploadFile = File(..., description="CSV file with user data"),
    company_id: Optional[str] = Form(None, description="Company ID to associate users with"),
    update_existing: bool = Form(False, description="Update existing users if found"),
    current_user: models.PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
) -> schemas.ImportResult:
    """
    Import users from CSV file to enrich user data.
    
    Expected CSV columns:
    - email (required): User email address
    - name (optional): User's full name
    - phone_number (optional): Phone number
    - wallet_address (optional): Associated wallet address
    - wallet_type (optional): Type of wallet
    - country (optional): Country code
    - region (optional): Region/state
    - city (optional): City
    - subscription_plan (optional): Subscription plan
    - tags (optional): Comma-separated tags
    """
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    # Verify company ownership if company_id provided
    company = None
    if company_id:
        company = crud_companies.get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Company not found or access denied"
            )
    
    try:
        # Read CSV content
        content = await file.read()
        csv_text = content.decode('utf-8')
        
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        
        imported_count = 0
        updated_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=2):
            try:
                # Validate required fields
                if not row.get('email'):
                    errors.append(f"Row {row_num}: Missing email")
                    continue
                
                email = row['email'].strip()
                if not email:
                    errors.append(f"Row {row_num}: Empty email")
                    continue
                
                # Check if user already exists
                existing_user = crud_users.get_user_by_email(db, email)
                
                if existing_user and not update_existing:
                    errors.append(f"Row {row_num}: User {email} already exists (use update_existing=true)")
                    continue
                
                # Prepare user data
                user_data = {
                    'email': email,
                    'name': row.get('name', '').strip() or None,
                    'phone_number': row.get('phone_number', '').strip() or None,
                    'country': row.get('country', '').strip() or None,
                    'region': row.get('region', '').strip() or None,
                    'city': row.get('city', '').strip() or None,
                    'subscription_plan': row.get('subscription_plan', '').strip() or None,
                }
                
                # Handle tags
                tags = row.get('tags', '').strip()
                if tags:
                    user_data['tags'] = [tag.strip() for tag in tags.split(',') if tag.strip()]
                
                if existing_user and update_existing:
                    # Update existing user
                    crud_users.update_user_info(db, existing_user.id, user_data)
                    updated_count += 1
                else:
                    # Create new user
                    user_data['company_id'] = company.id if company else None
                    user_data['platform_user_id'] = current_user.id
                    
                    # Handle wallet association
                    if row.get('wallet_address'):
                        wallet_data = {
                            'wallet_address': row['wallet_address'].strip(),
                            'wallet_type': row.get('wallet_type', '').strip() or None,
                            'user_id': None,  # Will be set after user creation
                        }
                    
                    # Create user
                    new_user = crud_users.create_user(db, user_data)
                    
                    # Associate wallet if provided
                    if row.get('wallet_address'):
                        wallet_data['user_id'] = str(new_user.id)
                        wallet_data['company_id'] = company.id if company else None
                        wallet_data['platform_user_id'] = current_user.id
                        crud_users.create_wallet_user(db, wallet_data)
                    
                    imported_count += 1
                
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                logger.error(f"Error processing row {row_num}: {e}")
        
        return schemas.ImportResult(
            success=True,
            imported_count=imported_count,
            updated_count=updated_count,
            total_rows=len(list(csv.DictReader(io.StringIO(csv_text)))),
            errors=errors
        )
        
    except Exception as e:
        logger.error(f"CSV import failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )

@router.get("/templates/", response_model=schemas.ImportTemplates)
async def get_import_templates(
    current_user: models.PlatformUser = Depends(get_current_platform_user)
) -> schemas.ImportTemplates:
    """Get CSV import templates and column descriptions."""
    
    return schemas.ImportTemplates(
        wallet_template={
            "description": "Import wallets to enrich user data",
            "columns": {
                "wallet_address": "Required: The wallet address (e.g., 0x1234...)",
                "wallet_type": "Optional: Type of wallet (e.g., metamask, walletconnect)",
                "user_id": "Optional: Associated user ID",
                "email": "Optional: User email for association",
                "name": "Optional: User name",
                "country": "Optional: Country code (e.g., US, CA)",
                "region": "Optional: Region/state (e.g., California)",
                "city": "Optional: City name",
                "tags": "Optional: Comma-separated tags (e.g., premium,active)"
            },
            "example_row": {
                "wallet_address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6",
                "wallet_type": "metamask",
                "email": "user@example.com",
                "name": "John Doe",
                "country": "US",
                "region": "California",
                "city": "San Francisco",
                "tags": "premium,active"
            }
        },
        user_template={
            "description": "Import users to enrich user data",
            "columns": {
                "email": "Required: User email address",
                "name": "Optional: User's full name",
                "phone_number": "Optional: Phone number",
                "wallet_address": "Optional: Associated wallet address",
                "wallet_type": "Optional: Type of wallet",
                "country": "Optional: Country code (e.g., US, CA)",
                "region": "Optional: Region/state (e.g., California)",
                "city": "Optional: City name",
                "subscription_plan": "Optional: Subscription plan (e.g., basic,premium)",
                "tags": "Optional: Comma-separated tags (e.g., vip,beta)"
            },
            "example_row": {
                "email": "jane@example.com",
                "name": "Jane Smith",
                "phone_number": "+1-555-0123",
                "wallet_address": "0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6",
                "wallet_type": "metamask",
                "country": "CA",
                "region": "Ontario",
                "city": "Toronto",
                "subscription_plan": "premium",
                "tags": "vip,beta"
            }
        }
    )
