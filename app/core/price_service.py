"""Price Service - Fetches real-time cryptocurrency prices from CoinGecko API."""

import asyncio
import httpx
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone, timedelta
import json

logger = logging.getLogger(__name__)


class PriceService:
    """Service for fetching real-time cryptocurrency prices."""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self.cache = {}
        self.cache_duration = 300  # 5 minutes cache
        self.rate_limit_delay = 1.0  # 1 second between requests
        
        # CoinGecko coin IDs mapping
        self.coin_ids = {
            'ethereum': 'ethereum',
            'eth': 'ethereum',
            'solana': 'solana',
            'sol': 'solana',
            'polygon': 'matic-network',
            'matic': 'matic-network',
            'bsc': 'binancecoin',
            'bnb': 'binancecoin',
            'arbitrum': 'ethereum',  # Uses ETH
            'optimism': 'ethereum',  # Uses ETH
            'base': 'ethereum',      # Uses ETH
            'avalanche': 'avalanche-2',
            'avax': 'avalanche-2'
        }
        
        # Network to coin mapping
        self.network_coins = {
            'ethereum': 'ethereum',
            'polygon': 'matic-network',
            'bsc': 'binancecoin',
            'arbitrum': 'ethereum',
            'optimism': 'ethereum',
            'base': 'ethereum',
            'avalanche': 'avalanche-2',
            'solana': 'solana'
        }
    
    async def get_price(self, coin_id: str) -> Optional[float]:
        """Get current price for a specific coin."""
        try:
            # Check cache first
            if self._is_cached(coin_id):
                return self.cache[coin_id]['price']
            
            # Fetch from API
            price = await self._fetch_price_from_api(coin_id)
            if price:
                self._cache_price(coin_id, price)
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching price for {coin_id}: {e}")
            return None
    
    async def get_eth_price(self) -> float:
        """Get current ETH price."""
        price = await self.get_price('ethereum')
        return price if price else 2000.0  # Fallback price
    
    async def get_sol_price(self) -> float:
        """Get current SOL price."""
        price = await self.get_price('solana')
        return price if price else 100.0  # Fallback price
    
    async def get_token_price(self, network: str) -> float:
        """Get current token price for a specific network."""
        coin_id = self.network_coins.get(network, 'ethereum')
        price = await self.get_price(coin_id)
        return price if price else self._get_fallback_price(network)
    
    async def get_multiple_prices(self, coin_ids: list[str]) -> Dict[str, float]:
        """Get prices for multiple coins in a single API call."""
        try:
            # Check which coins need fresh data
            fresh_coins = []
            cached_prices = {}
            
            for coin_id in coin_ids:
                if self._is_cached(coin_id):
                    cached_prices[coin_id] = self.cache[coin_id]['price']
                else:
                    fresh_coins.append(coin_id)
            
            # Fetch fresh prices if needed
            if fresh_coins:
                fresh_prices = await self._fetch_multiple_prices_from_api(fresh_coins)
                for coin_id, price in fresh_prices.items():
                    if price:
                        self._cache_price(coin_id, price)
                        cached_prices[coin_id] = price
            
            return cached_prices
            
        except Exception as e:
            logger.error(f"Error fetching multiple prices: {e}")
            return {}
    
    async def _fetch_price_from_api(self, coin_id: str) -> Optional[float]:
        """Fetch price from CoinGecko API."""
        try:
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                if coin_id in data and 'usd' in data[coin_id]:
                    return float(data[coin_id]['usd'])
                
                return None
                
        except Exception as e:
            logger.error(f"API error fetching price for {coin_id}: {e}")
            return None
    
    async def _fetch_multiple_prices_from_api(self, coin_ids: list[str]) -> Dict[str, float]:
        """Fetch multiple prices from CoinGecko API."""
        try:
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': ','.join(coin_ids),
                'vs_currencies': 'usd'
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                prices = {}
                
                for coin_id in coin_ids:
                    if coin_id in data and 'usd' in data[coin_id]:
                        prices[coin_id] = float(data[coin_id]['usd'])
                
                return prices
                
        except Exception as e:
            logger.error(f"API error fetching multiple prices: {e}")
            return {}
    
    def _is_cached(self, coin_id: str) -> bool:
        """Check if price is cached and not expired."""
        if coin_id not in self.cache:
            return False
        
        cache_time = self.cache[coin_id]['timestamp']
        return datetime.now(timezone.utc) - cache_time < timedelta(seconds=self.cache_duration)
    
    def _cache_price(self, coin_id: str, price: float):
        """Cache a price with timestamp."""
        self.cache[coin_id] = {
            'price': price,
            'timestamp': datetime.now(timezone.utc)
        }
    
    def _get_fallback_price(self, network: str) -> float:
        """Get fallback price for a network."""
        fallback_prices = {
            'ethereum': 2000.0,
            'polygon': 0.8,
            'bsc': 300.0,
            'arbitrum': 2000.0,
            'optimism': 2000.0,
            'base': 2000.0,
            'avalanche': 25.0,
            'solana': 100.0
        }
        return fallback_prices.get(network, 2000.0)
    
    async def get_price_history(self, coin_id: str, days: int = 7) -> Optional[list]:
        """Get price history for a coin."""
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                if 'prices' in data:
                    return data['prices']
                
                return None
                
        except Exception as e:
            logger.error(f"Error fetching price history for {coin_id}: {e}")
            return None
    
    def get_cached_prices(self) -> Dict[str, Any]:
        """Get all cached prices with timestamps."""
        return {
            coin_id: {
                'price': data['price'],
                'timestamp': data['timestamp'].isoformat(),
                'age_seconds': (datetime.now(timezone.utc) - data['timestamp']).total_seconds()
            }
            for coin_id, data in self.cache.items()
        }
    
    def clear_cache(self):
        """Clear all cached prices."""
        self.cache.clear()
        logger.info("Price cache cleared")


# Global price service instance
price_service = PriceService()
