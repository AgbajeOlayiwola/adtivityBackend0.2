"""Unified Analytics Service - Integrates aggregation system with existing analytics."""

from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
import uuid

from ..models import (
    Event, Web3Event, ClientCompany, SubscriptionPlan,
    CampaignAnalyticsDaily, CampaignAnalyticsHourly, RawEvent
)
from ..core.aggregation_service import AggregationService


class UnifiedAnalyticsService:
    """Service that provides unified analytics across all data sources based on subscription plans."""
    
    def __init__(self, db: Session):
        self.db = db
        self.aggregation_service = AggregationService(db)
    
    def get_company_subscription_plan(self, company_id: str) -> Optional[SubscriptionPlan]:
        """Get the subscription plan for a company."""
        return self.db.query(SubscriptionPlan).filter(
            SubscriptionPlan.company_id == uuid.UUID(company_id)
        ).first()
    
    def get_default_plan(self) -> SubscriptionPlan:
        """Get default basic plan settings."""
        return SubscriptionPlan(
            plan_name="basic",
            plan_tier=1,
            raw_data_retention_days=0,
            aggregation_frequency="daily",
            max_raw_events_per_month=0,
            max_aggregated_rows_per_month=100000,
            monthly_price_usd=0.0
        )
    
    async def process_sdk_event(self, company_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process SDK events through the aggregation system.
        This replaces the direct Event/Web3Event storage.
        """
        # Get subscription plan
        plan = self.get_company_subscription_plan(company_id)
        if not plan:
            plan = self.get_default_plan()
        
        # Process through aggregation system
        aggregation_result = await self.aggregation_service.process_event(company_id, event_data)
        
        # Also store in original tables for backward compatibility (if needed)
        # This can be removed once all systems are migrated
        if plan.plan_tier >= 3:  # Enterprise - keep raw data
            self._store_legacy_event(company_id, event_data)
        
        return aggregation_result
    
    def _store_legacy_event(self, company_id: str, event_data: Dict[str, Any]):
        """Store event in legacy tables for backward compatibility."""
        try:
            # Determine if it's a Web3 event
            is_web3_event = (
                event_data.get("type") == "TX" or
                event_data.get("wallet_address") or
                event_data.get("chain_id") or
                event_data.get("properties", {}).get("wallet_address") or
                event_data.get("properties", {}).get("chain_id")
            )
            
            if is_web3_event:
                # Store as Web3Event
                web3_event = Web3Event(
                    client_company_id=uuid.UUID(company_id),
                    user_id=event_data.get("user_id", ""),
                    event_name=event_data.get("event_name", "unknown"),
                    wallet_address=event_data.get("wallet_address", ""),
                    chain_id=event_data.get("chain_id", ""),
                    transaction_hash=event_data.get("properties", {}).get("transaction_hash"),
                    contract_address=event_data.get("properties", {}).get("contract_address"),
                    properties=event_data.get("properties", {}),
                    timestamp=event_data.get("timestamp", datetime.utcnow()),
                    country=event_data.get("country"),
                    region=event_data.get("region"),
                    city=event_data.get("city"),
                    ip_address=event_data.get("ip_address")
                )
                self.db.add(web3_event)
            else:
                # Store as regular Event
                event = Event(
                    client_company_id=uuid.UUID(company_id),
                    event_name=event_data.get("event_name", "unknown"),
                    event_type=event_data.get("type", "unknown"),
                    user_id=event_data.get("user_id"),
                    anonymous_id=event_data.get("anonymous_id"),
                    session_id=event_data.get("session_id"),
                    properties=event_data.get("properties", {}),
                    timestamp=event_data.get("timestamp", datetime.utcnow()),
                    country=event_data.get("country"),
                    region=event_data.get("region"),
                    city=event_data.get("city"),
                    ip_address=event_data.get("ip_address")
                )
                self.db.add(event)
            
            self.db.commit()
        except Exception as e:
            print(f"Error storing legacy event: {e}")
            self.db.rollback()
    
    def get_analytics_data(
        self, 
        company_ids: List[str], 
        start_date: datetime, 
        end_date: datetime,
        data_type: str = "sessions"  # sessions, events, regions, etc.
    ) -> Dict[str, Any]:
        """
        Get analytics data based on subscription plans.
        Routes queries to appropriate data sources.
        """
        results = {}
        
        for company_id in company_ids:
            plan = self.get_company_subscription_plan(company_id)
            if not plan:
                plan = self.get_default_plan()
            
            if data_type == "sessions":
                results[company_id] = self._get_sessions_analytics(company_id, start_date, end_date, plan)
            elif data_type == "events":
                results[company_id] = self._get_events_analytics(company_id, start_date, end_date, plan)
            elif data_type == "regions":
                results[company_id] = self._get_regions_analytics(company_id, start_date, end_date, plan)
            elif data_type == "unique_users":
                results[company_id] = self._get_unique_users_analytics(company_id, start_date, end_date, plan)
        
        return results
    
    def _get_sessions_analytics(self, company_id: str, start_date: datetime, end_date: datetime, plan: SubscriptionPlan) -> Dict[str, Any]:
        """Get sessions analytics based on subscription plan."""
        if plan.plan_tier >= 3:  # Enterprise - use raw data
            return self._get_sessions_from_raw_data(company_id, start_date, end_date)
        elif plan.plan_tier >= 2:  # Pro - use hourly aggregation
            return self._get_sessions_from_hourly_aggregation(company_id, start_date, end_date)
        else:  # Basic - use daily aggregation
            return self._get_sessions_from_daily_aggregation(company_id, start_date, end_date)
    
    def _get_sessions_from_raw_data(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get sessions from raw events (Enterprise plan)."""
        # Query raw events for session data
        raw_events = self.db.query(RawEvent).filter(
            and_(
                RawEvent.company_id == uuid.UUID(company_id),
                RawEvent.event_timestamp >= start_date,
                RawEvent.event_timestamp <= end_date,
                RawEvent.session_id.isnot(None),
                RawEvent.session_id != ""
            )
        ).all()
        
        # Process raw data
        sessions = {}
        for event in raw_events:
            session_id = event.session_id
            if session_id not in sessions:
                sessions[session_id] = {
                    "session_id": session_id,
                    "first_seen": event.event_timestamp,
                    "last_seen": event.event_timestamp,
                    "events": 0,
                    "user_id": event.user_id
                }
            
            sessions[session_id]["events"] += 1
            if event.event_timestamp < sessions[session_id]["first_seen"]:
                sessions[session_id]["first_seen"] = event.event_timestamp
            if event.event_timestamp > sessions[session_id]["last_seen"]:
                sessions[session_id]["last_seen"] = event.event_timestamp
        
        return {
            "total_sessions": len(sessions),
            "sessions": list(sessions.values()),
            "data_source": "raw_events"
        }
    
    def _get_sessions_from_hourly_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get sessions from hourly aggregation (Pro plan)."""
        # Query hourly aggregations
        hourly_data = self.db.query(CampaignAnalyticsHourly).filter(
            and_(
                CampaignAnalyticsHourly.company_id == uuid.UUID(company_id),
                CampaignAnalyticsHourly.analytics_date >= start_date.date(),
                CampaignAnalyticsHourly.analytics_date <= end_date.date()
            )
        ).all()
        
        total_sessions = sum(data.unique_users for data in hourly_data)
        total_events = sum(sum(data.event_counts.values()) for data in hourly_data)
        
        return {
            "total_sessions": total_sessions,
            "total_events": total_events,
            "avg_events_per_session": total_events / total_sessions if total_sessions > 0 else 0,
            "data_source": "hourly_aggregation"
        }
    
    def _get_sessions_from_daily_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get sessions from daily aggregation (Basic plan)."""
        # Query daily aggregations
        daily_data = self.db.query(CampaignAnalyticsDaily).filter(
            and_(
                CampaignAnalyticsDaily.company_id == uuid.UUID(company_id),
                CampaignAnalyticsDaily.analytics_date >= start_date.date(),
                CampaignAnalyticsDaily.analytics_date <= end_date.date()
            )
        ).all()
        
        total_sessions = sum(data.unique_users for data in daily_data)
        total_events = sum(sum(data.event_counts.values()) for data in daily_data)
        
        return {
            "total_sessions": total_sessions,
            "total_events": total_events,
            "avg_events_per_session": total_events / total_sessions if total_sessions > 0 else 0,
            "data_source": "daily_aggregation"
        }
    
    def _get_events_analytics(self, company_id: str, start_date: datetime, end_date: datetime, plan: SubscriptionPlan) -> Dict[str, Any]:
        """Get events analytics based on subscription plan."""
        if plan.plan_tier >= 3:  # Enterprise - use raw data
            return self._get_events_from_raw_data(company_id, start_date, end_date)
        elif plan.plan_tier >= 2:  # Pro - use hourly aggregation
            return self._get_events_from_hourly_aggregation(company_id, start_date, end_date)
        else:  # Basic - use daily aggregation
            return self._get_events_from_daily_aggregation(company_id, start_date, end_date)
    
    def _get_events_from_raw_data(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get events from raw data (Enterprise plan)."""
        events = self.db.query(RawEvent).filter(
            and_(
                RawEvent.company_id == uuid.UUID(company_id),
                RawEvent.event_timestamp >= start_date,
                RawEvent.event_timestamp <= end_date
            )
        ).all()
        
        return {
            "total_events": len(events),
            "events": [{"id": str(e.id), "event_name": e.event_name, "timestamp": e.event_timestamp} for e in events],
            "data_source": "raw_events"
        }
    
    def _get_events_from_hourly_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get events from hourly aggregation (Pro plan)."""
        hourly_data = self.db.query(CampaignAnalyticsHourly).filter(
            and_(
                CampaignAnalyticsHourly.company_id == uuid.UUID(company_id),
                CampaignAnalyticsHourly.analytics_date >= start_date.date(),
                CampaignAnalyticsHourly.analytics_date <= end_date.date()
            )
        ).all()
        
        total_events = sum(sum(data.event_counts.values()) for data in hourly_data)
        
        return {
            "total_events": total_events,
            "data_source": "hourly_aggregation"
        }
    
    def _get_events_from_daily_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get events from daily aggregation (Basic plan)."""
        daily_data = self.db.query(CampaignAnalyticsDaily).filter(
            and_(
                CampaignAnalyticsDaily.company_id == uuid.UUID(company_id),
                CampaignAnalyticsDaily.analytics_date >= start_date.date(),
                CampaignAnalyticsDaily.analytics_date <= end_date.date()
            )
        ).all()
        
        total_events = sum(sum(data.event_counts.values()) for data in daily_data)
        
        # Convert aggregated data to individual event records
        events = []
        for data in daily_data:
            for event_name, count in data.event_counts.items():
                for i in range(count):
                    events.append({
                        "id": f"{data.id}-{event_name}-{i}",
                        "event_name": event_name,
                        "timestamp": data.analytics_date,
                        "event_type": "page_view" if "page" in event_name.lower() else "custom",
                        "properties": {},
                        "data_source": "daily_aggregation"
                    })
        
        return {
            "total_events": total_events,
            "events": events,
            "data_source": "daily_aggregation"
        }
    
    def _get_regions_analytics(self, company_id: str, start_date: datetime, end_date: datetime, plan: SubscriptionPlan) -> Dict[str, Any]:
        """Get regions analytics based on subscription plan."""
        if plan.plan_tier >= 3:  # Enterprise - use raw data
            return self._get_regions_from_raw_data(company_id, start_date, end_date)
        elif plan.plan_tier >= 2:  # Pro - use hourly aggregation
            return self._get_regions_from_hourly_aggregation(company_id, start_date, end_date)
        else:  # Basic - use daily aggregation
            return self._get_regions_from_daily_aggregation(company_id, start_date, end_date)
    
    def _get_regions_from_raw_data(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get regions from raw data (Enterprise plan)."""
        events = self.db.query(RawEvent).filter(
            and_(
                RawEvent.company_id == uuid.UUID(company_id),
                RawEvent.event_timestamp >= start_date,
                RawEvent.event_timestamp <= end_date,
                RawEvent.country.isnot(None)
            )
        ).all()
        
        countries = {}
        for event in events:
            country = event.country
            if country not in countries:
                countries[country] = {"country": country, "events": 0, "users": set()}
            countries[country]["events"] += 1
            if event.user_id:
                countries[country]["users"].add(event.user_id)
        
        # Convert sets to counts
        for country_data in countries.values():
            country_data["users"] = len(country_data["users"])
        
        return {
            "regions": list(countries.values()),
            "data_source": "raw_events"
        }
    
    def _get_regions_from_hourly_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get regions from hourly aggregation (Pro plan)."""
        hourly_data = self.db.query(CampaignAnalyticsHourly).filter(
            and_(
                CampaignAnalyticsHourly.company_id == uuid.UUID(company_id),
                CampaignAnalyticsHourly.analytics_date >= start_date.date(),
                CampaignAnalyticsHourly.analytics_date <= end_date.date()
            )
        ).all()
        
        # Aggregate country breakdowns
        countries = {}
        for data in hourly_data:
            for country, count in data.country_breakdown.items():
                if country not in countries:
                    countries[country] = {"country": country, "events": 0}
                countries[country]["events"] += count
        
        return {
            "regions": list(countries.values()),
            "data_source": "hourly_aggregation"
        }
    
    def _get_regions_from_daily_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get regions from daily aggregation (Basic plan)."""
        daily_data = self.db.query(CampaignAnalyticsDaily).filter(
            and_(
                CampaignAnalyticsDaily.company_id == uuid.UUID(company_id),
                CampaignAnalyticsDaily.analytics_date >= start_date.date(),
                CampaignAnalyticsDaily.analytics_date <= end_date.date()
            )
        ).all()
        
        # Aggregate all region data (country, region, city)
        regions = {}
        for data in daily_data:
            # Process city breakdown first (most specific)
            for city, city_count in data.city_breakdown.items():
                # Find matching country and region for this city
                country = None
                region = None
                for c, c_count in data.country_breakdown.items():
                    if c_count > 0:
                        country = c
                        break
                for r, r_count in data.region_breakdown.items():
                    if r_count > 0:
                        region = r
                        break
                
                key = f"{country}_{region}_{city}"
                if key not in regions:
                    regions[key] = {"country": country, "region": region, "city": city, "events": 0}
                regions[key]["events"] += city_count
            
            # Process region breakdown (if no city data)
            for region, region_count in data.region_breakdown.items():
                # Find matching country for this region
                country = None
                for c, c_count in data.country_breakdown.items():
                    if c_count > 0:
                        country = c
                        break
                
                # Only add if we don't already have city data for this region
                has_city_data = any(
                    r.get("region") == region and r.get("city") is not None 
                    for r in regions.values()
                )
                
                if not has_city_data:
                    key = f"{country}_{region}"
                    if key not in regions:
                        regions[key] = {"country": country, "region": region, "city": None, "events": 0}
                    regions[key]["events"] += region_count
            
            # Process country breakdown (if no region/city data)
            for country, country_count in data.country_breakdown.items():
                # Only add if we don't already have region/city data for this country
                has_region_data = any(
                    r.get("country") == country and (r.get("region") is not None or r.get("city") is not None)
                    for r in regions.values()
                )
                
                if not has_region_data:
                    key = f"{country}"
                    if key not in regions:
                        regions[key] = {"country": country, "region": None, "city": None, "events": 0}
                    regions[key]["events"] += country_count
        
        return {
            "regions": list(regions.values()),
            "data_source": "daily_aggregation"
        }
    
    def _get_unique_users_analytics(self, company_id: str, start_date: datetime, end_date: datetime, plan: SubscriptionPlan) -> Dict[str, Any]:
        """Get unique users analytics based on subscription plan."""
        if plan.plan_tier >= 3:  # Enterprise - use raw data
            return self._get_unique_users_from_raw_data(company_id, start_date, end_date)
        elif plan.plan_tier >= 2:  # Pro - use hourly aggregation
            return self._get_unique_users_from_hourly_aggregation(company_id, start_date, end_date)
        else:  # Basic - use daily aggregation
            return self._get_unique_users_from_daily_aggregation(company_id, start_date, end_date)
    
    def _get_unique_users_from_raw_data(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get unique users from raw data (Enterprise plan)."""
        events = self.db.query(RawEvent).filter(
            and_(
                RawEvent.company_id == uuid.UUID(company_id),
                RawEvent.event_timestamp >= start_date,
                RawEvent.event_timestamp <= end_date,
                RawEvent.session_id.isnot(None),
                RawEvent.session_id != ""
            )
        ).all()
        
        unique_sessions = set(event.session_id for event in events)
        total_events = len(events)
        
        return {
            "total_unique_users": len(unique_sessions),
            "total_events": total_events,
            "avg_events_per_user": total_events / len(unique_sessions) if unique_sessions else 0,
            "data_source": "raw_events"
        }
    
    def _get_unique_users_from_hourly_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get unique users from hourly aggregation (Pro plan)."""
        hourly_data = self.db.query(CampaignAnalyticsHourly).filter(
            and_(
                CampaignAnalyticsHourly.company_id == uuid.UUID(company_id),
                CampaignAnalyticsHourly.analytics_date >= start_date.date(),
                CampaignAnalyticsHourly.analytics_date <= end_date.date()
            )
        ).all()
        
        total_users = sum(data.unique_users for data in hourly_data)
        total_events = sum(sum(data.event_counts.values()) for data in hourly_data)
        
        return {
            "total_unique_users": total_users,
            "total_events": total_events,
            "avg_events_per_user": total_events / total_users if total_users > 0 else 0,
            "data_source": "hourly_aggregation"
        }
    
    def _get_unique_users_from_daily_aggregation(self, company_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get unique users from daily aggregation (Basic plan)."""
        daily_data = self.db.query(CampaignAnalyticsDaily).filter(
            and_(
                CampaignAnalyticsDaily.company_id == uuid.UUID(company_id),
                CampaignAnalyticsDaily.analytics_date >= start_date.date(),
                CampaignAnalyticsDaily.analytics_date <= end_date.date()
            )
        ).all()
        
        total_users = sum(data.unique_users for data in daily_data)
        total_events = sum(sum(data.event_counts.values()) for data in daily_data)
        
        return {
            "total_unique_users": total_users,
            "total_events": total_events,
            "avg_events_per_user": total_events / total_users if total_users > 0 else 0,
            "data_source": "daily_aggregation"
        }


# Global service instance
unified_analytics_service = UnifiedAnalyticsService
