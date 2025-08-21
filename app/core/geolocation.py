"""
Geolocation utilities for determining user regions from IP addresses.
"""

import requests
import logging
from typing import Optional, Dict, Any
from fastapi import Request

logger = logging.getLogger(__name__)

class GeolocationService:
    """Service for determining geographic location from IP addresses."""
    
    def __init__(self):
        self.free_apis = [
            "https://ipapi.co/{ip}/json/",
            "https://ipinfo.io/{ip}/json"
        ]
        self.fallback_data = {
            "country": "Unknown",
            "region": "Unknown", 
            "city": "Unknown"
        }
    
    def get_location_from_ip(self, ip_address: str) -> Dict[str, str]:
        """Get location information from an IP address."""
        if not ip_address or ip_address in ['127.0.0.1', 'localhost', '::1']:
            return self.fallback_data.copy()
        
        for api_url in self.free_apis:
            try:
                response = requests.get(api_url.format(ip=ip_address), timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_location_data(data)
            except Exception as e:
                logger.warning(f"Failed to get location from {api_url}: {e}")
                continue
        
        return self.fallback_data.copy()
    
    def _parse_location_data(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Parse location data from various API responses."""
        location = {
            "country": "Unknown",
            "region": "Unknown",
            "city": "Unknown"
        }
        
        try:
            if "country_code" in data:
                location["country"] = data.get("country_code", "Unknown")
                location["region"] = data.get("region", "Unknown")
                location["city"] = data.get("city", "Unknown")
            elif "country" in data:
                location["country"] = data.get("country", "Unknown")
                location["region"] = data.get("region", "Unknown")
                location["city"] = data.get("city", "Unknown")
        except Exception as e:
            logger.error(f"Error parsing location data: {e}")
            return self.fallback_data.copy()
        
        return location
    
    def get_client_ip(self, request: Request) -> str:
        """Extract the client's real IP address from the request."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "Unknown"

geolocation_service = GeolocationService()
