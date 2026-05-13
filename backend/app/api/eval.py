"""Eval API — trigger runs as BackgroundTasks, query results, markdown report."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_scope
from app.storage.call_store import CallStore
from app.storage.database import get_db

log = structlog.get_logger()
router = APIRouter(prefix="/eval", tags=["eval"])


class EvalRunRequest(BaseModel):
    prompt_version_id: str
    scenario_ids: list[str] | str = "all"
    baseline_version_id: str | None = None


async def _run_eval_background(
    run_id: str,
    prompt_version_id: str,
    scenario_ids: list[str] | str,
    baseline_version_id: str | None,
) -> None:
    """Background task: execute eval scenarios and store results."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.config import settings
    from app.eval.runner import run_eval
    from app.storage.call_store import CallStore

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        store = CallStore(session)
        await store.update_eval_run(run_id, status="running")
        try:
            summary, scenario_results = await run_eval(
                prompt_version_id=prompt_version_id,
                scenario_ids=scenario_ids,
                baseline_version_id=baseline_version_id,
            )
            await store.update_eval_run(
                run_id,
                status="complete",
                completed_at=datetime.utcnow(),
                summary=summary,
                scenario_results=scenario_results,
            )
            log.info("eval_run_complete", run_id=run_id, accuracy=summary.get("overall_accuracy"))
        except Exception as exc:
            log.error("eval_run_failed", run_id=run_id, error=str(exc))
            await store.update_eval_run(run_id, status="failed")
    await engine.dispose()


@router.post("/runs", status_code=202)
async def create_eval_run(
    body: EvalRunRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("write")),
):
    store = CallStore(db)
    run = await store.create_eval_run(
        prompt_version_id=body.prompt_version_id,
        baseline_version_id=body.baseline_version_id,
    )
    background_tasks.add_task(
        _run_eval_background,
        run.run_id,
        body.prompt_version_id,
        body.scenario_ids,
        body.baseline_version_id,
    )
    log.info("eval_run_queued", run_id=run.run_id, version=body.prompt_version_id)
    return {"run_id": run.run_id, "status": "queued"}


@router.get("/runs")
async def list_eval_runs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    store = CallStore(db)
    runs = await store.list_eval_runs()
    return [
        {
            "run_id": r.run_id,
            "prompt_version_id": r.prompt_version_id,
            "baseline_version_id": r.baseline_version_id,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "overall_accuracy": (r.summary or {}).get("overall_accuracy"),
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_eval_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    store = CallStore(db)
    run = await store.get_eval_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return {
        "run_id": run.run_id,
        "prompt_version_id": run.prompt_version_id,
        "baseline_version_id": run.baseline_version_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "summary": run.summary,
        "scenario_results": run.scenario_results,
    }


@router.get("/runs/{run_id}/report")
async def get_eval_report(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_scope("read")),
):
    from fastapi.responses import Response
    from app.eval.reporter import generate_report

    store = CallStore(db)
    run = await store.get_eval_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Eval run not found")
    if run.status != "complete":
        raise HTTPException(status_code=400, detail=f"Run is not complete (status: {run.status})")

    report_md = generate_report(run.run_id, run.prompt_version_id, run.summary, run.scenario_results)
    return Response(content=report_md, media_type="text/markdown")
