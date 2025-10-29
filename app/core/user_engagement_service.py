"""User Engagement Service - Handles user activity tracking and engagement calculations."""

from datetime import datetime, timezone, timedelta, date
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session
import uuid
import json

from ..models import UserSession, UserEngagement, UserActivitySummary, Event, Web3Event
from ..crud.user_engagement import user_engagement_crud
from ..schemas import UserSessionCreate, UserEngagementCreate, UserActivitySummaryCreate


class UserEngagementService:
    """Service for tracking and calculating user engagement metrics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def process_event_for_engagement(self, company_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming event and update user engagement tracking.
        This should be called for every event that comes through the SDK.
        """
        try:
            # Extract user and session information
            user_id = event_data.get("user_id") or event_data.get("anonymous_id")
            session_id = event_data.get("session_id")
            event_name = event_data.get("event_name") or event_data.get("eventName", "unknown")
            event_timestamp = event_data.get("timestamp", datetime.now(timezone.utc))
            
            # Convert timestamp string to datetime if needed
            if isinstance(event_timestamp, str):
                from dateutil import parser
                event_timestamp = parser.parse(event_timestamp)
            
            if not user_id or not session_id:
                return {"status": "skipped", "reason": "missing_user_or_session"}
            
            # Get or create user session
            session = self._get_or_create_session(company_id, user_id, session_id, event_data, event_timestamp)
            
            # Create engagement record
            engagement = self._create_engagement_record(company_id, user_id, session_id, event_data, event_timestamp)
            
            # Update session metrics
            self._update_session_metrics(session, event_data, event_timestamp)
            
            # Update daily/hourly summaries
            self._update_activity_summaries(company_id, user_id, session_id, event_data, event_timestamp)
            
            return {
                "status": "success",
                "session_id": str(session.id),
                "engagement_id": str(engagement.id) if engagement else None
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _get_or_create_session(self, company_id: str, user_id: str, session_id: str, 
                              event_data: Dict[str, Any], event_timestamp: datetime) -> UserSession:
        """Get existing session or create a new one."""
        # Try to get existing session
        existing_session = user_engagement_crud.get_user_session(self.db, session_id, company_id)
        
        if existing_session:
            # Update last activity
            existing_session.last_activity = event_timestamp
            self.db.commit()
            return existing_session
        
        # Create new session
        session_data = UserSessionCreate(
            company_id=uuid.UUID(company_id),
            user_id=user_id,
            session_id=session_id,
            session_start=event_timestamp,
            last_activity=event_timestamp,
            country=event_data.get("country"),
            region=event_data.get("region"),
            city=event_data.get("city"),
            ip_address=event_data.get("ip_address"),
            user_agent=event_data.get("user_agent"),
            referrer=event_data.get("referrer"),
            device_type=self._detect_device_type(event_data.get("user_agent", "")),
            browser=self._detect_browser(event_data.get("user_agent", "")),
            os=self._detect_os(event_data.get("user_agent", ""))
        )
        
        return user_engagement_crud.create_user_session(self.db, session_data)
    
    def _create_engagement_record(self, company_id: str, user_id: str, session_id: str,
                                 event_data: Dict[str, Any], event_timestamp: datetime) -> Optional[UserEngagement]:
        """Create an engagement record for the event."""
        event_name = event_data.get("event_name") or event_data.get("eventName", "unknown")
        
        # Calculate engagement duration (for page events, this might be time spent on page)
        engagement_duration = self._calculate_engagement_duration(event_data, event_timestamp)
        
        engagement_data = UserEngagementCreate(
            company_id=uuid.UUID(company_id),
            user_id=user_id,
            session_id=session_id,
            event_name=event_name,
            event_timestamp=event_timestamp,
            engagement_duration_seconds=engagement_duration,
            page_url=event_data.get("properties", {}).get("url") or event_data.get("url"),
            page_title=event_data.get("properties", {}).get("title") or event_data.get("title"),
            event_properties=event_data.get("properties", {}),
            country=event_data.get("country"),
            region=event_data.get("region"),
            city=event_data.get("city"),
            ip_address=event_data.get("ip_address")
        )
        
        return user_engagement_crud.create_user_engagement(self.db, engagement_data)
    
    def _update_session_metrics(self, session: UserSession, event_data: Dict[str, Any], event_timestamp: datetime):
        """Update session metrics based on the event."""
        session.total_events += 1
        session.last_activity = event_timestamp
        
        # Update page view count
        event_name = event_data.get("event_name") or event_data.get("eventName", "")
        if event_name.lower() in ["page_view", "page", "screen"]:
            session.page_views += 1
        
        # Update unique pages (this is a simplified version)
        page_url = event_data.get("properties", {}).get("url") or event_data.get("url")
        if page_url:
            # In a real implementation, you'd track unique pages more carefully
            session.unique_pages = max(session.unique_pages, session.page_views)
        
        # Update active time
        engagement_duration = self._calculate_engagement_duration(event_data, event_timestamp)
        session.active_time_seconds += engagement_duration
        
        self.db.commit()
    
    def _update_activity_summaries(self, company_id: str, user_id: str, session_id: str,
                                  event_data: Dict[str, Any], event_timestamp: datetime):
        """Update daily and hourly activity summaries."""
        summary_date = event_timestamp.date()
        hour = event_timestamp.hour
        
        # Update daily summary
        daily_summary = self._get_or_create_activity_summary(company_id, summary_date, None)
        self._update_summary_metrics(daily_summary, user_id, event_data, event_timestamp)
        
        # Update hourly summary
        hourly_summary = self._get_or_create_activity_summary(company_id, summary_date, hour)
        self._update_summary_metrics(hourly_summary, user_id, event_data, event_timestamp)
        
        self.db.commit()
    
    def _get_or_create_activity_summary(self, company_id: str, summary_date: date, hour: Optional[int]) -> UserActivitySummary:
        """Get existing activity summary or create a new one."""
        existing_summary = user_engagement_crud.get_user_activity_summary(self.db, company_id, summary_date, hour)
        
        if existing_summary:
            return existing_summary
        
        # Create new summary
        summary_data = UserActivitySummaryCreate(
            company_id=uuid.UUID(company_id),
            summary_date=summary_date,  # Fixed: was 'date' should be 'summary_date'
            hour=hour
        )
        
        return user_engagement_crud.create_user_activity_summary(self.db, summary_data)
    
    def _update_summary_metrics(self, summary: UserActivitySummary, user_id: str, 
                               event_data: Dict[str, Any], event_timestamp: datetime):
        """Update summary metrics for a user event."""
        # Check if this is a new user (simplified - in reality you'd check against historical data)
        is_new_user = self._is_new_user(summary.company_id, user_id, event_timestamp)
        
        # Update user counts
        if is_new_user:
            summary.total_new_users += 1
        else:
            summary.total_returning_users += 1
        
        summary.total_active_users = summary.total_new_users + summary.total_returning_users
        summary.total_events += 1
        
        # Update engagement time
        engagement_duration = self._calculate_engagement_duration(event_data, event_timestamp)
        summary.total_engagement_time_seconds += engagement_duration
        
        # Update page views
        event_name = event_data.get("event_name") or event_data.get("eventName", "")
        if event_name.lower() in ["page_view", "page", "screen"]:
            summary.total_page_views += 1
        
        # Update geographic breakdown
        self._update_geographic_breakdown(summary, event_data)
        
        # Update device breakdown
        self._update_device_breakdown(summary, event_data)
        
        # Recalculate averages
        if summary.total_active_users > 0:
            summary.avg_engagement_time_per_user = summary.total_engagement_time_seconds / summary.total_active_users
        
        if summary.total_sessions > 0:
            summary.avg_engagement_time_per_session = summary.total_engagement_time_seconds / summary.total_sessions
    
    def _is_new_user(self, company_id: str, user_id: str, event_timestamp: datetime) -> bool:
        """Check if this is a new user (simplified implementation)."""
        # Check if user has any previous events before this timestamp
        previous_events = self.db.query(UserEngagement).filter(
            UserEngagement.company_id == company_id,
            UserEngagement.user_id == user_id,
            UserEngagement.event_timestamp < event_timestamp
        ).first()
        
        return previous_events is None
    
    def _update_geographic_breakdown(self, summary: UserActivitySummary, event_data: Dict[str, Any]):
        """Update geographic breakdown in summary."""
        country = event_data.get("country")
        region = event_data.get("region")
        city = event_data.get("city")
        
        if country:
            if not summary.country_breakdown:
                summary.country_breakdown = {}
            summary.country_breakdown[country] = summary.country_breakdown.get(country, 0) + 1
        
        if region:
            if not summary.region_breakdown:
                summary.region_breakdown = {}
            summary.region_breakdown[region] = summary.region_breakdown.get(region, 0) + 1
        
        if city:
            if not summary.city_breakdown:
                summary.city_breakdown = {}
            summary.city_breakdown[city] = summary.city_breakdown.get(city, 0) + 1
    
    def _update_device_breakdown(self, summary: UserActivitySummary, event_data: Dict[str, Any]):
        """Update device breakdown in summary."""
        user_agent = event_data.get("user_agent", "")
        device_type = self._detect_device_type(user_agent)
        browser = self._detect_browser(user_agent)
        os = self._detect_os(user_agent)
        
        if device_type:
            if not summary.device_breakdown:
                summary.device_breakdown = {}
            summary.device_breakdown[device_type] = summary.device_breakdown.get(device_type, 0) + 1
        
        if browser:
            if not summary.browser_breakdown:
                summary.browser_breakdown = {}
            summary.browser_breakdown[browser] = summary.browser_breakdown.get(browser, 0) + 1
        
        if os:
            if not summary.operating_system_breakdown:
                summary.operating_system_breakdown = {}
            summary.operating_system_breakdown[os] = summary.operating_system_breakdown.get(os, 0) + 1
    
    def _calculate_engagement_duration(self, event_data: Dict[str, Any], event_timestamp: datetime) -> int:
        """Calculate engagement duration for an event."""
        # For page events, try to get time spent on page
        properties = event_data.get("properties", {})
        time_spent = properties.get("time_spent") or properties.get("duration")
        
        if time_spent:
            try:
                return int(time_spent)
            except (ValueError, TypeError):
                pass
        
        # Default engagement duration based on event type
        event_name = event_data.get("event_name") or event_data.get("eventName", "").lower()
        
        if event_name in ["page_view", "page", "screen"]:
            return 30  # Default 30 seconds for page views
        elif event_name in ["click", "button_click", "link_click"]:
            return 1  # 1 second for clicks
        elif event_name in ["form_submit", "purchase", "signup"]:
            return 5  # 5 seconds for form submissions
        else:
            return 1  # Default 1 second for other events
    
    def _detect_device_type(self, user_agent: str) -> Optional[str]:
        """Detect device type from user agent."""
        user_agent_lower = user_agent.lower()
        
        if any(mobile in user_agent_lower for mobile in ["mobile", "android", "iphone", "ipod"]):
            return "mobile"
        elif any(tablet in user_agent_lower for tablet in ["tablet", "ipad"]):
            return "tablet"
        else:
            return "desktop"
    
    def _detect_browser(self, user_agent: str) -> Optional[str]:
        """Detect browser from user agent."""
        user_agent_lower = user_agent.lower()
        
        if "chrome" in user_agent_lower:
            return "chrome"
        elif "firefox" in user_agent_lower:
            return "firefox"
        elif "safari" in user_agent_lower:
            return "safari"
        elif "edge" in user_agent_lower:
            return "edge"
        elif "opera" in user_agent_lower:
            return "opera"
        else:
            return "unknown"
    
    def _detect_os(self, user_agent: str) -> Optional[str]:
        """Detect operating system from user agent."""
        user_agent_lower = user_agent.lower()
        
        if "windows" in user_agent_lower:
            return "windows"
        elif "mac" in user_agent_lower or "macos" in user_agent_lower:
            return "macos"
        elif "linux" in user_agent_lower:
            return "linux"
        elif "android" in user_agent_lower:
            return "android"
        elif "ios" in user_agent_lower or "iphone" in user_agent_lower or "ipad" in user_agent_lower:
            return "ios"
        else:
            return "unknown"
    
    def end_user_session(self, company_id: str, session_id: str) -> bool:
        """End a user session."""
        try:
            session = user_engagement_crud.get_user_session(self.db, session_id, company_id)
            if not session:
                return False
            
            session.session_end = datetime.now(timezone.utc)
            self.db.commit()
            return True
        except Exception:
            return False
    
    def get_user_engagement_summary(self, company_id: str, user_id: str, 
                                   start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get engagement summary for a specific user."""
        engagements = user_engagement_crud.get_user_engagements(
            self.db, user_id, company_id, start_date, end_date
        )
        
        if not engagements:
            return {
                "user_id": user_id,
                "total_events": 0,
                "total_engagement_time": 0,
                "avg_engagement_time": 0,
                "sessions": 0,
                "page_views": 0
            }
        
        total_engagement_time = sum(e.engagement_duration_seconds for e in engagements)
        sessions = len(set(e.session_id for e in engagements))
        page_views = len([e for e in engagements if e.event_name.lower() in ["page_view", "page", "screen"]])
        
        return {
            "user_id": user_id,
            "total_events": len(engagements),
            "total_engagement_time": total_engagement_time,
            "avg_engagement_time": total_engagement_time / len(engagements) if engagements else 0,
            "sessions": sessions,
            "page_views": page_views,
            "first_seen": min(e.event_timestamp for e in engagements),
            "last_seen": max(e.event_timestamp for e in engagements)
        }
