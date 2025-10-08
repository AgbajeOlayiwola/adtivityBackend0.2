"""Twitter API endpoints for managing Twitter integration."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta
from uuid import UUID

from ..core.database import get_db
from ..core.security import get_current_platform_user
from ..core.twitter_service import twitter_service
from ..core.background_tasks import background_task_service
from ..crud.twitter import twitter_crud
from .. import crud
from ..schemas import (
    CompanyTwitterCreate, CompanyTwitterResponse, CompanyTwitterUpdate,
    TwitterTweetResponse, TwitterFollowerResponse, TwitterAnalyticsResponse,
    TwitterSyncRequest, TwitterSyncResponse, HashtagMentionResponse,
    MentionResponse, MentionAnalyticsResponse, MentionSearchRequest, MentionNotificationRequest,
    TwitterUserSuggestion, TwitterHandleValidationRequest, TwitterHandleValidationResponse,
    TwitterUserSearchRequest, TwitterUserSearchResponse, HashtagSearchRequest, HashtagSearchResponse
)
from ..models import PlatformUser

router = APIRouter(prefix="/twitter", tags=["Twitter"])


@router.post("/accounts/", response_model=CompanyTwitterResponse)
async def create_twitter_account(
    twitter_data: CompanyTwitterCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Create a new Twitter account for a company."""
    # Check if company exists and user has access
    # TODO: Add company access validation
    
    # Validate Twitter handle first
    handle_validation = await twitter_service.validate_twitter_handle(twitter_data.twitter_handle)
    
    if not handle_validation["valid"]:
        # Return validation error with suggestions
        raise HTTPException(
            status_code=400, 
            detail={
                "message": "Invalid Twitter handle",
                "error": handle_validation["error"],
                "suggestions": handle_validation["suggestions"],
                "handle": twitter_data.twitter_handle
            }
        )
    
    # Check if Twitter handle already exists in our system
    existing = twitter_crud.get_company_twitter_by_handle(db, twitter_data.twitter_handle)
    if existing:
        raise HTTPException(status_code=400, detail="Twitter handle already exists in our system")
    
    # Get Twitter profile data to populate additional fields
    user_data = handle_validation["user_data"]
    
    # Create enhanced Twitter account data
    enhanced_twitter_data = CompanyTwitterCreate(
        company_id=twitter_data.company_id,
        twitter_handle=twitter_data.twitter_handle,
        description=twitter_data.description or user_data.description
    )
    
    # Create Twitter account
    twitter_account = twitter_crud.create_company_twitter(db, enhanced_twitter_data)
    
    # Update with Twitter API data
    twitter_account.twitter_user_id = user_data.id
    twitter_account.followers_count = user_data.followers_count
    twitter_account.following_count = user_data.following_count
    twitter_account.tweets_count = user_data.tweets_count
    twitter_account.profile_image_url = user_data.profile_image_url
    twitter_account.verified = user_data.verified
    twitter_account.last_updated = datetime.utcnow()
    
    # Update company's Twitter integration status
    company = crud.get_client_company_by_id(db, twitter_data.company_id)
    if company:
        company.is_twitter_added = True
    
    db.commit()
    db.refresh(twitter_account)
    
    # Convert to response schema with proper UUID handling
    return CompanyTwitterResponse.from_orm(twitter_account)


