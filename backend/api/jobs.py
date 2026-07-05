"""
YTAutomation — Job Manager

Manages background pipeline jobs with progress tracking, step management,
timing data, and SSE (Server-Sent Events) broadcasting.
"""

import asyncio
import uuid
import time
from typing import Dict, Any, List


# Pipeline stages in order
PIPELINE_STAGES = [
    {"key": "DOWNLOAD", "label": "Download Video", "icon": "⬇️"},
    {"key": "TRANSCRIBE", "label": "Transcribe Audio", "icon": "🗣️"},
    {"key": "ANALYZE", "label": "AI Viral Detection", "icon": "🤖"},
    {"key": "CLIP", "label": "Extract Clips", "icon": "✂️"},
    {"key": "SUBTITLE", "label": "Burn Subtitles", "icon": "🔤"},
    {"key": "DONE", "label": "Complete", "icon": "✅"},
]

STAGE_KEYS = [s["key"] for s in PIPELINE_STAGES]


class JobManager:
    def __init__(self):
        # job_id -> job dict
        self.jobs: Dict[str, Dict[str, Any]] = {}

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        now = time.time()
        self.jobs[job_id] = {
            "status": "processing",
            "events": [],
            "result": None,
            "error": None,
            "queues": [],
            # Enhanced tracking
            "start_time": now,
            "end_time": None,
            "current_stage": None,
            "current_step": 0,
            "total_steps": len(PIPELINE_STAGES),
            "stage_times": {},  # stage_key -> {"start": float, "end": float}
        }
        return job_id

    def add_event(self, job_id: str, stage: str, detail: str):
        if job_id not in self.jobs:
            return

        job = self.jobs[job_id]
        now = time.time()

        # Track stage transitions
        if stage in STAGE_KEYS and stage != job["current_stage"]:
            # Close previous stage timing
            if job["current_stage"] and job["current_stage"] in job["stage_times"]:
                job["stage_times"][job["current_stage"]]["end"] = now

            # Open new stage timing
            job["current_stage"] = stage
            job["stage_times"][stage] = {"start": now, "end": None}

            # Update step number
            if stage in STAGE_KEYS:
                job["current_step"] = STAGE_KEYS.index(stage) + 1

        # Calculate elapsed and ETA
        elapsed = now - job["start_time"]
        progress = job["current_step"] / job["total_steps"] if job["total_steps"] > 0 else 0
        eta_seconds = None
        if progress > 0.05:  # Only estimate after 5% progress
            eta_seconds = round((elapsed / progress) - elapsed)

        event = {
            "stage": stage,
            "detail": detail,
            "timestamp": now,
            "current_step": job["current_step"],
            "total_steps": job["total_steps"],
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": eta_seconds,
            "progress_percent": round(progress * 100, 1),
        }
        job["events"].append(event)

        # Notify all active SSE connections
        for q in job["queues"]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def complete_job(self, job_id: str, result: Any = None, error: str = None):
        if job_id not in self.jobs:
            return

        job = self.jobs[job_id]
        job["end_time"] = time.time()

        # Close last stage timing
        if job["current_stage"] and job["current_stage"] in job["stage_times"]:
            job["stage_times"][job["current_stage"]]["end"] = job["end_time"]

        if error:
            job["status"] = "error"
            job["error"] = error
            self.add_event(job_id, "ERROR", error)
        else:
            job["status"] = "completed"
            job["result"] = result
            job["current_step"] = job["total_steps"]
            self.add_event(job_id, "DONE", "Pipeline completed successfully")

        # Send EOF to close all SSE connections
        for q in job["queues"]:
            try:
                q.put_nowait({"stage": "EOF"})
            except asyncio.QueueFull:
                pass

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        if job_id not in self.jobs:
            raise ValueError("Job not found")

        q = asyncio.Queue()
        # Seed with past events so client catches up
        for evt in self.jobs[job_id]["events"]:
            q.put_nowait(evt)

        if self.jobs[job_id]["status"] in ["completed", "error"]:
            q.put_nowait({"stage": "EOF"})
        else:
            self.jobs[job_id]["queues"].append(q)

        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue):
        if job_id in self.jobs:
            if q in self.jobs[job_id]["queues"]:
                self.jobs[job_id]["queues"].remove(q)

    def get_job(self, job_id: str) -> Dict[str, Any]:
        return self.jobs.get(job_id)

    def get_job_summary(self, job_id: str) -> Dict[str, Any] | None:
        """Return a summary of the job state for the results endpoint."""
        job = self.jobs.get(job_id)
        if not job:
            return None

        elapsed = (job.get("end_time") or time.time()) - job["start_time"]

        return {
            "status": job["status"],
            "result": job["result"],
            "error": job["error"],
            "current_stage": job["current_stage"],
            "current_step": job["current_step"],
            "total_steps": job["total_steps"],
            "elapsed_seconds": round(elapsed, 1),
            "stage_times": job["stage_times"],
            "stages": PIPELINE_STAGES,
        }


job_manager = JobManager()
