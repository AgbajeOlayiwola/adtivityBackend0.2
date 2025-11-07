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
        self.request_count = 0
        self.daily_request_limit = 300  # Conservative limit
        self.daily_reset_time = 0
    
    def _get_oauth_session(self) -> OAuth1Session:
        """Create OAuth 1.0a session for user context authentication."""
        return OAuth1Session(
            client_key=self.api_key,
            client_secret=self.api_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret
        )
    
    async def _check_rate_limits(self) -> bool:
        """Check if we can make a request based on rate limits."""
        current_time = time.time()
        
        # Check daily limit
        if current_time > self.daily_reset_time:
            self.request_count = 0
            self.daily_reset_time = current_time + 86400  # 24 hours
        
        if self.request_count >= self.daily_request_limit:
            print(f"⚠️ Daily request limit reached ({self.daily_request_limit}). Reset in {self.daily_reset_time - current_time:.0f} seconds.")
            return False
        
        # Check per-request rate limit
        if current_time < self.rate_limit_reset:
            wait_time = self.rate_limit_reset - current_time
            print(f"⏳ Rate limit active. Wait {wait_time:.0f} seconds before next request.")
            return False
        
        # Rate limiting: wait at least 10 seconds between requests
        if current_time - self.last_request_time < 10:
            await asyncio.sleep(10 - (current_time - self.last_request_time))
        
        return True
    
    async def _handle_rate_limit_response(self, response: httpx.Response) -> None:
        """Handle rate limit response and update internal state."""
        if response.status_code == 429:
            rate_limit_reset = response.headers.get('x-rate-limit-reset')
            if rate_limit_reset:
                self.rate_limit_reset = int(rate_limit_reset)
                print(f"⚠️ Rate limit exceeded. Reset at: {datetime.fromtimestamp(self.rate_limit_reset)}")
            else:
                # Fallback: wait 15 minutes
                self.rate_limit_reset = time.time() + 900
                print("⚠️ Rate limit exceeded. Waiting 15 minutes.")
            
            # Also check for daily limits
            remaining = response.headers.get('x-rate-limit-remaining')
            if remaining and int(remaining) < 10:
                print(f"⚠️ Low rate limit remaining: {remaining}")
    
    async def _make_request_with_retry(self, url: str, params: dict = None, max_retries: int = 3) -> Optional[httpx.Response]:
        """Make HTTP request with retry logic and rate limiting."""
        for attempt in range(max_retries):
            if not await self._check_rate_limits():
                return None
            
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(url, headers=self.headers, params=params)
                    self.last_request_time = time.time()
                    self.request_count += 1
                    
                    if response.status_code == 200:
                        return response
                    elif response.status_code == 429:
                        await self._handle_rate_limit_response(response)
                        if attempt < max_retries - 1:
                            wait_time = min(60 * (2 ** attempt), 300)  # Exponential backoff, max 5 minutes
                            print(f"⏳ Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ Request failed with status {response.status_code}: {response.text}")
                        return response
                        
            except httpx.TimeoutException:
                print(f"⏰ Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                continue
            except Exception as e:
                print(f"❌ Request error: {str(e)} (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                continue
        
        return None
    
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
            
            # Make request with retry logic
            response = await self._make_request_with_retry(
                f"{self.base_url}/users/by/username/{username}",
                params={
                    "user.fields": "id,username,name,description,profile_image_url,verified,public_metrics,created_at"
                }
            )
            
            if not response:
                print(f"⚠️ Could not fetch profile for @{username} (rate limited or failed)")
                return None
            
            if response.status_code == 200:
                data = response.json()
                user_data = data.get("data", {})
                
                # Extract metrics
                metrics = user_data.get("public_metrics", {})
                
                # Handle cases where Twitter API returns incomplete data
                profile_data = TwitterProfileData(
                    id=user_data.get("id") or None,
                    username=user_data.get("username") or None,
                    name=user_data.get("name") or None,
                    description=user_data.get("description") or None,
                    profile_image_url=user_data.get("profile_image_url") or None,
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
            if user_data and user_data.id and user_data.username:
                # Convert TwitterProfileData to dict format for autocomplete
                user_dict = {
                    "id": user_data.id,
                    "username": user_data.username,
                    "name": user_data.name or "",
                    "description": user_data.description or "",
                    "profile_image_url": user_data.profile_image_url or "",
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
            # Twitter API v2 requires max_results between 5 and 100
            if max_results < 5:
                max_results = 5
            elif max_results > 100:
                max_results = 100
            # Make request with retry logic
            response = await self._make_request_with_retry(
                f"{self.base_url}/users/{user_id}/tweets",
                params={
                    "max_results": max_results,
                    "tweet.fields": "id,text,created_at,public_metrics,entities"
                }
            )
            
            if not response:
                print(f"⚠️ Could not fetch tweets for user {user_id} (rate limited or failed)")
                return []
            
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
            else:
                print(f"❌ Error fetching tweets: {response.status_code} - {response.text[:100]}")
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
    
    async def get_user_liked_tweets(self, user_id: str, max_results: int = 100) -> List[Dict]:
        """Get tweets liked by a user.
        
        Note: This endpoint may require OAuth 1.0a User Context authentication depending on API access level.
        For privacy reasons, many users' liked tweets may not be accessible via public API.
        """
        try:
            # Twitter API v2 requires max_results between 5 and 100
            if max_results < 5:
                max_results = 5
            elif max_results > 100:
                max_results = 100
            
            # Make request with retry logic (uses Bearer token)
            # Note: Liked tweets endpoint may require OAuth 1.0a User Context for some users
            # This is a limitation of Twitter API - we'll attempt with Bearer token first
            response = await self._make_request_with_retry(
                f"{self.base_url}/users/{user_id}/liked_tweets",
                params={
                    "max_results": max_results,
                    "tweet.fields": "id,text,created_at,public_metrics,author_id,entities",
                    "expansions": "author_id",
                    "user.fields": "id,username,name,verified,profile_image_url"
                }
            )
            
            if not response:
                print(f"⚠️ Could not fetch liked tweets for user {user_id} (rate limited or failed)")
                return []
            
            if response.status_code == 200:
                data = response.json()
                tweets = data.get("data", [])
                users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
                
                results = []
                for tweet in tweets:
                    author = users.get(tweet.get("author_id"), {})
                    metrics = tweet.get("public_metrics", {})
                    
                    # Extract hashtags and mentions from entities
                    entities = tweet.get("entities", {})
                    hashtags = []
                    mentions = []
                    
                    if "hashtags" in entities:
                        hashtags = [tag.get("tag") for tag in entities["hashtags"]]
                    if "mentions" in entities:
                        mentions = [mention.get("username") for mention in entities["mentions"]]
                    
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
                        "reply_count": metrics.get("reply_count", 0),
                        "quote_count": metrics.get("quote_count", 0),
                        "hashtags": hashtags,
                        "mentions": mentions
                    }
                    results.append(tweet_result)
                
                return results
            elif response.status_code == 401:
                print(f"⚠️ Twitter API: Unauthorized - Liked tweets may require OAuth 1.0a User Context or may be private")
                return []
            elif response.status_code == 403:
                print(f"⚠️ Twitter API: Forbidden - Liked tweets may not be accessible (privacy settings or API limitations)")
                return []
            elif response.status_code == 404:
                print(f"⚠️ Twitter API: User {user_id} not found or liked tweets not accessible")
                return []
            else:
                print(f"⚠️ Error fetching liked tweets: {response.status_code} - {response.text[:100]}")
                return []
                
        except Exception as e:
            print(f"⚠️ Error fetching liked tweets for user {user_id}: {e}")
            return []
    
    async def get_user_mentions(self, username: str, max_results: int = 100) -> List[Dict]:
        """Get tweets that mention a user (search for @username)."""
        try:
            # Clean username (remove @ if present)
            clean_username = username.lstrip("@").strip()
            
            # Twitter API v2 requires max_results between 10 and 100 for search
            if max_results < 10:
                max_results = 10
            elif max_results > 100:
                max_results = 100
            
            # Make request with retry logic
            response = await self._make_request_with_retry(
                f"{self.base_url}/tweets/search/recent",
                params={
                    "query": f"@{clean_username}",
                    "max_results": max_results,
                    "tweet.fields": "id,text,created_at,public_metrics,author_id,entities,in_reply_to_user_id",
                    "user.fields": "id,username,name,verified,profile_image_url",
                    "expansions": "author_id"
                }
            )
            
            if not response:
                print(f"⚠️ Could not fetch mentions for @{clean_username} (rate limited or failed)")
                return []
            
            if response.status_code == 200:
                data = response.json()
                tweets = data.get("data", [])
                users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
                
                results = []
                for tweet in tweets:
                    author = users.get(tweet.get("author_id"), {})
                    metrics = tweet.get("public_metrics", {})
                    
                    # Extract hashtags and mentions
                    entities = tweet.get("entities", {})
                    hashtags = []
                    mentions = []
                    
                    if "hashtags" in entities:
                        hashtags = [tag.get("tag") for tag in entities["hashtags"]]
                    if "mentions" in entities:
                        mentions = [mention.get("username") for mention in entities["mentions"]]
                    
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
                        "reply_count": metrics.get("reply_count", 0),
                        "quote_count": metrics.get("quote_count", 0),
                        "hashtags": hashtags,
                        "mentions": mentions
                    }
                    results.append(tweet_result)
                
                return results
            elif response.status_code == 401:
                print(f"❌ Twitter API: Unauthorized - Check your Bearer Token for mentions")
                return []
            elif response.status_code == 403:
                print(f"❌ Twitter API: Forbidden - Check your API permissions for mentions")
                return []
            elif response.status_code == 429:
                print(f"⚠️ Twitter API: Rate limit exceeded for mentions")
                await self._handle_rate_limit_response(response)
                return []
            else:
                print(f"❌ Twitter API Error {response.status_code} for mentions: {response.text[:100]}")
                return []
                
        except Exception as e:
            print(f"Error fetching mentions for @{username}: {e}")
            return []


# Global service instance
twitter_service = TwitterService()