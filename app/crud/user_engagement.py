"""CRUD operations for user engagement tracking."""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc, asc
import uuid

from ..models import UserSession, UserEngagement, UserActivitySummary, ClientCompany
from ..schemas import (
    UserSessionCreate, UserSessionUpdate, UserEngagementCreate,
    UserActivitySummaryCreate, UserAnalyticsResponse, UserEngagementMetrics,
    UserEngagementTimeSeries, UserEngagementDashboardResponse
)


class UserEngagementCRUD:
    """CRUD operations for user engagement tracking."""

    # UserSession CRUD operations
    def create_user_session(self, db: Session, session_data: UserSessionCreate) -> UserSession:
        """Create a new user session."""
        db_session = UserSession(**session_data.model_dump())
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        return db_session

    def get_user_session(self, db: Session, session_id: str, company_id: str) -> Optional[UserSession]:
        """Get a user session by ID."""
        return db.query(UserSession).filter(
            and_(
                UserSession.session_id == session_id,
                UserSession.company_id == uuid.UUID(company_id)
            )
        ).first()

    def update_user_session(self, db: Session, session_id: str, company_id: str, 
                           update_data: UserSessionUpdate) -> Optional[UserSession]:
        """Update a user session."""
        session = self.get_user_session(db, session_id, company_id)
        if not session:
            return None
        
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(session, field, value)
        
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)
        return session

    def get_active_sessions(self, db: Session, company_id: str, 
                           last_activity_threshold: datetime) -> List[UserSession]:
        """Get all active sessions for a company."""
        return db.query(UserSession).filter(
            and_(
                UserSession.company_id == uuid.UUID(company_id),
                UserSession.last_activity >= last_activity_threshold
            )
        ).all()

    # UserEngagement CRUD operations
    def create_user_engagement(self, db: Session, engagement_data: UserEngagementCreate) -> UserEngagement:
        """Create a new user engagement record."""
        engagement = UserEngagement(**engagement_data.model_dump())
        db.add(engagement)
        db.commit()
        db.refresh(engagement)
        return engagement

    def get_user_engagements(self, db: Session, user_id: str, company_id: str,
                            start_date: datetime, end_date: datetime) -> List[UserEngagement]:
        """Get user engagement records for a specific user and time period."""
        return db.query(UserEngagement).filter(
            and_(
                UserEngagement.user_id == user_id,
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date
            )
        ).order_by(UserEngagement.event_timestamp).all()

    def get_session_engagements(self, db: Session, session_id: str, company_id: str) -> List[UserEngagement]:
        """Get all engagement records for a specific session."""
        return db.query(UserEngagement).filter(
            and_(
                UserEngagement.session_id == session_id,
                UserEngagement.company_id == uuid.UUID(company_id)
            )
        ).order_by(UserEngagement.event_timestamp).all()

    # UserActivitySummary CRUD operations
    def create_user_activity_summary(self, db: Session, summary_data: UserActivitySummaryCreate) -> UserActivitySummary:
        """Create a new user activity summary."""
        summary = UserActivitySummary(**summary_data.model_dump())
        db.add(summary)
        db.commit()
        db.refresh(summary)
        return summary

    def get_user_activity_summary(self, db: Session, company_id: str, 
                                 summary_date: date, hour: Optional[int] = None) -> Optional[UserActivitySummary]:
        """Get user activity summary for a specific date and hour."""
        query = db.query(UserActivitySummary).filter(
            and_(
                UserActivitySummary.company_id == uuid.UUID(company_id),
                UserActivitySummary.summary_date == summary_date
            )
        )
        
        if hour is not None:
            query = query.filter(UserActivitySummary.hour == hour)
        else:
            query = query.filter(UserActivitySummary.hour.is_(None))
        
        return query.first()

    def update_user_activity_summary(self, db: Session, summary_id: str, 
                                   update_data: Dict[str, Any]) -> Optional[UserActivitySummary]:
        """Update an existing user activity summary."""
        summary = db.query(UserActivitySummary).filter(
            UserActivitySummary.id == uuid.UUID(summary_id)
        ).first()
        
        if not summary:
            return None
        
        for field, value in update_data.items():
            setattr(summary, field, value)
        
        summary.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(summary)
        return summary

    def get_activity_summaries(self, db: Session, company_id: str, 
                              start_date: date, end_date: date,
                              hourly: bool = False) -> List[UserActivitySummary]:
        """Get activity summaries for a date range."""
        query = db.query(UserActivitySummary).filter(
            and_(
                UserActivitySummary.company_id == uuid.UUID(company_id),
                UserActivitySummary.summary_date >= start_date,
                UserActivitySummary.summary_date <= end_date
            )
        )
        
        if hourly:
            query = query.filter(UserActivitySummary.hour.isnot(None))
        else:
            query = query.filter(UserActivitySummary.hour.is_(None))
        
        return query.order_by(UserActivitySummary.summary_date, UserActivitySummary.hour).all()

    # Analytics methods
    def get_user_analytics(self, db: Session, company_id: str, 
                          start_date: datetime, end_date: datetime) -> UserAnalyticsResponse:
        """Get comprehensive user analytics for a time period."""
        # Get active users (users with at least one event in the period)
        active_users_query = db.query(UserEngagement.user_id).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date
            )
        ).distinct()
        
        total_active_users = active_users_query.count()
        
        # Get new users (users who have never been seen before the start date)
        new_users_query = db.query(UserEngagement.user_id).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date
            )
        ).filter(
            ~UserEngagement.user_id.in_(
                db.query(UserEngagement.user_id).filter(
                    and_(
                        UserEngagement.company_id == uuid.UUID(company_id),
                        UserEngagement.event_timestamp < start_date
                    )
                ).distinct()
            )
        ).distinct()
        
        total_new_users = new_users_query.count()
        total_returning_users = total_active_users - total_new_users
        
        # Get engagement metrics
        engagement_stats = db.query(
            func.sum(UserEngagement.engagement_duration_seconds).label('total_engagement_time'),
            func.count(UserEngagement.id).label('total_events'),
            func.count(func.distinct(UserEngagement.session_id)).label('total_sessions')
        ).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date
            )
        ).first()
        
        total_engagement_time = engagement_stats.total_engagement_time or 0
        total_events = engagement_stats.total_events or 0
        total_sessions = engagement_stats.total_sessions or 0
        
        # Calculate averages
        avg_engagement_time_per_user = total_engagement_time / total_active_users if total_active_users > 0 else 0
        avg_engagement_time_per_session = total_engagement_time / total_sessions if total_sessions > 0 else 0
        
        # Get page views
        page_views = db.query(func.count(UserEngagement.id)).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date,
                UserEngagement.event_name.in_(['page_view', 'page', 'screen'])
            )
        ).scalar() or 0
        
        return UserAnalyticsResponse(
            total_active_users=total_active_users,
            total_new_users=total_new_users,
            total_returning_users=total_returning_users,
            avg_engagement_time_per_user=avg_engagement_time_per_user,
            avg_engagement_time_per_session=avg_engagement_time_per_session,
            total_sessions=total_sessions,
            total_events=total_events,
            total_page_views=page_views,
            period_start=start_date,
            period_end=end_date,
            data_source="user_engagement"
        )

    def get_user_engagement_metrics(self, db: Session, company_id: str, 
                                   start_date: datetime, end_date: datetime,
                                   limit: int = 100) -> List[UserEngagementMetrics]:
        """Get detailed engagement metrics for top users."""
        # Get user engagement statistics
        user_stats = db.query(
            UserEngagement.user_id,
            func.count(func.distinct(UserEngagement.session_id)).label('total_sessions'),
            func.sum(UserEngagement.engagement_duration_seconds).label('total_engagement_time'),
            func.count(UserEngagement.id).label('total_events'),
            func.count(func.distinct(UserEngagement.page_url)).label('unique_pages'),
            func.min(UserEngagement.event_timestamp).label('first_seen'),
            func.max(UserEngagement.event_timestamp).label('last_seen'),
            func.max(UserEngagement.country).label('country'),
            func.max(UserEngagement.device_type).label('device_type')
        ).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date
            )
        ).group_by(UserEngagement.user_id).order_by(
            desc('total_engagement_time')
        ).limit(limit).all()
        
        # Get page views per user
        page_views_per_user = db.query(
            UserEngagement.user_id,
            func.count(UserEngagement.id).label('page_views')
        ).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date,
                UserEngagement.event_name.in_(['page_view', 'page', 'screen'])
            )
        ).group_by(UserEngagement.user_id).all()
        
        page_views_dict = {pv.user_id: pv.page_views for pv in page_views_per_user}
        
        # Check which users are new
        existing_users_before = db.query(UserEngagement.user_id).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp < start_date
            )
        ).distinct().all()
        existing_user_ids = {user.user_id for user in existing_users_before}
        
        metrics = []
        for stat in user_stats:
            avg_session_duration = stat.total_engagement_time / stat.total_sessions if stat.total_sessions > 0 else 0
            is_new_user = stat.user_id not in existing_user_ids
            
            metrics.append(UserEngagementMetrics(
                user_id=stat.user_id,
                total_sessions=stat.total_sessions,
                total_engagement_time_seconds=stat.total_engagement_time or 0,
                avg_session_duration_seconds=avg_session_duration,
                total_events=stat.total_events,
                total_page_views=page_views_dict.get(stat.user_id, 0),
                unique_pages_viewed=stat.unique_pages,
                first_seen=stat.first_seen,
                last_seen=stat.last_seen,
                is_new_user=is_new_user,
                country=stat.country,
                device_type=stat.device_type
            ))
        
        return metrics

    def get_engagement_time_series(self, db: Session, company_id: str,
                                  start_date: datetime, end_date: datetime,
                                  interval_hours: int = 1) -> List[UserEngagementTimeSeries]:
        """Get time series data for user engagement."""
        # Generate time buckets
        time_buckets = []
        current_time = start_date.replace(minute=0, second=0, microsecond=0)
        while current_time <= end_date:
            time_buckets.append(current_time)
            current_time += timedelta(hours=interval_hours)
        
        time_series = []
        for bucket_start in time_buckets:
            bucket_end = bucket_start + timedelta(hours=interval_hours)
            
            # Get metrics for this time bucket
            bucket_stats = db.query(
                func.count(func.distinct(UserEngagement.user_id)).label('active_users'),
                func.avg(UserEngagement.engagement_duration_seconds).label('avg_engagement_time'),
                func.count(func.distinct(UserEngagement.session_id)).label('total_sessions')
            ).filter(
                and_(
                    UserEngagement.company_id == uuid.UUID(company_id),
                    UserEngagement.event_timestamp >= bucket_start,
                    UserEngagement.event_timestamp < bucket_end
                )
            ).first()
            
            # Get new users for this bucket
            new_users = db.query(func.count(func.distinct(UserEngagement.user_id))).filter(
                and_(
                    UserEngagement.company_id == uuid.UUID(company_id),
                    UserEngagement.event_timestamp >= bucket_start,
                    UserEngagement.event_timestamp < bucket_end
                )
            ).filter(
                ~UserEngagement.user_id.in_(
                    db.query(UserEngagement.user_id).filter(
                        and_(
                            UserEngagement.company_id == uuid.UUID(company_id),
                            UserEngagement.event_timestamp < bucket_start
                        )
                    ).distinct()
                )
            ).scalar() or 0
            
            time_series.append(UserEngagementTimeSeries(
                timestamp=bucket_start,
                active_users=bucket_stats.active_users or 0,
                new_users=new_users,
                avg_engagement_time=bucket_stats.avg_engagement_time or 0,
                total_sessions=bucket_stats.total_sessions or 0
            ))
        
        return time_series

    def get_engagement_dashboard_data(self, db: Session, company_id: str,
                                     start_date: datetime, end_date: datetime) -> UserEngagementDashboardResponse:
        """Get comprehensive dashboard data for user engagement."""
        # Get summary analytics
        summary = self.get_user_analytics(db, company_id, start_date, end_date)
        
        # Get time series data (daily buckets)
        time_series = self.get_engagement_time_series(db, company_id, start_date, end_date, interval_hours=24)
        
        # Get top users
        top_users = self.get_user_engagement_metrics(db, company_id, start_date, end_date, limit=10)
        
        # Get device breakdown
        device_breakdown = db.query(
            UserEngagement.device_type,
            func.count(func.distinct(UserEngagement.user_id)).label('user_count')
        ).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date,
                UserEngagement.device_type.isnot(None)
            )
        ).group_by(UserEngagement.device_type).all()
        
        device_dict = {d.device_type: d.user_count for d in device_breakdown}
        
        # Get country breakdown
        country_breakdown = db.query(
            UserEngagement.country,
            func.count(func.distinct(UserEngagement.user_id)).label('user_count')
        ).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date,
                UserEngagement.country.isnot(None)
            )
        ).group_by(UserEngagement.country).all()
        
        country_dict = {c.country: c.user_count for c in country_breakdown}
        
        # Get hourly breakdown
        hourly_breakdown = db.query(
            func.extract('hour', UserEngagement.event_timestamp).label('hour'),
            func.count(func.distinct(UserEngagement.user_id)).label('user_count')
        ).filter(
            and_(
                UserEngagement.company_id == uuid.UUID(company_id),
                UserEngagement.event_timestamp >= start_date,
                UserEngagement.event_timestamp <= end_date
            )
        ).group_by(func.extract('hour', UserEngagement.event_timestamp)).all()
        
        hourly_dict = {int(h.hour): h.user_count for h in hourly_breakdown}
        
        return UserEngagementDashboardResponse(
            summary=summary,
            time_series=time_series,
            top_users=top_users,
            device_breakdown=device_dict,
            country_breakdown=country_dict,
            hourly_breakdown=hourly_dict
        )


# Create instance
user_engagement_crud = UserEngagementCRUD()
