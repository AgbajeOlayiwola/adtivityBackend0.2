"""Twitter API endpoints for managing Twitter integration."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, date, timedelta

from ..core.database import get_db
from ..core.security import get_current_platform_user
from ..core.twitter_service import twitter_service
from ..crud.twitter import twitter_crud
from ..schemas import (
    CompanyTwitterCreate, CompanyTwitterResponse, CompanyTwitterUpdate,
    HashtagCampaignCreate, HashtagCampaignResponse, HashtagCampaignUpdate,
    TwitterTweetResponse, TwitterFollowerResponse, TwitterAnalyticsResponse,
    TwitterSyncRequest, TwitterSyncResponse
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
    
    # Check if Twitter handle already exists
    existing = twitter_crud.get_company_twitter_by_handle(db, twitter_data.twitter_handle)
    if existing:
        raise HTTPException(status_code=400, detail="Twitter handle already exists")
    
    # Create Twitter account
    twitter_account = twitter_crud.create_company_twitter(db, twitter_data)
    return twitter_account


@router.get("/accounts/{twitter_id}", response_model=CompanyTwitterResponse)
async def get_twitter_account(
    twitter_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get Twitter account by ID."""
    twitter_account = twitter_crud.get_company_twitter(db, twitter_id)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    return twitter_account


@router.put("/accounts/{twitter_id}", response_model=CompanyTwitterResponse)
async def update_twitter_account(
    twitter_id: int,
    update_data: CompanyTwitterUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Update Twitter account."""
    twitter_account = twitter_crud.update_company_twitter(db, twitter_id, update_data)
    if not twitter_account:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
    return twitter_account


@router.delete("/accounts/{twitter_id}")
async def delete_twitter_account(
    twitter_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Delete Twitter account."""
    success = twitter_crud.delete_company_twitter(db, twitter_id)
    if not success:
        raise HTTPException(status_code=404, detail="Twitter account not found")
    
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
                        # Calculate sentiment
                        sentiment_score, sentiment_label = twitter_service.calculate_sentiment(tweet.text)
                        
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
                            "mentions": tweet.mentions,
                            "sentiment_score": sentiment_score,
                            "sentiment_label": sentiment_label
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
    twitter_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get tweets for a company Twitter account."""
    tweets = twitter_crud.get_company_tweets(db, twitter_id, limit)
    return tweets


@router.get("/accounts/{twitter_id}/followers", response_model=List[TwitterFollowerResponse])
async def get_company_followers(
    twitter_id: int,
    limit: int = Query(1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get followers for a company Twitter account."""
    followers = twitter_crud.get_company_followers(db, twitter_id, limit)
    return followers


@router.post("/campaigns/", response_model=HashtagCampaignResponse)
async def create_hashtag_campaign(
    campaign_data: HashtagCampaignCreate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Create a new hashtag campaign."""
    campaign = twitter_crud.create_hashtag_campaign(db, campaign_data)
    return campaign


@router.get("/campaigns/", response_model=List[HashtagCampaignResponse])
async def get_company_campaigns(
    company_id: int,
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get hashtag campaigns for a company."""
    campaigns = twitter_crud.get_company_campaigns(db, company_id, active_only)
    return campaigns


@router.get("/campaigns/{campaign_id}", response_model=HashtagCampaignResponse)
async def get_hashtag_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get hashtag campaign by ID."""
    campaign = twitter_crud.get_hashtag_campaign(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    return campaign


@router.put("/campaigns/{campaign_id}", response_model=HashtagCampaignResponse)
async def update_hashtag_campaign(
    campaign_id: int,
    update_data: HashtagCampaignUpdate,
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Update hashtag campaign."""
    campaign = twitter_crud.get_hashtag_campaign(db, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Update campaign
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(campaign, field, value)
    
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/analytics/{twitter_id}", response_model=List[TwitterAnalyticsResponse])
async def get_twitter_analytics(
    twitter_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Get Twitter analytics for a date range."""
    analytics = twitter_crud.get_analytics_range(db, twitter_id, start_date, end_date)
    return analytics


@router.post("/search/hashtag")
async def search_hashtag(
    hashtag: str = Query(..., description="Hashtag to search for (with or without #)"),
    max_results: int = Query(100, ge=1, le=100),
    current_user: PlatformUser = Depends(get_current_platform_user)
):
    """Search for tweets with a specific hashtag."""
    results = await twitter_service.search_hashtag(hashtag, max_results)
    return {
        "hashtag": hashtag,
        "results_count": len(results),
        "tweets": results
    }