@router.get("/accounts/{twitter_id}", response_model=CompanyTwitterResponse)
async def get_twitter_account(
    twitter_id: UUID,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get Twitter account by ID."""
    twitter_account = twitter_crud.get_company_twitter(db, twitter_id)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    # Convert to response schema with proper UUID handling
    return CompanyTwitterResponse.from_orm(twitter_account)


@router.put("/accounts/{twitter_id}", response_model=CompanyTwitterResponse)
async def update_twitter_account(
    twitter_id: UUID,
    update_data: CompanyTwitterUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Update Twitter account."""
    twitter_account = twitter_crud.update_company_twitter(db, twitter_id, update_data)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    # Convert to response schema with proper UUID handling
    return CompanyTwitterResponse.from_orm(twitter_account)


@router.delete("/accounts/{twitter_id}")
async def delete_twitter_account(
    twitter_id: UUID,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Delete Twitter account."""
    company_id = twitter_crud.delete_company_twitter(db, twitter_id)
    if not company_id:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    # Check if company has any other Twitter accounts
    remaining_twitter_accounts = twitter_crud.get_company_twitter_by_company(db, company_id)
    
    # Update company's Twitter integration status
    company = crud.get_client_company_by_id(db, company_id)
    if company:
        # Set to False if no Twitter accounts remain, True if others exist
        company.is_twitter_added = remaining_twitter_accounts is not None
        db.commit()
    
    return {"message": "Twitter account deleted successfully"}


@router.post("/sync/", response_model=TwitterSyncResponse)
async def sync_twitter_data(
    sync_request: TwitterSyncRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Sync Twitter data for a company."""
    try:
        # Get or create Twitter account
        twitter_account = twitter_crud.get_company_twitter_by_company(db, sync_request.company_id)
        if not twitter_account:
            # Create new Twitter account
            twitter_data = CompanyTwitterCreate(
                company_id=sync_request.company_id,
                twitter_handle=sync_request.twitter_handle
            )
            twitter_account = twitter_crud.create_company_twitter(db, twitter_data)
        
        # Fetch Twitter profile data
        profile_data = await twitter_service.get_user_by_username(sync_request.twitter_handle)
        if not profile_data:
            raise HTTPException(status_code=404, detail="Twitter user not found")
        
        # Update profile data
        update_data = CompanyTwitterUpdate(
            description=profile_data.description
        )
        twitter_crud.update_company_twitter(db, twitter_account.id, update_data)
        
        # Update basic profile info
        twitter_account.twitter_user_id = profile_data.id
        twitter_account.followers_count = profile_data.followers_count
        twitter_account.following_count = profile_data.following_count
        twitter_account.tweets_count = profile_data.tweets_count
        twitter_account.profile_image_url = profile_data.profile_image_url
        twitter_account.verified = profile_data.verified
        twitter_account.last_updated = datetime.utcnow()
        db.commit()
        
        tweets_synced = 0
        followers_synced = 0
        errors = []
        
        # Sync tweets if requested
        if sync_request.sync_tweets and profile_data.id:
            try:
                tweets = await twitter_service.get_user_tweets(
                    profile_data.id, 
                    sync_request.max_tweets
                )
                
                for tweet in tweets:
                    # Check if tweet already exists
                    existing_tweet = twitter_crud.get_tweet_by_id(db, tweet.tweet_id)
                    if not existing_tweet:
                        tweet_data = {
                            "tweet_id": tweet.tweet_id,
                            "company_twitter_id": twitter_account.id,
                            "text": tweet.text,
                            "created_at": tweet.created_at,
                            "retweet_count": tweet.retweet_count,
                            "like_count": tweet.like_count,
                            "reply_count": tweet.reply_count,
                            "quote_count": tweet.quote_count,
                            "hashtags": tweet.hashtags,
                            "mentions": tweet.mentions
                        }
                        
                        twitter_crud.create_tweet(db, tweet_data)
                        tweets_synced += 1
                        
            except Exception as e:
                errors.append(f"Error syncing tweets: {str(e)}")
        
        # Sync followers if requested
        if sync_request.sync_followers and profile_data.id:
            try:
                followers = await twitter_service.get_user_followers(
                    profile_data.id, 
                    sync_request.max_followers
                )
                
                for follower in followers:
                    # Check if follower already exists
                    existing_follower = twitter_crud.get_follower_by_id(
                        db, follower.follower_id, twitter_account.id
                    )
                    if not existing_follower:
                        follower_data = {
                            "follower_id": follower.follower_id,
                            "company_twitter_id": twitter_account.id,
                            "username": follower.username,
                            "display_name": follower.display_name,
                            "verified": follower.verified,
                            "followers_count": follower.followers_count,
                            "following_count": follower.following_count,
                            "tweets_count": follower.tweets_count
                        }
                        
                        twitter_crud.create_follower(db, follower_data)
                        followers_synced += 1
                        
            except Exception as e:
                errors.append(f"Error syncing followers: {str(e)}")
        
        return TwitterSyncResponse(
            success=True,
            message="Twitter data synced successfully",
            profile_updated=True,
            tweets_synced=tweets_synced,
            followers_synced=followers_synced,
            errors=errors
        )
        
    except Exception as e:
        return TwitterSyncResponse(
            success=False,
            message=f"Error syncing Twitter data: {str(e)}",
            errors=[str(e)]
        )


@router.get("/accounts/{twitter_id}/tweets", response_model=List[TwitterTweetResponse])
async def get_company_tweets(
    twitter_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get tweets for a company Twitter account."""
    tweets = twitter_crud.get_company_tweets(db, twitter_id, limit)
    return tweets


@router.get("/accounts/{twitter_id}/followers", response_model=List[TwitterFollowerResponse])
async def get_company_followers(
    twitter_id: UUID,
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get followers for a company Twitter account."""
    followers = twitter_crud.get_company_followers(db, twitter_id, limit)
    return followers


@router.post("/search/hashtag", response_model=HashtagSearchResponse)
async def search_hashtag(
    search_request: HashtagSearchRequest,
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Search for tweets with a specific hashtag."""
    results = await twitter_service.search_hashtag(search_request.hashtag, search_request.max_results)
    return HashtagSearchResponse(
        hashtag=search_request.hashtag,
        results_count=len(results),
        tweets=results
    )


# New Mention-related Endpoints
@router.get("/accounts/{twitter_id}/mentions", response_model=List[MentionResponse])
async def get_company_mentions(
    twitter_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get all mentions of a company Twitter account."""
    mentions = twitter_crud.get_company_mentions(db, twitter_id, limit)
    return mentions


@router.get("/accounts/{twitter_id}/mentions/analytics")
async def get_mention_analytics(
    twitter_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get mention analytics for a company Twitter account within a date range in frontend-compatible format."""
    analytics = twitter_crud.get_mention_analytics(db, twitter_id, start_date, end_date)
    
    # Transform to frontend-compatible format
    days_diff = (end_date - start_date).days + 1
    
    # Convert mentions_by_date to array format expected by frontend
    mentions_by_date_array = []
    for i in range(days_diff):
        current_date = start_date + timedelta(days=i)
        day_data = analytics['mentions_by_date'].get(current_date, {
            'count': 0, 'likes': 0, 'retweets': 0, 'replies': 0
        })
        mentions_by_date_array.append({
            "date": f"Day {i + 1}",
            "mentions": day_data['count'],
            "likes": day_data['likes']
        })
    
    # Engagement by type
    engagement_by_type = [
        {"name": "Likes", "value": analytics['total_likes']},
        {"name": "Comments", "value": analytics['total_replies']},
        {"name": "Shares", "value": analytics['total_retweets']}
    ]
    
    # Top topics (mock data for now - you can implement real topic analysis later)
    top_topics = [
        {"name": "Product Launch", "mentions": max(1, analytics['total_mentions'] // 4)},
        {"name": "Customer Service", "mentions": max(1, analytics['total_mentions'] // 6)},
        {"name": "New Features", "mentions": max(1, analytics['total_mentions'] // 8)},
        {"name": "Company News", "mentions": max(1, analytics['total_mentions'] // 10)}
    ]
    
    return {
        "total_mentions": analytics['total_mentions'],
        "total_likes": analytics['total_likes'],
        "total_followers": 0,  # This would need to be calculated from TwitterAnalytics table
        "mentions_by_date": mentions_by_date_array,
        "engagement_by_type": engagement_by_type,
        "top_topics": top_topics
    }


@router.post("/mentions/search", response_model=List[MentionResponse])
async def search_mentions(
    search_request: MentionSearchRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Search for mentions across all company Twitter accounts."""
    # Get company Twitter accounts
    company_twitter = twitter_crud.get_company_twitter_by_company(db, search_request.company_id)
    if not company_twitter:
        raise HTTPException(status_code=404, detail="Company Twitter account not found")
    
    # Search mentions
    if search_request.start_date and search_request.end_date:
        mentions = twitter_crud.get_mentions_by_date_range(
            db, company_twitter.id, search_request.start_date, search_request.end_date
        )
    else:
        mentions = twitter_crud.get_company_mentions(db, company_twitter.id, search_request.limit)
    
    return mentions


@router.post("/mentions/notifications/setup")
async def setup_mention_notifications(
    notification_request: MentionNotificationRequest,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Set up mention notifications for a company."""
    # This is a placeholder for future notification system implementation
    # For now, we'll just return a success message
    
    # Verify company exists
    company_twitter = twitter_crud.get_company_twitter_by_company(db, notification_request.company_id)
    if not company_twitter:
        raise HTTPException(status_code=404, detail="Company Twitter account not found")
    
    return {
        "message": "Mention notifications configured successfully",
        "company_id": notification_request.company_id,
        "twitter_handle": notification_request.twitter_handle,
        "notification_email": notification_request.notification_email,
        "notification_webhook": notification_request.notification_webhook,
        "mention_keywords": notification_request.mention_keywords,
        "is_active": notification_request.is_active
    }


@router.get("/mentions/recent", response_model=List[MentionResponse])
async def get_recent_mentions(
    company_id: str = Query(...),
    hours: int = Query(24, ge=1, le=168),  # Default to last 24 hours, max 1 week
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get recent mentions for a company within the last N hours."""
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)
    
    # Get company Twitter account
    company_twitter = twitter_crud.get_company_twitter_by_company(db, company_id)
    if not company_twitter:
        raise HTTPException(status_code=404, detail="Company Twitter account not found")
    
    # Get mentions in time range
    mentions = twitter_crud.get_mentions_by_date_range(
        db, company_twitter.id, start_time, end_time
    )
    
    # Limit results
    return mentions[:limit]


# Twitter User Autocomplete Endpoints
@router.post("/users/search", response_model=TwitterUserSearchResponse)
async def search_twitter_users(
    search_request: TwitterUserSearchRequest,
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Search for Twitter users with autocomplete functionality."""
    try:
        users = await twitter_service.search_users_autocomplete(
            search_request.query, 
            search_request.max_results
        )
        
        return TwitterUserSearchResponse(
            users=users,
            query=search_request.query,
            total_results=len(users)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching users: {str(e)}")


@router.post("/users/validate", response_model=TwitterHandleValidationResponse)
async def validate_twitter_handle(
    validation_request: TwitterHandleValidationRequest,
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Validate a Twitter handle and get suggestions if invalid."""
    try:
        validation_result = await twitter_service.validate_twitter_handle(
            validation_request.handle
        )
        
        return TwitterHandleValidationResponse(**validation_result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating handle: {str(e)}")


@router.get("/users/autocomplete")
async def get_twitter_user_suggestions(
    query: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    max_results: int = Query(5, ge=1, le=20, description="Maximum number of results (default: 5 for free API)"),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get Twitter user suggestions for autocomplete (lightweight endpoint)."""
    try:
        if len(query.strip()) < 2:
            return {"users": [], "query": query, "total_results": 0}
        
        users = await twitter_service.search_users_autocomplete(query.strip(), max_results)
        
        # Filter out any users with missing required data
        valid_users = []
        for user in users:
            if user and user.get("id") and user.get("username"):
                valid_users.append(user)
        
        return {
            "users": valid_users,
            "query": query,
            "total_results": len(valid_users)
        }
        
    except Exception as e:
        print(f"Error fetching Twitter user {query}: {e}")
        # Return empty results instead of throwing error to prevent frontend crashes
        return {
            "users": [],
            "query": query,
            "total_results": 0,
            "error": "Unable to fetch suggestions at this time"
        }


@router.get("/users/quick-validate/{handle}")
async def quick_validate_handle(
    handle: str,
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Quick validation of a Twitter handle (for real-time input validation)."""
    try:
        # Clean the handle
        clean_handle = handle.lstrip("@").strip()
        
        if not clean_handle:
            return {
                "valid": False,
                "error": "Handle cannot be empty",
                "handle": handle
            }
        
        # Quick check if handle exists
        user_data = await twitter_service.get_user_by_username(clean_handle)
        
        if user_data:
            return {
                "valid": True,
                "handle": clean_handle,
                "exists": True,
                "username": user_data.username,
                "name": user_data.name,
                "verified": user_data.verified,
                "followers_count": user_data.followers_count
            }
        else:
            return {
                "valid": False,
                "handle": clean_handle,
                "exists": False,
                "error": "Twitter handle not found"
            }
            
    except Exception as e:
        return {
            "valid": False,
            "error": f"Error validating handle: {str(e)}",
            "handle": handle
        }


# Background Sync Management Endpoints
@router.post("/sync/trigger")
async def trigger_auto_sync(
    company_id: str = Query(..., description="Company ID to sync"),
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Manually trigger sync for a specific company."""
    try:
        # Verify user owns this company
        company = crud.get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Trigger on-demand sync
        await background_task_service.sync_account_on_demand(company_id)
        
        return {
            "success": True,
            "message": f"Sync triggered for company {company_id}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering sync: {str(e)}"
        )


@router.get("/sync/status")
async def get_sync_status(
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get the status of automatic sync service."""
    return {
        "auto_sync_running": background_task_service.is_running,
        "sync_interval_seconds": background_task_service.sync_interval,
        "next_sync_in": f"{background_task_service.sync_interval} seconds" if background_task_service.is_running else "Not running",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/rate-limit/status")
async def get_rate_limit_status(
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get current Twitter API rate limit status."""
    import time
    from ..core.twitter_service import twitter_service
    
    current_time = time.time()
    rate_limit_info = {
        "rate_limit_reset": twitter_service.rate_limit_reset,
        "rate_limit_active": current_time < twitter_service.rate_limit_reset,
        "seconds_until_reset": max(0, twitter_service.rate_limit_reset - current_time),
        "daily_requests_used": twitter_service.request_count,
        "daily_request_limit": twitter_service.daily_request_limit,
        "daily_requests_remaining": max(0, twitter_service.daily_request_limit - twitter_service.request_count),
        "cache_size": len(twitter_service.user_cache),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if rate_limit_info["rate_limit_active"]:
        rate_limit_info["reset_time"] = datetime.fromtimestamp(twitter_service.rate_limit_reset).isoformat()
    
    return rate_limit_info


@router.post("/sync/start")
async def start_auto_sync(
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Start automatic sync service (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if background_task_service.is_running:
        return {
            "success": False,
            "message": "Auto sync is already running",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    # Start auto sync in background
    import asyncio
    asyncio.create_task(background_task_service.start_auto_sync())
    
    return {
        "success": True,
        "message": "Auto sync started",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/sync/stop")
async def stop_auto_sync(
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Stop automatic sync service (admin only)."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    background_task_service.stop_auto_sync()
    
    return {
        "success": True,
        "message": "Auto sync stopped",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/sync/initial")
async def initial_sync_all_tweets(
    company_id: str = Query(..., description="Company ID to sync"),
    max_tweets: int = Query(500, ge=1, le=1000, description="Maximum tweets to sync"),
    current_user: PlatformUser = Depends(get_current_platform_user),
    db: Session = Depends(get_db)
):
    """Perform initial sync of all available tweets for a company."""
    try:
        # Verify user owns this company
        company = crud.get_client_company_by_id(db, company_id)
        if not company or company.platform_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Get Twitter account
        twitter_account = twitter_crud.get_company_twitter_by_company(db, company_id)
        if not twitter_account:
            raise HTTPException(status_code=404, detail="No Twitter account found for this company")
        
        # Fetch all available tweets
        profile_data = await twitter_service.get_user_by_username(twitter_account.twitter_handle)
        if not profile_data:
            raise HTTPException(status_code=404, detail="Twitter user not found")
        
        tweets = await twitter_service.get_user_tweets(profile_data.id, max_results=max_tweets)
        
        tweets_synced = 0
        for tweet in tweets:
            # Check if tweet already exists
            existing_tweet = twitter_crud.get_tweet_by_id(db, tweet.tweet_id)
            if not existing_tweet:
                tweet_data = {
                    "tweet_id": tweet.tweet_id,
                    "company_twitter_id": twitter_account.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at,
                    "retweet_count": tweet.retweet_count,
                    "like_count": tweet.like_count,
                    "reply_count": tweet.reply_count,
                    "quote_count": tweet.quote_count,
                    "hashtags": tweet.hashtags,
                    "mentions": tweet.mentions
                }
                
                twitter_crud.create_tweet(db, tweet_data)
                tweets_synced += 1
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Initial sync completed for @{twitter_account.twitter_handle}",
            "tweets_synced": tweets_synced,
            "total_tweets_fetched": len(tweets),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error in initial sync: {str(e)}"
        )
