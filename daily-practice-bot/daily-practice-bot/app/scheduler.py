"""
APScheduler wiring for a daily automatic run. Kept separate from main.py so
you can also run the agent purely via `python -m app.agent` or the FastAPI
endpoint without the scheduler ever starting (useful for testing).
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.agent import run_once

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()


def _job() -> None:
    logger.info("Running scheduled daily practice job...")
    result = run_once()
    logger.info("Daily practice job finished: %s", result)


def start_scheduler(hour: int = 9, minute: int = 0) -> None:
    """Runs once a day at the given hour/minute (server local time)."""
    scheduler.add_job(_job, CronTrigger(hour=hour, minute=minute), id="daily_practice", replace_existing=True)
    scheduler.start()
