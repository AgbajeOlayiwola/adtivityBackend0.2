"""CRUD operations for Twitter data."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from datetime import datetime, date, timedelta
from uuid import UUID
from ..models import (
    CompanyTwitter, TwitterTweet, TwitterFollower, 
    HashtagMention, TwitterAnalytics, MentionNotification
)
from ..schemas import (
    CompanyTwitterCreate, CompanyTwitterUpdate,
    HashtagMentionResponse
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
    
    def get_company_twitter(self, db: Session, twitter_id: UUID) -> Optional[CompanyTwitter]:
        """Get company Twitter account by ID."""
        return db.query(CompanyTwitter).filter(CompanyTwitter.id == twitter_id).first()
    
    def get_company_twitter_by_handle(self, db: Session, handle: str) -> Optional[CompanyTwitter]:
        """Get company Twitter account by handle."""
        return db.query(CompanyTwitter).filter(CompanyTwitter.twitter_handle == handle).first()
    
    def get_company_twitter_by_company(self, db: Session, company_id: str) -> Optional[CompanyTwitter]:
        """Get company Twitter account by company ID."""
        return db.query(CompanyTwitter).filter(CompanyTwitter.company_id == company_id).first()
    
    def update_company_twitter(self, db: Session, twitter_id: UUID, update_data: CompanyTwitterUpdate) -> Optional[CompanyTwitter]:
        """Update company Twitter account."""
        db_twitter = self.get_company_twitter(db, twitter_id)
        if db_twitter:
            for field, value in update_data.dict(exclude_unset=True).items():
                setattr(db_twitter, field, value)
            db_twitter.last_updated = datetime.utcnow()
            db.commit()
            db.refresh(db_twitter)
        return db_twitter
    
    def delete_company_twitter(self, db: Session, twitter_id: UUID) -> Optional[str]:
        """Delete company Twitter account and return company_id."""
        db_twitter = self.get_company_twitter(db, twitter_id)
        if db_twitter:
            company_id = db_twitter.company_id
            db.delete(db_twitter)
            db.commit()
            return company_id
        return None
    
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
    
    def get_company_tweets(self, db: Session, company_twitter_id: UUID, limit: int = 100) -> List[TwitterTweet]:
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
    
    def get_follower_by_id(self, db: Session, follower_id: str, company_twitter_id: UUID) -> Optional[TwitterFollower]:
        """Get follower by Twitter ID and company."""
        return db.query(TwitterFollower)\
            .filter(and_(
                TwitterFollower.follower_id == follower_id,
                TwitterFollower.company_twitter_id == company_twitter_id
            ))\
            .first()
    
    def get_company_followers(self, db: Session, company_twitter_id: UUID, limit: int = 1000) -> List[TwitterFollower]:
        """Get followers for a company."""
        return db.query(TwitterFollower)\
            .filter(TwitterFollower.company_twitter_id == company_twitter_id)\
            .order_by(desc(TwitterFollower.collected_at))\
            .limit(limit)\
            .all()
    
    def update_follower_metrics(self, db: Session, follower_id: str, company_twitter_id: UUID, metrics: Dict[str, Any]) -> Optional[TwitterFollower]:
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
    
    # Hashtag Mention operations
    def create_hashtag_mention(self, db: Session, mention_data: Dict[str, Any]) -> HashtagMention:
        """Create a new hashtag mention record."""
        db_mention = HashtagMention(**mention_data)
        db.add(db_mention)
        db.commit()
        db.refresh(db_mention)
        return db_mention
    
    def get_hashtag_mentions(self, db: Session, hashtag: str, company_id: str, limit: int = 100) -> List[HashtagMention]:
        """Get mentions for a specific hashtag."""
        return db.query(HashtagMention)\
            .filter(and_(
                HashtagMention.hashtag == hashtag,
                HashtagMention.company_id == company_id
            ))\
            .order_by(desc(HashtagMention.created_at))\
            .limit(limit)\
            .all()
    
    def search_hashtag_mentions(self, db: Session, hashtag: str, company_id: str, limit: int = 100) -> List[HashtagMention]:
        """Search for hashtag mentions for a company."""
        return db.query(HashtagMention)\
            .filter(and_(
                HashtagMention.company_id == company_id,
                HashtagMention.hashtag.ilike(f"%{hashtag}%")
            ))\
            .order_by(desc(HashtagMention.created_at))\
            .limit(limit)\
            .all()
    
    def get_company_mentions(self, db: Session, company_twitter_id: UUID, limit: int = 100) -> List[TwitterTweet]:
        """Get all mentions of a company (tweets that mention the company's handle)."""
        return db.query(TwitterTweet)\
            .filter(TwitterTweet.mentions.isnot(None))\
            .filter(TwitterTweet.company_twitter_id == company_twitter_id)\
            .order_by(desc(TwitterTweet.created_at))\
            .limit(limit)\
            .all()
    
    def get_mentions_by_date_range(self, db: Session, company_twitter_id: UUID, start_date: datetime, end_date: datetime) -> List[TwitterTweet]:
        """Get mentions of a company within a date range."""
        return db.query(TwitterTweet)\
            .filter(TwitterTweet.mentions.isnot(None))\
            .filter(TwitterTweet.company_twitter_id == company_twitter_id)\
            .filter(TwitterTweet.created_at >= start_date)\
            .filter(TwitterTweet.created_at <= end_date)\
            .order_by(desc(TwitterTweet.created_at))\
            .all()
    
    def get_mention_analytics(self, db: Session, company_twitter_id: UUID, start_date: date, end_date: date) -> Dict[str, Any]:
        """Get mention analytics for a date range."""
        mentions = self.get_mentions_by_date_range(
            db, company_twitter_id, 
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time())
        )
        
        total_mentions = len(mentions)
        total_likes = sum(mention.like_count for mention in mentions)
        total_retweets = sum(mention.retweet_count for mention in mentions)
        total_replies = sum(mention.reply_count for mention in mentions)
        
        # Group by date
        mentions_by_date = {}
        for mention in mentions:
            date_key = mention.created_at.date()
            if date_key not in mentions_by_date:
                mentions_by_date[date_key] = {
                    'count': 0,
                    'likes': 0,
                    'retweets': 0,
                    'replies': 0
                }
            mentions_by_date[date_key]['count'] += 1
            mentions_by_date[date_key]['likes'] += mention.like_count
            mentions_by_date[date_key]['retweets'] += mention.retweet_count
            mentions_by_date[date_key]['replies'] += mention.reply_count
        
        return {
            'total_mentions': total_mentions,
            'total_likes': total_likes,
            'total_retweets': total_retweets,
            'total_replies': total_replies,
            'mentions_by_date': mentions_by_date,
            'date_range': {
                'start_date': start_date,
                'end_date': end_date
            }
        }
    
    def create_mention_notification(self, db: Session, mention_data: Dict[str, Any]) -> bool:
        """Create a mention notification record (placeholder for future notification system)."""
        # This is a placeholder for future notification system
        # For now, we'll just return True to indicate the mention was processed
        return True
    
    # Mention Notification operations
    def create_mention_notification_prefs(self, db: Session, notification_data: Dict[str, Any]) -> 'MentionNotification':
        """Create mention notification preferences for a company."""
        from ..models import MentionNotification
        db_notification = MentionNotification(**notification_data)
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)
        return db_notification
    
    def get_mention_notification_prefs(self, db: Session, company_id: str) -> Optional['MentionNotification']:
        """Get mention notification preferences for a company."""
        from ..models import MentionNotification
        return db.query(MentionNotification).filter(MentionNotification.company_id == company_id).first()
    
    def update_mention_notification_prefs(self, db: Session, company_id: str, update_data: Dict[str, Any]) -> Optional['MentionNotification']:
        """Update mention notification preferences for a company."""
        from ..models import MentionNotification
        db_notification = self.get_mention_notification_prefs(db, company_id)
        if db_notification:
            for field, value in update_data.items():
                if hasattr(db_notification, field):
                    setattr(db_notification, field, value)
            db_notification.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(db_notification)
        return db_notification
    
    def delete_mention_notification_prefs(self, db: Session, company_id: str) -> bool:
        """Delete mention notification preferences for a company."""
        from ..models import MentionNotification
        db_notification = self.get_mention_notification_prefs(db, company_id)
        if db_notification:
            db.delete(db_notification)
            db.commit()
            return True
        return False
    
    # Twitter Analytics operations
    def create_analytics(self, db: Session, analytics_data: Dict[str, Any]) -> TwitterAnalytics:
        """Create a new Twitter analytics record."""
        db_analytics = TwitterAnalytics(**analytics_data)
        db.add(db_analytics)
        db.commit()
        db.refresh(db_analytics)
        return db_analytics
    
    def get_analytics_by_date(self, db: Session, company_twitter_id: UUID, target_date: date) -> Optional[TwitterAnalytics]:
        """Get analytics for a specific date."""
        return db.query(TwitterAnalytics)\
            .filter(and_(
                TwitterAnalytics.company_twitter_id == company_twitter_id,
                TwitterAnalytics.date == target_date
            ))\
            .first()
    
    def get_analytics_range(self, db: Session, company_twitter_id: UUID, start_date: date, end_date: date) -> List[TwitterAnalytics]:
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
