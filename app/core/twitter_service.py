"""Twitter API service for fetching and processing Twitter data."""

import httpx
import json
import re
import time
import asyncio
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from requests_oauthlib import OAuth1Session
from .twitter_config import twitter_settings
from ..schemas import TwitterProfileData, TwitterTweetBase, TwitterFollowerBase


class TwitterService:
    """Service for interacting with Twitter API v2."""
    
    def __init__(self):
        self.bearer_token = twitter_settings.TWITTER_BEARER_TOKEN
        self.api_key = twitter_settings.TWITTER_API_KEY
        self.api_secret = twitter_settings.TWITTER_API_SECRET
        self.access_token = twitter_settings.TWITTER_ACCESS_TOKEN
        self.access_token_secret = twitter_settings.TWITTER_ACCESS_TOKEN_SECRET
        self.base_url = twitter_settings.TWITTER_API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json"
        }
        
        # Rate limiting and caching
        self.user_cache = {}  # Simple in-memory cache
        self.rate_limit_reset = 0
        self.last_request_time = 0
    
    def _get_oauth_session(self) -> OAuth1Session:
        """Create OAuth 1.0a session for user context authentication."""
        return OAuth1Session(
            client_key=self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )
    
    async def get_user_by_username(self, username: str) -> Optional[TwitterProfileData]:
        """Get Twitter user profile by username with rate limiting and caching."""
        try:
            # Check cache first
            cache_key = f"user_{username.lower()}"
            if cache_key in self.user_cache:
                cached_data, cache_time = self.user_cache[cache_key]
                # Cache for 5 minutes
                if time.time() - cache_time < 300:
                    if cached_data is not None:
                        print(f"📦 Using cached data for @{username}")
                    return cached_data
            
            # Check rate limits
            current_time = time.time()
            if current_time < self.rate_limit_reset:
                wait_time = self.rate_limit_reset - current_time
                print(f"⏳ Rate limit active. Wait {wait_time:.0f} seconds before next request.")
                return None
            
            # Rate limiting: wait at least 1 second between requests
            if current_time - self.last_request_time < 1:
                await asyncio.sleep(1)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/users/by/username/{username}",
                    headers=self.headers,
                    params={
                        "user.fields": "id,username,name,description,profile_image_url,verified,public_metrics,created_at"
                    }
                )
                
                self.last_request_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    user_data = data.get("data", {})
                    
                    # Extract metrics
                    metrics = user_data.get("public_metrics", {})
                    
                    profile_data = TwitterProfileData(
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
                    
                    # Cache the result
                    self.user_cache[cache_key] = (profile_data, time.time())
                    print(f"✅ Fetched and cached @{username}")
                    
                    return profile_data
                
                elif response.status_code == 429:
                    # Handle rate limiting
                    rate_limit_reset = response.headers.get('x-rate-limit-reset')
                    if rate_limit_reset:
                        self.rate_limit_reset = int(rate_limit_reset)
                        print(f"⚠️ Rate limit exceeded. Reset at: {datetime.fromtimestamp(self.rate_limit_reset)}")
                    else:
                        # Fallback: wait 15 minutes
                        self.rate_limit_reset = current_time + 900
                        print("⚠️ Rate limit exceeded. Waiting 15 minutes.")
                    return None
                
                elif response.status_code == 404:
                    print(f"❌ User @{username} not found")
                    # Cache the "not found" result to avoid repeated API calls
                    self.user_cache[cache_key] = (None, time.time())
                    return None
                
                else:
                    print(f"❌ Twitter API Error {response.status_code} for @{username}: {response.text[:100]}")
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
            
            # Strategy 1: Try exact username lookup first (works with basic API access)
            # GET /2/users/by/username/:username
            user_data = await self.get_user_by_username(query)
            if user_data:
                # Convert TwitterProfileData to dict format for autocomplete
                user_dict = {
                    "id": user_data.id,
                    "username": user_data.username,
                    "name": user_data.name,
                    "description": user_data.description or "",
                    "profile_image_url": user_data.profile_image_url,
                    "verified": user_data.verified,
                    "followers_count": user_data.followers_count,
                    "following_count": user_data.following_count,
                    "tweets_count": user_data.tweets_count,
                    "created_at": user_data.created_at.isoformat() if user_data.created_at else None,
                    "display_name": f"@{user_data.username} - {user_data.name or ''}",
                    "verified_badge": "✓" if user_data.verified else ""
                }
                return [user_dict]
            
            # Strategy 2: Try multiple username variations for partial matches
            # This simulates autocomplete by trying common variations
            variations = await self._try_username_variations(query, max_results)
            if variations:
                return variations
            
            # Strategy 3: Try search endpoint if available (requires higher API access)
            search_results = await self._try_search_endpoint(query, max_results)
            if search_results:
                return search_results
            
            # No results found
            return []
                
        except Exception as e:
            print(f"Error searching Twitter users for '{query}': {e}")
            return []
    
    async def _try_username_variations(self, query: str, max_results: int) -> List[Dict]:
        """Try common username variations to find multiple users."""
        try:
            # Common variations to try
            variations = [
                query,  # Original
                f"{query}1", f"{query}2", f"{query}3",  # Numbered versions
                f"{query}_", f"_{query}",  # Underscore variations
                f"{query}official", f"{query}real",  # Official accounts
            ]
            
            results = []
            for variation in variations[:max_results]:
                if len(results) >= max_results:
                    break
                    
                user_data = await self.get_user_by_username(variation)
                if user_data:
                    user_dict = {
                        "id": user_data.id,
                        "username": user_data.username,
                        "name": user_data.name,
                        "description": user_data.description or "",
                        "profile_image_url": user_data.profile_image_url,
                        "verified": user_data.verified,
                        "followers_count": user_data.followers_count,
                        "following_count": user_data.following_count,
                        "tweets_count": user_data.tweets_count,
                        "created_at": user_data.created_at.isoformat() if user_data.created_at else None,
                        "display_name": f"@{user_data.username} - {user_data.name or ''}",
                        "verified_badge": "✓" if user_data.verified else ""
                    }
                    results.append(user_dict)
            
            if results:
                print(f"🔍 Found {len(results)} users with variations of '{query}'")
            
            return results
            
        except Exception as e:
            print(f"Error trying username variations: {e}")
            return []
    
    async def _try_search_endpoint(self, query: str, max_results: int) -> List[Dict]:
        """Try the search endpoint for multiple users (requires higher API access)."""
        try:
            # This would use the /users/search endpoint
            # But it requires OAuth 1.0a User Context and higher API access
            print(f"🔍 Search endpoint not available (requires higher API access) for '{query}'")
            return []
            
        except Exception as e:
            print(f"Error with search endpoint: {e}")
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