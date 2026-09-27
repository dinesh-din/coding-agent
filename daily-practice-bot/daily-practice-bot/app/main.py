"""
FastAPI control layer.

Endpoints:
  GET  /health            liveness check
  POST /run               trigger one agent run in the background, returns immediately
  GET  /history           list recent runs
  GET  /history/{run_id}  detail of one run
"""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException

from app import db
from app.agent import run_once
from app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Daily Practice Bot", version="1.0.0")


@app.on_event("startup")
def _on_startup() -> None:
    # Comment this out if you only want to trigger runs manually via POST /run.
    start_scheduler(hour=9, minute=0)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/run")
def trigger_run(background_tasks: BackgroundTasks) -> dict:
    """Kicks off one agent run in the background and returns immediately.
    Poll GET /history to see the result once it finishes."""
    background_tasks.add_task(run_once)
    return {"status": "started"}


@app.post("/run/sync")
def trigger_run_sync() -> dict:
    """Same as /run but waits for completion — handy for local testing."""
    return run_once()


@app.get("/history")
def history(limit: int = 30) -> list[dict]:
    return db.list_runs(limit=limit)


@app.get("/history/{run_id}")
def history_detail(run_id: int) -> dict:
    run = db.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
