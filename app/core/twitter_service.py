"""Twitter API service for fetching and processing Twitter data."""

import httpx
import json
import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from .twitter_config import twitter_settings
from ..schemas import TwitterProfileData, TwitterTweetBase, TwitterFollowerBase


class TwitterService:
    """Service for interacting with Twitter API v2."""
    
    def __init__(self):
        self.bearer_token = twitter_settings.TWITTER_BEARER_TOKEN
        self.base_url = twitter_settings.TWITTER_API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
    
    async def get_user_by_username(self, username: str) -> Optional[TwitterProfileData]:
        """Get Twitter user profile by username."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/by/username/{username}",
                    headers=self.headers,
                    params={
                        "user.fields": "id,username,name,description,profile_image_url,verified,public_metrics,created_at"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    user_data = data.get("data", {})
                    
                    # Extract metrics
                    metrics = user_data.get("public_metrics", {})
                    
                    return TwitterProfileData(
                        id=user_data.get("id"),
                        username=user_data.get("username"),
                        name=user_data.get("name"),
                        description=user_data.get("description"),
                        profile_image_url=user_data.get("profile_image_url"),
                        verified=user_data.get("verified", False),
                        followers_count=metrics.get("followers_count", 0),
                        following_count=metrics.get("following_count", 0),
                        tweets_count=metrics.get("tweet_count", 0),
                        created_at=datetime.fromisoformat(user_data.get("created_at").replace("Z", "+00:00")) if user_data.get("created_at") else None
                    )
                
                return None
                
        except Exception as e:
            print(f"Error fetching Twitter user {username}: {e}")
            return None
    
    async def search_users_autocomplete(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search for Twitter users with autocomplete functionality."""
        try:
            # Clean the query (remove @ if present)
            query = query.lstrip("@").strip()
            
            if len(query) < 2:
                return []
            
            async with httpx.AsyncClient() as client:
                # Use the users/search endpoint for autocomplete
                response = await client.get(
                    f"{self.base_url}/users/search",
                    headers=self.headers,
                    params={
                        "query": query,
                        "max_results": max_results,
                        "user.fields": "id,username,name,description,profile_image_url,verified,public_metrics,created_at"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    users = data.get("data", [])
                    
                    user_list = []
                    for user in users:
                        # Extract metrics
                        metrics = user.get("public_metrics", {})
                        
                        user_data = {
                            "id": user.get("id"),
                            "username": user.get("username"),
                            "name": user.get("name"),
                            "description": user.get("description", ""),
                            "profile_image_url": user.get("profile_image_url"),
                            "verified": user.get("verified", False),
                            "followers_count": metrics.get("followers_count", 0),
                            "following_count": metrics.get("following_count", 0),
                            "tweets_count": metrics.get("tweet_count", 0),
                            "created_at": user.get("created_at"),
                            "display_name": f"@{user.get('username')} - {user.get('name', '')}",
                            "verified_badge": "✓" if user.get("verified", False) else ""
                        }
                        
                        user_list.append(user_data)
                    
                    return user_list
                
                return []
                
        except Exception as e:
            print(f"Error searching Twitter users for '{query}': {e}")
            return []
    
    async def validate_twitter_handle(self, handle: str) -> Dict:
        """Validate a Twitter handle and return detailed information."""
        try:
            # Clean the handle
            clean_handle = handle.lstrip("@").strip()
            
            if not clean_handle:
                return {
                    "valid": False,
                    "error": "Handle cannot be empty"
                }
            
            # Check if handle exists
            user_data = await self.get_user_by_username(clean_handle)
            
            if user_data:
                return {
                    "valid": True,
                    "handle": clean_handle,
                    "user_data": user_data,
                    "suggestions": await self.search_users_autocomplete(clean_handle, 5)
                }
            else:
                # Handle doesn't exist, provide suggestions
                suggestions = await self.search_users_autocomplete(clean_handle, 5)
                return {
                    "valid": False,
                    "handle": clean_handle,
                    "error": "Twitter handle not found",
                    "suggestions": suggestions
                }
                
        except Exception as e:
            return {
                "valid": False,
                "error": f"Error validating handle: {str(e)}"
            }
    
    async def get_user_tweets(self, user_id: str, max_results: int = 100) -> List[TwitterTweetBase]:
        """Get recent tweets from a user."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/{user_id}/tweets",
                    headers=self.headers,
                    params={
                        "max_results": max_results,
                        "tweet.fields": "id,text,created_at,public_metrics,entities"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    tweets = data.get("data", [])
                    
                    tweet_list = []
                    for tweet in tweets:
                        # Extract hashtags and mentions
                        entities = tweet.get("entities", {})
                        hashtags = []
                        mentions = []
                        
                        if "hashtags" in entities:
                            hashtags = [tag.get("tag") for tag in entities["hashtags"]]
                        
                        if "mentions" in entities:
                            mentions = [mention.get("username") for mention in entities["mentions"]]
                        
                        # Extract metrics
                        metrics = tweet.get("public_metrics", {})
                        
                        tweet_data = TwitterTweetBase(
                            tweet_id=tweet.get("id"),
                            text=tweet.get("text"),
                            created_at=datetime.fromisoformat(tweet.get("created_at").replace("Z", "+00:00")),
                            retweet_count=metrics.get("retweet_count", 0),
                            like_count=metrics.get("like_count", 0),
                            reply_count=metrics.get("reply_count", 0),
                            quote_count=metrics.get("quote_count", 0)
                        )
                        
                        # Add hashtags and mentions as attributes
                        tweet_data.hashtags = hashtags
                        tweet_data.mentions = mentions
                        
                        tweet_list.append(tweet_data)
                    
                    return tweet_list
                
                return []
                
        except Exception as e:
            print(f"Error fetching tweets for user {user_id}: {e}")
            return []
    
    async def get_user_followers(self, user_id: str, max_results: int = 1000) -> List[TwitterFollowerBase]:
        """Get followers of a user."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/{user_id}/followers",
                    headers=self.headers,
                    params={
                        "max_results": max_results,
                        "user.fields": "id,username,name,description,profile_image_url,verified,public_metrics,created_at"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    followers = data.get("data", [])
                    
                    follower_list = []
                    for follower in followers:
                        # Extract metrics
                        metrics = follower.get("public_metrics", {})
                        
                        follower_data = TwitterFollowerBase(
                            follower_id=follower.get("id"),
                            username=follower.get("username"),
                            display_name=follower.get("name"),
                            verified=follower.get("verified", False),
                            followers_count=metrics.get("followers_count", 0),
                            following_count=metrics.get("following_count", 0),
                            tweets_count=metrics.get("tweet_count", 0)
                        )
                        
                        follower_list.append(follower_data)
                    
                    return follower_list
                
                return []
                
        except Exception as e:
            print(f"Error fetching followers for user {user_id}: {e}")
            return []
    
    async def search_hashtag(self, hashtag: str, max_results: int = 10) -> List[Dict]:
        """Search for tweets with a specific hashtag."""
        try:
            # Remove # if present
            hashtag = hashtag.lstrip("#")
            
            async with httpx.AsyncClient() as client:
                # Use the correct Twitter API v2 search endpoint
                response = await client.get(
                    f"{self.base_url}/tweets/search/recent",
                    headers=self.headers,
                    params={
                        "query": f"#{hashtag}",
                        "max_results": max_results,
                        "tweet.fields": "id,text,created_at,public_metrics,author_id,entities",
                        "user.fields": "id,username,name,verified,profile_image_url",
                        "expansions": "author_id"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    tweets = data.get("data", [])
                    users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
                    
                    results = []
                    for tweet in tweets:
                        author = users.get(tweet.get("author_id"), {})
                        metrics = tweet.get("public_metrics", {})
                        
                        tweet_result = {
                            "tweet_id": tweet.get("id"),
                            "text": tweet.get("text"),
                            "created_at": tweet.get("created_at"),
                            "author_id": tweet.get("author_id"),
                            "author_username": author.get("username"),
                            "author_name": author.get("name"),
                            "author_verified": author.get("verified", False),
                            "retweet_count": metrics.get("retweet_count", 0),
                            "like_count": metrics.get("like_count", 0),
                            "reply_count": metrics.get("reply_count", 0)
                        }
                        
                        results.append(tweet_result)
                    
                    return results
                
                elif response.status_code == 401:
                    print(f"❌ Twitter API: Unauthorized - Check your Bearer Token for hashtag #{hashtag}")
                    return []
                elif response.status_code == 403:
                    print(f"❌ Twitter API: Forbidden - Check your API permissions for hashtag #{hashtag}")
                    return []
                elif response.status_code == 429:
                    print(f"⚠️ Twitter API: Rate limit exceeded for hashtag #{hashtag}")
                    print(f"   Rate limit reset: {response.headers.get('x-rate-limit-reset', 'unknown')}")
                    return []
                else:
                    print(f"❌ Twitter API Error {response.status_code} for hashtag #{hashtag}")
                    return []
                
        except Exception as e:
            print(f"❌ Error searching hashtag #{hashtag}: {e}")
            return []
    
    def extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text."""
        hashtag_pattern = r'#(\w+)'
        return re.findall(hashtag_pattern, text)
    
    def extract_mentions(self, text: str) -> List[str]:
        """Extract mentions from text."""
        mention_pattern = r'@(\w+)'
        return re.findall(mention_pattern, text)
    
    def calculate_sentiment(self, text: str) -> Tuple[float, str]:
        """Calculate sentiment score and label for text."""
        # Simple sentiment analysis based on positive/negative words
        positive_words = {
            'good', 'great', 'excellent', 'amazing', 'awesome', 'love', 'like', 'happy',
            'wonderful', 'fantastic', 'brilliant', 'outstanding', 'perfect', 'best'
        }
        negative_words = {
            'bad', 'terrible', 'awful', 'hate', 'dislike', 'sad', 'horrible',
            'worst', 'disappointing', 'frustrated', 'angry', 'upset', 'poor'
        }
        
        text_lower = text.lower()
        words = text_lower.split()
        
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        total_words = len(words)
        if total_words == 0:
            return 0.0, "neutral"
        
        sentiment_score = (positive_count - negative_count) / total_words
        
        if sentiment_score > 0.1:
            label = "positive"
        elif sentiment_score < -0.1:
            label = "negative"
        else:
            label = "neutral"
        
        return sentiment_score, label


# Global service instance
twitter_service = TwitterService()