"""Twitter API endpoints for managing Twitter integration."""

from typing import List, Optional
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path
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
    CompanyTwitterCreate, CompanyTwitterResponse, CompanyTwitterUpdate, CompanyTwitterPatch,
    TwitterTweetResponse, TwitterFollowerResponse, TwitterAnalyticsResponse,
    TwitterSyncRequest, TwitterSyncResponse, HashtagMentionResponse,
    MentionResponse, MentionAnalyticsResponse, MentionSearchRequest, MentionNotificationRequest,
    TwitterUserSuggestion, TwitterHandleValidationRequest, TwitterHandleValidationResponse,
    TwitterUserSearchRequest, TwitterUserSearchResponse, HashtagSearchRequest, HashtagSearchResponse,
    KOLAnalysisRequest, KOLAnalysisResponse, KOLTweetData
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


@router.patch("/accounts/{twitter_id}", response_model=CompanyTwitterResponse)
async def patch_twitter_account(
    twitter_id: UUID,
    patch_data: CompanyTwitterPatch,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """PATCH update Twitter account - allows partial updates including twitter_handle and twitter_user_id.
    
    This endpoint supports two scenarios:
    
    1. **Username Change (Same Account)**: User changes their Twitter username (@oldname -> @newname)
       - The twitter_user_id remains the same
       - Old tweets/followers are preserved
       - Example: PATCH with {"twitter_handle": "@newname"}
    
    2. **Account Change (Different Account)**: Company wants to switch to a different Twitter account
       - The twitter_user_id changes to a different user
       - Old tweets/followers/analytics are automatically deleted (they belong to the old account)
       - Example: PATCH with {"twitter_handle": "@differentaccount"} where @differentaccount has different user_id
    
    When updating twitter_handle, the system will:
    1. Validate the new handle via Twitter API
    2. Check if it's already taken in our system
    3. Detect if it's the same user (username change) or different user (account change)
    4. Automatically clean up old data if switching to a different account
    5. Fetch and update the latest profile data
    """
    # Get the existing Twitter account
    twitter_account = twitter_crud.get_company_twitter(db, twitter_id)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    # Update fields that are provided
    update_dict = patch_data.model_dump(exclude_unset=True)
    
    if not update_dict:
        # No fields to update
        return CompanyTwitterResponse.from_orm(twitter_account)
    
    # Track if we're changing to a different Twitter account (different user)
    is_changing_account = False
    old_twitter_user_id = twitter_account.twitter_user_id
    
    # Update twitter_handle if provided (this is the @username)
    if "twitter_handle" in update_dict and update_dict["twitter_handle"] is not None:
        new_handle = update_dict["twitter_handle"].strip().lstrip("@")
        
        # Check if handle is different from current one
        if new_handle.lower() != twitter_account.twitter_handle.lower():
            # Validate the new Twitter handle via Twitter API
            handle_validation = await twitter_service.validate_twitter_handle(new_handle)
            
            if not handle_validation["valid"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": "Invalid Twitter handle",
                        "error": handle_validation["error"],
                        "suggestions": handle_validation["suggestions"],
                        "handle": new_handle
                    }
                )
            
            # Check if this handle is already used by another CompanyTwitter record
            existing_account = twitter_crud.get_company_twitter_by_handle(db, new_handle)
            if existing_account and existing_account.id != twitter_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Twitter handle @{new_handle} is already associated with another account in our system"
                )
            
            # Get Twitter profile data
            user_data = handle_validation["user_data"]
            new_twitter_user_id = user_data.id
            
            # Determine if this is the same account (username change) or different account
            if patch_data.twitter_user_id:
                # User explicitly provided twitter_user_id - use it
                if user_data.id != patch_data.twitter_user_id:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Twitter handle @{new_handle} belongs to user ID {user_data.id}, but you provided {patch_data.twitter_user_id}. "
                               f"These don't match. Please remove twitter_user_id to use the handle's actual user ID."
                    )
                new_twitter_user_id = patch_data.twitter_user_id
            elif twitter_account.twitter_user_id:
                # Check if new handle belongs to same user (username change) or different user (account change)
                if user_data.id != twitter_account.twitter_user_id:
                    # Different account - user is changing to a different Twitter account
                    is_changing_account = True
                    new_twitter_user_id = user_data.id
                else:
                    # Same account - just username change
                    new_twitter_user_id = user_data.id
            else:
                # No existing twitter_user_id, so this is a new account assignment
                new_twitter_user_id = user_data.id
            
            # Update the handle
            twitter_account.twitter_handle = new_handle
            
            # Update profile data from Twitter API
            twitter_account.twitter_user_id = new_twitter_user_id
            twitter_account.followers_count = user_data.followers_count
            twitter_account.following_count = user_data.following_count
            twitter_account.tweets_count = user_data.tweets_count
            twitter_account.profile_image_url = user_data.profile_image_url
            twitter_account.verified = user_data.verified
            if not twitter_account.description and user_data.description:
                twitter_account.description = user_data.description
    
    # Update twitter_user_id if provided independently (without handle change)
    if "twitter_user_id" in update_dict and update_dict["twitter_user_id"] is not None:
        new_user_id = update_dict["twitter_user_id"]
        
        # Check if this is a different account
        if twitter_account.twitter_user_id and new_user_id != twitter_account.twitter_user_id:
            is_changing_account = True
            old_twitter_user_id = twitter_account.twitter_user_id
        
        # Check if this twitter_user_id is already used by another CompanyTwitter record
        existing_account = twitter_crud.get_company_twitter_by_twitter_user_id(
            db, new_user_id
        )
        if existing_account and existing_account.id != twitter_id:
            raise HTTPException(
                status_code=400,
                detail=f"Twitter user ID {new_user_id} is already associated with another account in our system"
            )
        twitter_account.twitter_user_id = new_user_id
    
    # If changing to a different Twitter account, clean up old data
    if is_changing_account and old_twitter_user_id:
        # Delete old tweets, followers, and analytics for the old account
        # This is necessary because they're linked to the CompanyTwitter record
        # and should belong to the new account going forward
        from ..models import TwitterTweet, TwitterFollower, TwitterAnalytics
        
        deleted_tweets = db.query(TwitterTweet).filter(
            TwitterTweet.company_twitter_id == twitter_id
        ).delete(synchronize_session=False)
        
        deleted_followers = db.query(TwitterFollower).filter(
            TwitterFollower.company_twitter_id == twitter_id
        ).delete(synchronize_session=False)
        
        deleted_analytics = db.query(TwitterAnalytics).filter(
            TwitterAnalytics.company_twitter_id == twitter_id
        ).delete(synchronize_session=False)
    
    # Update description if provided
    if "description" in update_dict:
        twitter_account.description = update_dict["description"]
    
    # Update last_updated timestamp
    twitter_account.last_updated = datetime.utcnow()
    
    db.commit()
    db.refresh(twitter_account)
    
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
    return [TwitterTweetResponse.from_orm(t) for t in tweets]


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
@router.get("/accounts/{twitter_id}/mentions", response_model=List[TwitterTweetResponse])
async def get_company_mentions(
    twitter_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get all mentions of a company Twitter account."""
    mentions = twitter_crud.get_company_mentions(db, twitter_id, limit)
    # Convert ORM tweets to response schema to handle UUID/string fields
    return [TwitterTweetResponse.from_orm(m) for m in mentions]


@router.get("/accounts/{twitter_id}/mentions/analytics")
async def get_mention_analytics(
    twitter_id: str = Path(..., description="Twitter account UUID"),
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get mention analytics for a company Twitter account within a date range in frontend-compatible format."""
    # Validate twitter_id is not "undefined" and is a valid UUID
    if twitter_id == "undefined" or not twitter_id or twitter_id.strip() == "":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Twitter account ID is required",
                "error": "The twitter_id parameter is missing or undefined. Please ensure the Twitter account is configured before accessing analytics.",
                "hint": "You may need to create or link a Twitter account first using POST /twitter/accounts/"
            }
        )
    
    try:
        twitter_id_uuid = UUID(twitter_id)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid Twitter account ID format",
                "error": f"The provided twitter_id '{twitter_id}' is not a valid UUID.",
                "hint": "Please provide a valid UUID format (e.g., '550e8400-e29b-41d4-a716-446655440000')"
            }
        )
    
    analytics = twitter_crud.get_mention_analytics(db, twitter_id_uuid, start_date, end_date)
    
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


