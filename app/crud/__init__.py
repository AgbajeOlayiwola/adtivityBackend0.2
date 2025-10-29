"""CRUD operations module."""

from .auth import get_password_hash, verify_password
from .users import (
    create_platform_user,
    get_platform_user_by_email,
    get_platform_user_by_id,
    authenticate_platform_user,
    create_client_app_user,
    get_client_app_user,
    get_client_app_user_by_email,
    get_client_app_user_by_wallet,
    update_client_app_user_verification,
    upsert_client_app_user_from_sdk_event
)
from .companies import (
    create_client_company_with_api_key,
    get_client_company_by_api_key,
    get_client_company_by_id,
    get_client_company_by_name,
    get_client_companies_by_platform_user,
    regenerate_client_company_api_key,
    get_twitter_profile_by_platform_user
)
from .events import (
    create_event,
    get_events_for_client_company,
    create_web3_event,
    get_web3_events_for_client_company,
    handle_sdk_event,
    handle_web3_sdk_event,
    get_all_events_for_user
)
from .metrics import (
    create_platform_metric,
    get_metrics_by_timeframe_for_companies,
    calculate_growth_rate
)
from .regions import (
    get_region_analytics,
    get_user_locations
)
from .user_engagement import user_engagement_crud
from . import payments


__all__ = [
    # Auth
    "get_password_hash",
    "verify_password",
    
    # Users
    "create_platform_user",
    "get_platform_user_by_email",
    "get_platform_user_by_id",
    "authenticate_platform_user",
    "create_client_app_user",
    "get_client_app_user",
    "get_client_app_user_by_email",
    "get_client_app_user_by_wallet",
    "update_client_app_user_verification",
    "upsert_client_app_user_from_sdk_event",
    
    # Companies
    "create_client_company_with_api_key",
    "get_client_company_by_api_key",
    "get_client_company_by_id",
    "get_client_company_by_name",
    "get_client_companies_by_platform_user",
    "regenerate_client_company_api_key",
    "get_twitter_profile_by_platform_user",
    
    # Events
    "create_event",
    "get_events_for_client_company",
    "create_web3_event",
    "get_web3_events_for_client_company",
    "handle_sdk_event",
    "handle_web3_sdk_event",
    "get_all_events_for_user",
    
    # Metrics
    "create_platform_metric",
    "get_metrics_by_timeframe_for_companies",
    "calculate_growth_rate",
    
    # Region Analytics
    "get_region_analytics",
    "get_user_locations",
    
    # User Engagement
    "user_engagement_crud",
    
    # Payments
    "payments",
] 