"""
Background Scheduler Jobs.
Implements automated scraping and cleanup tasks using APScheduler.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from loguru import logger

from config import settings


# Scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create scheduler instance."""
    global _scheduler
    if _scheduler is None:
        jobstores = {
            "default": MemoryJobStore(),
        }
        executors = {
            "default": AsyncIOExecutor(),
        }
        job_defaults = {
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Only one instance of each job at a time
            "misfire_grace_time": 60 * 30,  # 30 minutes grace time
        }

        _scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="Asia/Ho_Chi_Minh",
        )
    return _scheduler


# ============================================================================
# Job Functions
# ============================================================================

async def auto_scrape_job():
    """
    Automated scraping job.
    Runs every N hours to fetch new listings from popular searches.
    """
    from agents.search_agent import RealEstateSearchAgent
    from storage.database import get_session, ListingCRUD, ScrapeLogCRUD
    from storage.vector_db import index_listings
    from storage.sheets import backup_listings
    from services.validator import get_validator

    logger.info("Starting auto_scrape job...")

    # Popular search queries to scrape
    queries = [
        "chung cư 2 phòng ngủ Cầu Giấy 2-3 tỷ",
        "chung cư 3 phòng ngủ Thanh Xuân 3-4 tỷ",
        "nhà riêng Ba Đình dưới 5 tỷ",
        "nhà riêng Đống Đa 3-5 tỷ",
        "đất nền Hà Đông dưới 2 tỷ",
        "chung cư Tây Hồ 4-6 tỷ",
        "nhà mặt phố Hoàn Kiếm",
        "chung cư Nam Từ Liêm 2-3 tỷ",
    ]

    agent = RealEstateSearchAgent(headless=True)
    validator = get_validator()

    total_found = 0
    total_new = 0
    total_errors = 0

    try:
        for query in queries:
            logger.info(f"Auto-scraping: {query}")

            async with get_session() as session:
                # Create scrape log
                scrape_log = await ScrapeLogCRUD.create(session, {
                    "platform": "multi",
                    "query": query,
                })
                log_id = scrape_log.id

            try:
                # Search
                result = await agent.search(
                    query,
                    max_results=20,
                    platforms=["chotot", "batdongsan"],
                )

                total_found += result.total_found

                if result.listings:
                    # Validate
                    valid_listings, _ = validator.validate_listings(result.listings)

                    # Save to database
                    new_count = 0
                    async with get_session() as session:
                        for listing in valid_listings:
                            _, is_new = await ListingCRUD.upsert(session, {
                                "id": listing.get("id"),
                                "title": listing.get("title"),
                                "description": listing.get("description"),
                                "price_text": listing.get("price_text"),
                                "price_number": listing.get("price_number"),
                                "price_per_m2": listing.get("price_per_m2"),
                                "property_type": listing.get("property_type"),
                                "area_m2": listing.get("area_m2"),
                                "bedrooms": listing.get("bedrooms"),
                                "bathrooms": listing.get("bathrooms"),
                                "address": listing.get("location", {}).get("address"),
                                "ward": listing.get("location", {}).get("ward"),
                                "district": listing.get("location", {}).get("district"),
                                "city": listing.get("location", {}).get("city", "Hà Nội"),
                                "contact_name": listing.get("contact", {}).get("name"),
                                "contact_phone": listing.get("contact", {}).get("phone"),
                                "contact_phone_clean": listing.get("contact", {}).get("phone_clean"),
                                "images": listing.get("images", []),
                                "source_url": listing.get("source_url"),
                                "source_platform": listing.get("source_platform"),
                                "validation_warnings": listing.get("_validation_warnings"),
                            })
                            if is_new:
                                new_count += 1

                    total_new += new_count

                    # Index to vector DB
                    await index_listings(valid_listings)

                    # Backup to Google Sheets (if configured)
                    if settings.google_sheets_credentials_file:
                        await backup_listings(valid_listings)

                # Update scrape log
                async with get_session() as session:
                    await ScrapeLogCRUD.finish(
                        session,
                        log_id,
                        listings_found=result.total_found,
                        listings_new=new_count if result.listings else 0,
                        status="completed",
                    )

            except Exception as e:
                logger.error(f"Error scraping '{query}': {e}")
                total_errors += 1

                async with get_session() as session:
                    await ScrapeLogCRUD.finish(
                        session,
                        log_id,
                        status="failed",
                        error_message=str(e),
                    )

            # Delay between queries
            await asyncio.sleep(30)

    finally:
        await agent.close()

    logger.info(
        f"Auto-scrape completed: found={total_found}, new={total_new}, errors={total_errors}"
    )


async def cleanup_old_data_job():
    """
    Cleanup job to mark old listings as expired.
    Runs daily.
    """
    from storage.database import get_session, ListingCRUD

    logger.info("Starting cleanup_old_data job...")

    async with get_session() as session:
        count = await ListingCRUD.cleanup_old(
            session,
            days=settings.cleanup_days_threshold
        )

    logger.info(f"Cleanup completed: {count} listings marked as expired")


