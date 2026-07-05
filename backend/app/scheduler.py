import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .db import AppSessionLocal
from .services import digest_generator, golden_tests
from .services.alert_engine import run_all_checks
from .models import StudentSummary
from .services.risk_engine import compute_risk, RiskInputs
from sqlalchemy import select, update

logger = logging.getLogger("scheduler")
scheduler = AsyncIOScheduler()

async def job_generate_digest():
    logger.info("Starting scheduled digest generation...")
    async with AppSessionLocal() as session:
        await digest_generator.generate_digest(session)
        logger.info("Scheduled digest generation completed.")

async def job_golden_tests():
    logger.info("Starting scheduled golden tests...")
    async with AppSessionLocal() as session:
        await golden_tests.run_all(session)
        logger.info("Scheduled golden tests completed.")

async def job_recompute_risk():
    logger.info("Starting nightly risk recompute (mock implementation)...")
    # In a full production system, this would recalculate attendance/grades from raw events.
    # For MVP, the seed script already populates accurate RiskInputs.
    pass

async def job_alert_scan():
    logger.info("Starting scheduled alert scan...")
    async with AppSessionLocal() as session:
        alerts = await run_all_checks(session)
        logger.info("Scheduled alert scan completed: %d alerts created.", len(alerts))

def start_scheduler():
    if not scheduler.running:
        # Digest: bi-weekly (1st and 15th of the month)
        scheduler.add_job(job_generate_digest, CronTrigger(day="1,15", hour=3), id="generate_digest", replace_existing=True)
        # Risk Recompute: nightly at 2 AM
        scheduler.add_job(job_recompute_risk, CronTrigger(hour=2), id="recompute_risk", replace_existing=True)
        # Golden tests: nightly at 3 AM
        scheduler.add_job(job_golden_tests, CronTrigger(hour=3), id="golden_tests", replace_existing=True)
        # Alert scan: every 6 hours
        scheduler.add_job(job_alert_scan, IntervalTrigger(hours=6), id="alert_scan", replace_existing=True)
        
        scheduler.start()
        logger.info("APScheduler started.")

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler stopped.")
