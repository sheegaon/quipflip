"""Background tasks for party session maintenance."""
import asyncio
import logging

from backend.database import AsyncSessionLocal
from backend.services.qf.party_session_service import PartySessionService

logger = logging.getLogger(__name__)

# Track if maintenance task is running to prevent concurrent executions
_maintenance_task_running = False


async def run_party_maintenance() -> None:
    """Run periodic party session maintenance tasks.

    This function should be called periodically (e.g., every hour) to:
    1. Mark stale/expired party sessions as abandoned
    2. Preserve disconnected participants for reconnect
    3. Free up database resources

    Runs safely with task deduplication to prevent concurrent executions.
    """
    global _maintenance_task_running

    # Prevent concurrent executions
    if _maintenance_task_running:
        logger.debug("Party maintenance already running, skipping")
        return

    _maintenance_task_running = True
    try:
        async with AsyncSessionLocal() as db:
            party_service = PartySessionService(db)

            # Clean up stale sessions (older than 24 hours)
            logger.info("Starting party session maintenance...")
            cleanup_stats = await party_service.cleanup_expired_sessions(max_session_age_hours=24)

            # Preserve disconnected participants; this is now a no-op for reconnect safety.
            disconnected_removed = await party_service.cleanup_disconnected_participants(
                inactive_minutes=30
            )

            # Log summary
            total_sessions_expired = (
                cleanup_stats['expired_open_sessions'] +
                cleanup_stats['expired_in_progress_sessions']
            )

            logger.info(
                f"Party maintenance completed: "
                f"{total_sessions_expired} sessions abandoned, "
                f"{cleanup_stats['removed_participants']} session participants removed, "
                f"{disconnected_removed} disconnected participants removed"
            )

    except Exception as e:
        logger.error(f"Error during party maintenance: {e}", exc_info=True)
    finally:
        _maintenance_task_running = False


async def schedule_periodic_maintenance(interval_hours: int = 1) -> None:
    """Schedule party maintenance to run periodically.

    Args:
        interval_hours: Hours between maintenance runs (default 1 hour)
    """
    logger.info(f"Starting party maintenance scheduler (interval: {interval_hours}h)")

    while True:
        try:
            await asyncio.sleep(interval_hours * 3600)  # Convert to seconds
            await run_party_maintenance()
        except asyncio.CancelledError:
            logger.info("Party maintenance scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Unexpected error in maintenance scheduler: {e}", exc_info=True)
            # Continue despite errors, try again in interval
            await asyncio.sleep(60)  # Brief pause before retry
