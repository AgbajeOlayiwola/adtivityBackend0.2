"""CRUD operations for Twitter data."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime, date, timedelta
from ..models import (
    CompanyTwitter, TwitterTweet, TwitterFollower, 
    HashtagCampaign, HashtagMention, TwitterAnalytics
)
from ..schemas import (
    CompanyTwitterCreate, CompanyTwitterUpdate,
    HashtagCampaignCreate, HashtagCampaignUpdate
)


class TwitterCRUD:
    """CRUD operations for Twitter data."""
    
    # Company Twitter Account operations
    def create_company_twitter(self, db: Session, twitter_data: CompanyTwitterCreate) -> CompanyTwitter:
        """Create a new company Twitter account."""
        db_twitter = CompanyTwitter(**twitter_data.dict())
        db.add(db_twitter)
        db.commit()
        db.refresh(db_twitter)
        return db_twitter
    
    def get_company_twitter(self, db: Session, twitter_id: int) -> Optional[CompanyTwitter]:
        """Get company Twitter account by ID."""
        return db.query(CompanyTwitter).filter(CompanyTwitter.id == twitter_id).first()
    
    def get_company_twitter_by_handle(self, db: Session, handle: str) -> Optional[CompanyTwitter]:
        """Get company Twitter account by handle."""
        return db.query(CompanyTwitter).filter(CompanyTwitter.twitter_handle == handle).first()
    
    def get_company_twitter_by_company(self, db: Session, company_id: int) -> Optional[CompanyTwitter]:
        """Get company Twitter account by company ID."""
        return db.query(CompanyTwitter).filter(CompanyTwitter.company_id == company_id).first()
    
    def update_company_twitter(self, db: Session, twitter_id: int, update_data: CompanyTwitterUpdate) -> Optional[CompanyTwitter]:
        """Update company Twitter account."""
        db_twitter = self.get_company_twitter(db, twitter_id)
        if db_twitter:
            for field, value in update_data.dict(exclude_unset=True).items():
                setattr(db_twitter, field, value)
            db_twitter.last_updated = datetime.utcnow()
            db.commit()
            db.refresh(db_twitter)
        return db_twitter
    
    def delete_company_twitter(self, db: Session, twitter_id: int) -> bool:
        """Delete company Twitter account."""
        db_twitter = self.get_company_twitter(db, twitter_id)
        if db_twitter:
            db.delete(db_twitter)
            db.commit()
            return True
        return False
    
    # Twitter Tweet operations
    def create_tweet(self, db: Session, tweet_data: Dict[str, Any]) -> TwitterTweet:
        """Create a new Twitter tweet record."""
        db_tweet = TwitterTweet(**tweet_data)
        db.add(db_tweet)
        db.commit()
        db.refresh(db_tweet)
        return db_tweet
    
    def get_tweet_by_id(self, db: Session, tweet_id: str) -> Optional[TwitterTweet]:
        """Get tweet by Twitter ID."""
        return db.query(TwitterTweet).filter(TwitterTweet.tweet_id == tweet_id).first()
    
    def get_company_tweets(self, db: Session, company_twitter_id: int, limit: int = 100) -> List[TwitterTweet]:
        """Get recent tweets for a company."""
        return db.query(TwitterTweet)\
            .filter(TwitterTweet.company_twitter_id == company_twitter_id)\
            .order_by(desc(TwitterTweet.created_at))\
            .limit(limit)\
            .all()
    
    def update_tweet_metrics(self, db: Session, tweet_id: str, metrics: Dict[str, Any]) -> Optional[TwitterTweet]:
        """Update tweet engagement metrics."""
        db_tweet = self.get_tweet_by_id(db, tweet_id)
        if db_tweet:
            for field, value in metrics.items():
                if hasattr(db_tweet, field):
                    setattr(db_tweet, field, value)
            db_tweet.collected_at = datetime.utcnow()
            db.commit()
            db.refresh(db_tweet)
        return db_tweet
    
    # Twitter Follower operations
    def create_follower(self, db: Session, follower_data: Dict[str, Any]) -> TwitterFollower:
        """Create a new Twitter follower record."""
        db_follower = TwitterFollower(**follower_data)
        db.add(db_follower)
        db.commit()
        db.refresh(db_follower)
        return db_follower
    
    def get_follower_by_id(self, db: Session, follower_id: str, company_twitter_id: int) -> Optional[TwitterFollower]:
        """Get follower by Twitter ID and company."""
        return db.query(TwitterFollower)\
            .filter(and_(
                TwitterFollower.follower_id == follower_id,
                TwitterFollower.company_twitter_id == company_twitter_id
            ))\
            .first()
    
    def get_company_followers(self, db: Session, company_twitter_id: int, limit: int = 1000) -> List[TwitterFollower]:
        """Get followers for a company."""
        return db.query(TwitterFollower)\
            .filter(TwitterFollower.company_twitter_id == company_twitter_id)\
            .order_by(desc(TwitterFollower.collected_at))\
            .limit(limit)\
            .all()
    
    def update_follower_metrics(self, db: Session, follower_id: str, company_twitter_id: int, metrics: Dict[str, Any]) -> Optional[TwitterFollower]:
        """Update follower metrics."""
        db_follower = self.get_follower_by_id(db, follower_id, company_twitter_id)
        if db_follower:
            for field, value in metrics.items():
                if hasattr(db_follower, field):
                    setattr(db_follower, field, value)
            db_follower.collected_at = datetime.utcnow()
            db.commit()
            db.refresh(db_follower)
        return db_follower
    
    # Hashtag Campaign operations
    def create_hashtag_campaign(self, db: Session, campaign_data: HashtagCampaignCreate) -> HashtagCampaign:
        """Create a new hashtag campaign."""
        db_campaign = HashtagCampaign(**campaign_data.dict())
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)
        return db_campaign
    
    def get_hashtag_campaign(self, db: Session, campaign_id: int) -> Optional[HashtagCampaign]:
        """Get hashtag campaign by ID."""
        return db.query(HashtagCampaign).filter(HashtagCampaign.id == campaign_id).first()
    
    def get_company_campaigns(self, db: Session, company_id: int, active_only: bool = True) -> List[HashtagCampaign]:
        """Get hashtag campaigns for a company."""
        query = db.query(HashtagCampaign).filter(HashtagCampaign.company_id == company_id)
        if active_only:
            query = query.filter(HashtagCampaign.is_active == True)
        return query.order_by(desc(HashtagCampaign.created_at)).all()
    
    def update_campaign_mentions(self, db: Session, campaign_id: int, mention_count: int) -> Optional[HashtagCampaign]:
        """Update campaign mention count."""
        db_campaign = self.get_hashtag_campaign(db, campaign_id)
        if db_campaign:
            db_campaign.current_mentions = mention_count
            db.commit()
            db.refresh(db_campaign)
        return db_campaign
    
    # Hashtag Mention operations
    def create_hashtag_mention(self, db: Session, mention_data: Dict[str, Any]) -> HashtagMention:
        """Create a new hashtag mention record."""
        db_mention = HashtagMention(**mention_data)
        db.add(db_mention)
        db.commit()
        db.refresh(db_mention)
        return db_mention
    
    def get_campaign_mentions(self, db: Session, campaign_id: int, limit: int = 100) -> List[HashtagMention]:
        """Get mentions for a hashtag campaign."""
        return db.query(HashtagMention)\
            .filter(HashtagMention.campaign_id == campaign_id)\
            .order_by(desc(HashtagMention.created_at))\
            .limit(limit)\
            .all()
    
    # Twitter Analytics operations
    def create_analytics(self, db: Session, analytics_data: Dict[str, Any]) -> TwitterAnalytics:
        """Create a new Twitter analytics record."""
        db_analytics = TwitterAnalytics(**analytics_data)
        db.add(db_analytics)
        db.commit()
        db.refresh(db_analytics)
        return db_analytics
    
    def get_analytics_by_date(self, db: Session, company_twitter_id: int, target_date: date) -> Optional[TwitterAnalytics]:
        """Get analytics for a specific date."""
        return db.query(TwitterAnalytics)\
            .filter(and_(
                TwitterAnalytics.company_twitter_id == company_twitter_id,
                TwitterAnalytics.date == target_date
            ))\
            .first()
    
    def get_analytics_range(self, db: Session, company_twitter_id: int, start_date: date, end_date: date) -> List[TwitterAnalytics]:
        """Get analytics for a date range."""
        return db.query(TwitterAnalytics)\
            .filter(and_(
                TwitterAnalytics.company_twitter_id == company_twitter_id,
                TwitterAnalytics.date >= start_date,
                TwitterAnalytics.date <= end_date
            ))\
            .order_by(TwitterAnalytics.date)\
            .all()
    
    def update_analytics(self, db: Session, analytics_id: int, update_data: Dict[str, Any]) -> Optional[TwitterAnalytics]:
        """Update analytics record."""
        db_analytics = db.query(TwitterAnalytics).filter(TwitterAnalytics.id == analytics_id).first()
        if db_analytics:
            for field, value in update_data.items():
                if hasattr(db_analytics, field):
                    setattr(db_analytics, field, value)
            db.commit()
            db.refresh(db_analytics)
        return db_analytics


# Global CRUD instance
twitter_crud = TwitterCRUD()