@router.get("/mentions/recent", response_model=List[TwitterTweetResponse])
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
    
    # Limit results and convert
    limited = mentions[:limit]
    return [TwitterTweetResponse.from_orm(m) for m in limited]


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
    twitter_id: str | None = Query(None, description="Optional CompanyTwitter UUID to echo back"),
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
    
    # Echo provided twitter_id for caller convenience
    if twitter_id:
        rate_limit_info["twitter_id"] = twitter_id
    
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


# KOL Analysis Endpoint
@router.post("/kol/analyze", response_model=KOLAnalysisResponse)
async def analyze_kol(
    analysis_request: KOLAnalysisRequest,
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Analyze a Twitter user (KOL - Key Opinion Leader) without adding them to the company.
    
    This endpoint allows companies to search and analyze Twitter users to see:
    - User profile information
    - User's own tweets with total likes and engagement metrics
    - Recent tweets that mention them
    
    No data is saved to the database - this is purely for analysis purposes.
    """
    try:
        # Clean username
        clean_username = analysis_request.username.lstrip("@").strip()
        
        if not clean_username:
            raise HTTPException(status_code=400, detail="Username cannot be empty")
        
        # Get user profile
        profile_data = await twitter_service.get_user_by_username(clean_username)
        
        if not profile_data or not profile_data.id:
            raise HTTPException(
                status_code=404,
                detail=f"Twitter user @{clean_username} not found"
            )
        
        # Fetch user's tweets and mentions
        user_tweets = []
        mentions = []
        errors = []
        
        # Fetch user's own tweets to analyze their engagement (likes they received)
        try:
            user_tweets_raw = await twitter_service.get_user_tweets(
                profile_data.id,
                max_results=analysis_request.max_tweets
            )
            user_tweets = [
                KOLTweetData(
                    tweet_id=tweet.tweet_id,
                    text=tweet.text,
                    created_at=tweet.created_at.isoformat() if tweet.created_at else "",
                    author_username=clean_username,
                    author_name=profile_data.name,
                    author_verified=profile_data.verified,
                    retweet_count=tweet.retweet_count,
                    like_count=tweet.like_count,  # Total likes this tweet received
                    reply_count=tweet.reply_count,
                    quote_count=tweet.quote_count,
                    hashtags=getattr(tweet, 'hashtags', []) or [],
                    mentions=getattr(tweet, 'mentions', []) or []
                )
                for tweet in user_tweets_raw
            ]
        except Exception as e:
            error_msg = f"Error fetching user tweets: {str(e)}"
            errors.append(error_msg)
            print(f"⚠️ {error_msg}")
        
        # Fetch mentions
        try:
            mentions_raw = await twitter_service.get_user_mentions(
                clean_username,
                max_results=analysis_request.max_mentions
            )
            mentions = [
                KOLTweetData(
                    tweet_id=tweet.get("tweet_id", ""),
                    text=tweet.get("text", ""),
                    created_at=tweet.get("created_at", ""),
                    author_username=tweet.get("author_username"),
                    author_name=tweet.get("author_name"),
                    author_verified=tweet.get("author_verified", False),
                    retweet_count=tweet.get("retweet_count", 0),
                    like_count=tweet.get("like_count", 0),
                    reply_count=tweet.get("reply_count", 0),
                    quote_count=tweet.get("quote_count", 0),
                    hashtags=tweet.get("hashtags", []),
                    mentions=tweet.get("mentions", [])
                )
                for tweet in mentions_raw
            ]
        except Exception as e:
            error_msg = f"Error fetching mentions: {str(e)}"
            errors.append(error_msg)
            print(f"⚠️ {error_msg}")
        
        # Calculate analysis summary
        total_user_tweets = len(user_tweets)
        total_mentions = len(mentions)
        
        # Calculate engagement metrics from user's own tweets (likes they received)
        total_likes_received = sum(t.like_count for t in user_tweets)
        total_retweets_received = sum(t.retweet_count for t in user_tweets)
        total_replies_received = sum(t.reply_count for t in user_tweets)
        total_quotes_received = sum(t.quote_count for t in user_tweets)
        total_engagement = total_likes_received + total_retweets_received + total_replies_received + total_quotes_received
        
        avg_likes_per_tweet = total_likes_received / total_user_tweets if total_user_tweets > 0 else 0
        avg_retweets_per_tweet = total_retweets_received / total_user_tweets if total_user_tweets > 0 else 0
        avg_engagement_per_tweet = total_engagement / total_user_tweets if total_user_tweets > 0 else 0
        
        # Calculate engagement rate (engagement / followers)
        engagement_rate = (total_engagement / profile_data.followers_count * 100) if profile_data.followers_count > 0 else 0
        
        # Calculate engagement metrics from mentions
        total_likes_on_mentions = sum(t.like_count for t in mentions)
        total_retweets_on_mentions = sum(t.retweet_count for t in mentions)
        avg_engagement_mentions = (
            (total_likes_on_mentions + total_retweets_on_mentions) / total_mentions
            if total_mentions > 0 else 0
        )
        
        # Extract common hashtags from user's tweets
        all_hashtags = []
        for tweet in user_tweets:
            all_hashtags.extend(tweet.hashtags)
        
        hashtag_counts = Counter(all_hashtags)
        top_hashtags = [{"hashtag": tag, "count": count} for tag, count in hashtag_counts.most_common(10)]
        
        # Find top performing tweets
        top_tweets = sorted(user_tweets, key=lambda x: x.like_count, reverse=True)[:5]
        top_tweets_summary = [
            {
                "tweet_id": t.tweet_id,
                "text": t.text[:100] + "..." if len(t.text) > 100 else t.text,
                "likes": t.like_count,
                "retweets": t.retweet_count
            }
            for t in top_tweets
        ]
        
        analysis_summary = {
            "total_tweets_analyzed": total_user_tweets,
            "total_mentions_fetched": total_mentions,
            "profile_followers": profile_data.followers_count,
            "profile_following": profile_data.following_count,
            "profile_tweets": profile_data.tweets_count,
            "profile_verified": profile_data.verified,
            "total_likes_received": total_likes_received,
            "total_retweets_received": total_retweets_received,
            "total_replies_received": total_replies_received,
            "total_quotes_received": total_quotes_received,
            "total_engagement": total_engagement,
            "avg_likes_per_tweet": round(avg_likes_per_tweet, 2),
            "avg_retweets_per_tweet": round(avg_retweets_per_tweet, 2),
            "avg_engagement_per_tweet": round(avg_engagement_per_tweet, 2),
            "engagement_rate_percent": round(engagement_rate, 2),
            "avg_engagement_mentions": round(avg_engagement_mentions, 2),
            "top_hashtags": top_hashtags,
            "top_performing_tweets": top_tweets_summary,
            "errors": errors if errors else None
        }
        
        return KOLAnalysisResponse(
            username=clean_username,
            profile=profile_data,
            user_tweets=user_tweets,
            mentions=mentions,
            analysis_summary=analysis_summary,
            error="; ".join(errors) if errors else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing KOL: {str(e)}"
        )


# Utility endpoint: get company's Twitter user ID by company UUID
@router.get("/company/{company_id}/twitter-id")
async def get_company_twitter_id(
    company_id: str,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Return the Twitter user ID (and handle) for a company if configured."""
    twitter_account = twitter_crud.get_company_twitter_by_company(db, company_id)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="No Twitter account found for this company")
    return {
        "twitter_id": str(twitter_account.id),
        "company_id": str(twitter_account.company_id),
        "twitter_user_id": twitter_account.twitter_user_id,
        "twitter_handle": twitter_account.twitter_handle
    }


# Utility endpoint: reverse lookup by Twitter numeric user ID
@router.get("/twitter-user/{twitter_user_id}")
async def get_company_by_twitter_user_id(
    twitter_user_id: str,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Return the company Twitter record by Twitter numeric user ID."""
    twitter_account = twitter_crud.get_company_twitter_by_twitter_user_id(db, twitter_user_id)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="No company found for this Twitter user ID")
    return {
        "company_id": str(twitter_account.company_id),
        "twitter_id": str(twitter_account.id),
        "twitter_user_id": twitter_account.twitter_user_id,
        "twitter_handle": twitter_account.twitter_handle
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
