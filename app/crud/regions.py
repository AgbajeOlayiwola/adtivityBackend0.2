"""
Region analytics CRUD operations.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Event, Web3Event

logger = logging.getLogger(__name__)


def get_region_analytics(
    db: Session,
    company_ids: List[str],
    start: datetime,
    end: datetime,
    platform: str = "both"
) -> Dict[str, Any]:
    """
    Get region-based analytics for specified companies and time period.
    """
    # Base query for events
    events_query = db.query(
        Event.country,
        Event.region,
        Event.city,
        func.count(Event.id).label('event_count'),
        func.count(func.distinct(Event.user_id)).label('unique_users')
    ).filter(
        Event.client_company_id.in_(company_ids),
        Event.timestamp >= start,
        Event.timestamp <= end
    )
    
    # Base query for Web3 events
    web3_query = db.query(
        Web3Event.country,
        Web3Event.region,
        Web3Event.city,
        func.count(Web3Event.id).label('event_count'),
        func.count(func.distinct(Web3Event.user_id)).label('unique_users')
    ).filter(
        Web3Event.client_company_id.in_(company_ids),
        Web3Event.timestamp >= end,
        Web3Event.timestamp <= end
    )
    
    # Apply platform filter
    if platform == "web2":
        web3_query = web3_query.filter(False)  # No Web3 events
    elif platform == "web3":
        events_query = events_query.filter(False)  # No Web2 events
    
    # Combine and aggregate results
    all_regions = []
    
    # Process Web2 events
    for result in events_query.group_by(Event.country, Event.region, Event.city).all():
        if result.country and result.country != "Unknown":
            all_regions.append({
                'country': result.country,
                'region': result.region or "Unknown",
                'city': result.city or "Unknown",
                'event_count': result.event_count,
                'user_count': result.unique_users
            })
    
    # Process Web3 events
    for result in web3_query.group_by(Web3Event.country, Web3Event.region, Web3Event.city).all():
        if result.country and result.country != "Unknown":
            all_regions.append({
                'country': result.country,
                'region': result.region or "Unknown",
                'city': result.city or "Unknown",
                'event_count': result.event_count,
                'user_count': result.unique_users
            })
    
    # Aggregate by region
    region_data = {}
    for region in all_regions:
        key = f"{region['country']}_{region['region']}_{region['city']}"
        if key not in region_data:
            region_data[key] = {
                'country': region['country'],
                'region': region['region'],
                'city': region['city'],
                'event_count': 0,
                'user_count': 0
            }
        region_data[key]['event_count'] += region['event_count']
        region_data[key]['user_count'] += region['user_count']
    
    # Convert to list and sort by user count
    regions = list(region_data.values())
    regions.sort(key=lambda x: x['user_count'], reverse=True)
    
    # Calculate totals
    total_users = sum(r['user_count'] for r in regions)
    total_events = sum(r['event_count'] for r in regions)
    
    # Get top countries and cities
    country_counts = {}
    city_counts = {}
    for region in regions:
        country_counts[region['country']] = country_counts.get(region['country'], 0) + region['user_count']
        city_counts[f"{region['city']}, {region['country']}"] = city_counts.get(f"{region['city']}, {region['country']}", 0) + region['user_count']
    
    top_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    top_cities = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    
    # Convert to response format
    region_objects = []
    for region in regions:
        region_objects.append({
            'country': region['country'],
            'region': region['region'],
            'city': region['city'],
            'user_count': region['user_count'],
            'event_count': region['event_count'],
            'conversion_rate': None,  # Could be calculated from other metrics
            'revenue_usd': None       # Could be calculated from other metrics
        })
    
    return {
        'regions': region_objects,
        'total_users': total_users,
        'total_events': total_events,
        'top_countries': [country[0] for country in top_countries],
        'top_cities': [city[0] for city in top_cities]
    }


def get_user_locations(
    db: Session,
    company_ids: List[str],
    country: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get location data for users across specified companies.
    """
    # Query for user locations from events
    events_query = db.query(
        Event.user_id,
        Event.country,
        Event.region,
        Event.city,
        Event.ip_address,
        func.max(Event.timestamp).label('last_seen')
    ).filter(
        Event.client_company_id.in_(company_ids),
        Event.user_id.isnot(None)
    )
    
    # Query for user locations from Web3 events
    web3_query = db.query(
        Web3Event.user_id,
        Web3Event.country,
        Web3Event.region,
        Web3Event.city,
        Web3Event.ip_address,
        func.max(Web3Event.timestamp).label('last_seen')
    ).filter(
        Web3Event.client_company_id.in_(company_ids)
    )
    
    # Apply country filter if specified
    if country:
        events_query = events_query.filter(Event.country == country)
        web3_query = web3_query.filter(Web3Event.country == country)
    
    # Get results
    events_results = events_query.group_by(
        Event.user_id, Event.country, Event.region, Event.city, Event.ip_address
    ).all()
    
    web3_results = web3_query.group_by(
        Web3Event.user_id, Web3Event.country, Web3Event.region, Web3Event.city, Web3Event.ip_address
    ).all()
    
    # Combine and deduplicate results
    user_locations = {}
    
    for result in events_results:
        if result.user_id:
            user_locations[result.user_id] = {
                'user_id': result.user_id,
                'country': result.country,
                'city': result.city,
                'ip_address': result.ip_address,
                'last_seen': result.last_seen
            }
    
    for result in web3_results:
        if result.user_id:
            # Update existing user or add new one
            if result.user_id in user_locations:
                # Keep the most recent location data
                if result.last_seen > user_locations[result.user_id]['last_seen']:
                    user_locations[result.user_id].update({
                        'country': result.country,
                        'region': result.region,
                        'city': result.city,
                        'ip_address': result.ip_address,
                        'last_seen': result.last_seen
                    })
            else:
                user_locations[result.user_id] = {
                    'user_id': result.user_id,
                    'country': result.country,
                    'region': result.region,
                    'city': result.city,
                    'ip_address': result.ip_address,
                    'last_seen': result.last_seen
                }
    
    return list(user_locations.values())
