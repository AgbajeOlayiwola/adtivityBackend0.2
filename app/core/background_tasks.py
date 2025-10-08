"""Background tasks for automatic data syncing."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session

from .database import SessionLocal
from .twitter_service import twitter_service
from ..crud.twitter import twitter_crud
from ..models import CompanyTwitter, TwitterTweet

logger = logging.getLogger(__name__)


class BackgroundTaskService:
    """Service for running background tasks."""
    
    def __init__(self):
        self.is_running = False
        self.sync_interval = 3600  # 1 hour in seconds
    
    async def start_auto_sync(self):
        """Start automatic Twitter data syncing."""
        if self.is_running:
            logger.warning("Auto sync is already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting automatic Twitter sync service")
        
        while self.is_running:
            try:
                await self._sync_all_twitter_accounts()
                logger.info(f"✅ Twitter sync completed. Next sync in {self.sync_interval} seconds")
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"❌ Error in auto sync: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    def stop_auto_sync(self):
        """Stop automatic syncing."""
        self.is_running = False
        logger.info("🛑 Stopping automatic Twitter sync service")
    
    async def _sync_all_twitter_accounts(self):
        """Sync all Twitter accounts in the database."""
        db = SessionLocal()
        try:
            # Get all active Twitter accounts
            twitter_accounts = db.query(CompanyTwitter).all()
            
            if not twitter_accounts:
                logger.info("No Twitter accounts found to sync")
                return
            
            logger.info(f"🔄 Syncing {len(twitter_accounts)} Twitter accounts")
            
            synced_count = 0
            for i, account in enumerate(twitter_accounts):
                try:
                    await self._sync_single_account(db, account)
                    synced_count += 1
                    
                    # Add delay between accounts to respect rate limits
                    if i < len(twitter_accounts) - 1:  # Don't delay after the last account
                        logger.info("⏳ Waiting 5 seconds before next account...")
                        await asyncio.sleep(5)
                        
                except Exception as e:
                    logger.error(f"❌ Error syncing account {account.twitter_handle}: {e}")
                    continue
            
            db.commit()
            logger.info(f"✅ Twitter sync completed: {synced_count}/{len(twitter_accounts)} accounts synced")
            
        except Exception as e:
            logger.error(f"❌ Error in batch sync: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def _sync_single_account(self, db: Session, account: CompanyTwitter):
        """Sync a single Twitter account."""
        logger.info(f"🔄 Syncing @{account.twitter_handle}")
        
        # Update profile data
        profile_data = await twitter_service.get_user_by_username(account.twitter_handle)
        if not profile_data:
            logger.warning(f"⚠️ Could not fetch profile for @{account.twitter_handle} (rate limited or user not found)")
            return
        
        # Update account metrics
        account.followers_count = profile_data.followers_count
        account.following_count = profile_data.following_count
        account.tweets_count = profile_data.tweets_count
        account.profile_image_url = profile_data.profile_image_url
        account.verified = profile_data.verified
        account.last_updated = datetime.utcnow()
        
        # Sync tweets
        if profile_data.id:
            # Check if this is the first sync (no existing tweets)
            existing_tweets_count = db.query(TwitterTweet).filter(
                TwitterTweet.company_twitter_id == account.id
            ).count()
            
            # Determine sync strategy
            if existing_tweets_count == 0:
                # First sync: get more tweets (up to 200)
                max_tweets = 200
                logger.info(f"🔄 First sync for @{account.twitter_handle} - fetching up to {max_tweets} tweets")
            else:
                # Ongoing sync: only recent tweets (last 24 hours)
                max_tweets = 50
                logger.info(f"🔄 Ongoing sync for @{account.twitter_handle} - fetching recent tweets")
            
            tweets = await twitter_service.get_user_tweets(profile_data.id, max_results=max_tweets)
            
            tweets_synced = 0
            for tweet in tweets:
                # For first sync, sync all tweets. For ongoing sync, only recent ones
                # Make RHS timezone-aware to match tweet.created_at (UTC)
                from datetime import timezone
                if existing_tweets_count == 0 or tweet.created_at > (datetime.now(timezone.utc) - timedelta(hours=24)):
                    existing_tweet = twitter_crud.get_tweet_by_id(db, tweet.tweet_id)
                    if not existing_tweet:
                        # Calculate sentiment
                        sentiment_score, sentiment_label = twitter_service.calculate_sentiment(tweet.text)
                        
                        tweet_data = {
                            "tweet_id": tweet.tweet_id,
                            "company_twitter_id": account.id,
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
            
            logger.info(f"✅ @{account.twitter_handle}: {tweets_synced} new tweets synced")
    
    async def sync_account_on_demand(self, company_id: str):
        """Sync a specific account on demand."""
        db = SessionLocal()
        try:
            account = twitter_crud.get_company_twitter_by_company(db, company_id)
            if account:
                await self._sync_single_account(db, account)
                db.commit()
                logger.info(f"✅ On-demand sync completed for @{account.twitter_handle}")
            else:
                logger.warning(f"⚠️ No Twitter account found for company {company_id}")
        except Exception as e:
            logger.error(f"❌ Error in on-demand sync: {e}")
            db.rollback()
        finally:
            db.close()


# Global background task service
background_task_service = BackgroundTaskService()
