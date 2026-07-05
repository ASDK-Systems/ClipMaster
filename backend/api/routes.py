"""
YTAutomation — API Routes

Endpoints:
  POST /process         — Start a new pipeline job
  GET  /status/{job_id} — SSE stream of progress events
  GET  /results/{job_id} — Fetch completed job results
  GET  /system-stats     — Current hardware usage (CPU/RAM/Disk)
  GET  /pipeline-stages  — Pipeline stage definitions
"""

import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field, HttpUrl
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from pipeline.orchestrator import run_pipeline
from backend.api.jobs import job_manager, PIPELINE_STAGES
from backend.api.system_stats import get_system_stats

router = APIRouter()


class ProcessRequest(BaseModel):
    url: HttpUrl
    num_clips: int = Field(default=5, ge=1, le=20)
    crop_vertical: bool = True
    subtitle_style: str = "tiktok"
    highlight_words: bool = True


@router.post("/process")
async def process_video(req: ProcessRequest, background_tasks: BackgroundTasks):
    """Start a new pipeline job and return the job ID."""
    job_id = job_manager.create_job()

    # Capture the current event loop so background thread can call back safely
    loop = asyncio.get_running_loop()

    def wrapped_task():
        def progress_callback(stage: str, detail: str):
            loop.call_soon_threadsafe(job_manager.add_event, job_id, stage, detail)

        try:
            result = run_pipeline(
                url=str(req.url),
                num_clips=req.num_clips,
                crop_vertical=req.crop_vertical,
                subtitle_style=req.subtitle_style,
                highlight_words=req.highlight_words,
                on_progress=progress_callback,
            )
            loop.call_soon_threadsafe(
                job_manager.complete_job, job_id, result.model_dump()
            )
        except Exception as e:
            loop.call_soon_threadsafe(
                job_manager.complete_job, job_id, None, str(e)
            )

    background_tasks.add_task(wrapped_task)
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def job_status_sse(job_id: str):
    """Stream pipeline progress events via SSE."""
    try:
        q = await job_manager.subscribe(job_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        try:
            while True:
                event = await q.get()
                data = json.dumps(event)
                yield f"data: {data}\n\n"
                if event.get("stage") == "EOF":
                    break
        finally:
            job_manager.unsubscribe(job_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/results/{job_id}")
def get_job_results(job_id: str):
    """Get job results including progress summary."""
    summary = job_manager.get_job_summary(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Job not found")
    return summary


@router.get("/system-stats")
def system_stats():
    """Return current system resource usage (CPU, RAM, disk)."""
    return get_system_stats()


@router.get("/pipeline-stages")
def pipeline_stages():
    """Return the list of pipeline stage definitions."""
    return {"stages": PIPELINE_STAGES}
