"""Background service to purge localhost-originated event data after 24 hours.

Removes rows from Event, Web3Event, and RawEvent where ip_address is a localhost
indicator and the record is older than the cutoff (24h by default).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Tuple

from sqlalchemy import or_

from .database import SessionLocal
from ..models import Event, Web3Event, RawEvent

logger = logging.getLogger(__name__)

LOCALHOST_IPS = {"127.0.0.1", "::1", "0:0:0:0:0:0:0:1", "localhost"}
DEFAULT_CUTOFF_HOURS = 24
DEFAULT_CLEANUP_INTERVAL_SECONDS = 3600  # run hourly

class EventCleanupService:
    def __init__(self):
        self.is_running = False
        self.cleanup_interval = DEFAULT_CLEANUP_INTERVAL_SECONDS

    async def start_auto_cleanup(self):
        """Start the automatic periodic cleanup loop."""
        if self.is_running:
            logger.warning("Event cleanup service already running")
            return
        self.is_running = True
        logger.info("🧹 Starting localhost event cleanup service")
        while self.is_running:
            try:
                deleted = self.purge_localhost_events()
                total_deleted = sum(deleted)
                if total_deleted > 0:
                    logger.info(f"🗑️ Purged localhost events older than 24h: Event={deleted[0]}, Web3Event={deleted[1]}, RawEvent={deleted[2]}")
                else:
                    logger.debug("No localhost events eligible for purge this cycle")
            except Exception as e:
                logger.error(f"Error during localhost event purge: {e}")
            # Sleep until next cycle
            await asyncio.sleep(self.cleanup_interval)

    def stop_auto_cleanup(self):
        """Signal the loop to stop."""
        self.is_running = False
        logger.info("🛑 Stopping localhost event cleanup service")

    def _localhost_clause(self, column):
        """Return SQLAlchemy filter clause matching localhost addresses."""
        return or_(
            column.in_(LOCALHOST_IPS),
            column.like("127.%")
        )

    def purge_localhost_events(self, cutoff_hours: int = DEFAULT_CUTOFF_HOURS) -> Tuple[int, int, int]:
        """Delete localhost-originated events older than cutoff.
        Returns tuple (#EventsDeleted, #Web3EventsDeleted, #RawEventsDeleted).
        """
        db = SessionLocal()
        try:
            cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=cutoff_hours)

            # Regular events
            events_deleted = db.query(Event).filter(
                self._localhost_clause(Event.ip_address),
                Event.timestamp < cutoff_dt
            ).delete(synchronize_session=False)

            # Web3 events
            web3_deleted = db.query(Web3Event).filter(
                self._localhost_clause(Web3Event.ip_address),
                Web3Event.timestamp < cutoff_dt
            ).delete(synchronize_session=False)

            # Raw events (enterprise) - use event_timestamp
            raw_deleted = db.query(RawEvent).filter(
                self._localhost_clause(RawEvent.ip_address),
                RawEvent.event_timestamp < cutoff_dt
            ).delete(synchronize_session=False)

            db.commit()
            return events_deleted, web3_deleted, raw_deleted
        except Exception as e:
            logger.error(f"Failed to purge localhost events: {e}")
            db.rollback()
            return 0, 0, 0
        finally:
            db.close()

# Global instance
event_cleanup_service = EventCleanupService()

# Convenience function for manual/one-off purge (used in tests or ops scripts)
def purge_localhost_events(cutoff_hours: int = DEFAULT_CUTOFF_HOURS) -> Tuple[int, int, int]:
    return event_cleanup_service.purge_localhost_events(cutoff_hours=cutoff_hours)