async def notify_new_listings_job():
    """
    Check for new listings matching saved searches and send notifications.
    Runs every hour.
    """
    from storage.database import get_session, SavedSearchCRUD, ListingCRUD
    from storage.vector_db import semantic_search

    logger.info("Starting notify_new_listings job...")

    async with get_session() as session:
        saved_searches = await SavedSearchCRUD.get_all_active(session)

    if not saved_searches:
        logger.debug("No active saved searches to process")
        return

    for search in saved_searches:
        try:
            # Find matching listings
            results = await semantic_search(
                search.query,
                n_results=10,
                filters=search.filters,
            )

            if results:
                # Filter new listings (scraped after last notification)
                new_results = []
                for r in results:
                    scraped_at = r.get("scraped_at")
                    if scraped_at and search.last_notified_at:
                        if scraped_at > search.last_notified_at.isoformat():
                            new_results.append(r)
                    elif not search.last_notified_at:
                        new_results.append(r)

                if new_results:
                    # Send notification
                    try:
                        from services.telegram_bot import send_search_alert
                        await send_search_alert(
                            user_id=search.user_id,
                            search_name=search.name or search.query,
                            listings=new_results,
                        )

                        # Update last_notified_at
                        async with get_session() as session:
                            from sqlalchemy import update
                            from storage.database import SavedSearch
                            await session.execute(
                                update(SavedSearch)
                                .where(SavedSearch.id == search.id)
                                .values(
                                    last_notified_at=datetime.utcnow(),
                                    match_count=SavedSearch.match_count + len(new_results),
                                    last_match_at=datetime.utcnow(),
                                )
                            )
                    except Exception as e:
                        logger.error(f"Failed to send notification: {e}")

        except Exception as e:
            logger.error(f"Error processing saved search {search.id}: {e}")

    logger.info("Notify job completed")


async def health_check_job():
    """
    Simple health check job.
    Runs every 5 minutes.
    """
    logger.debug("Health check: scheduler is running")


async def train_valuation_model_job():
    """
    Train AutoGluon valuation model.
    Runs daily.
    """
    from storage.database import get_session
    from services.valuation_service import valuation_service

    logger.info("Starting train_valuation_model job...")

    async with get_session() as session:
        result = await valuation_service.ml_service.train_model(session)
    
    logger.info(f"Training job completed: {result}")


# ============================================================================
# Scheduler Management
# ============================================================================

def setup_jobs():
    """Setup all scheduled jobs."""
    scheduler = get_scheduler()

    # Auto scrape job - every N hours
    if settings.scheduler_enabled:
        scheduler.add_job(
            auto_scrape_job,
            trigger=IntervalTrigger(hours=settings.auto_scrape_interval_hours),
            id="auto_scrape",
            name="Auto Scrape Listings",
            replace_existing=True,
        )
        logger.info(f"Scheduled auto_scrape every {settings.auto_scrape_interval_hours} hours")

    # Cleanup job - daily at 3 AM
    scheduler.add_job(
        cleanup_old_data_job,
        trigger=CronTrigger(hour=3, minute=0),
        id="cleanup_old_data",
        name="Cleanup Old Data",
        replace_existing=True,
    )
    logger.info("Scheduled cleanup_old_data daily at 3:00 AM")

    # Training job - daily at 2 AM
    scheduler.add_job(
        train_valuation_model_job,
        trigger=CronTrigger(hour=2, minute=0),
        id="train_valuation_model",
        name="Train Valuation Model",
        replace_existing=True,
    )
    logger.info("Scheduled train_valuation_model daily at 2:00 AM")

    # Notification job - every hour
    scheduler.add_job(
        notify_new_listings_job,
        trigger=IntervalTrigger(hours=1),
        id="notify_new_listings",
        name="Notify New Listings",
        replace_existing=True,
    )
    logger.info("Scheduled notify_new_listings every hour")

    # Health check - every 5 minutes
    scheduler.add_job(
        health_check_job,
        trigger=IntervalTrigger(minutes=5),
        id="health_check",
        name="Health Check",
        replace_existing=True,
    )


async def start_scheduler():
    """Start the scheduler."""
    scheduler = get_scheduler()

    if scheduler.running:
        logger.warning("Scheduler already running")
        return

    setup_jobs()
    scheduler.start()
    logger.info("Scheduler started")

    # Keep running
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def stop_scheduler():
    """Stop the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_job_status() -> list[dict]:
    """Get status of all jobs."""
    scheduler = get_scheduler()
    jobs = []

    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })

    return jobs


async def trigger_job(job_id: str) -> bool:
    """Manually trigger a job."""
    scheduler = get_scheduler()
    job = scheduler.get_job(job_id)

    if not job:
        logger.warning(f"Job not found: {job_id}")
        return False

    logger.info(f"Manually triggering job: {job_id}")

    # Run the job function directly
    if job_id == "auto_scrape":
        await auto_scrape_job()
    elif job_id == "cleanup_old_data":
        await cleanup_old_data_job()
    elif job_id == "notify_new_listings":
        await notify_new_listings_job()
    elif job_id == "train_valuation_model":
        await train_valuation_model_job()
    else:
        return False

    return True
