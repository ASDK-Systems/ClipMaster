"""
Tests for the backend JobManager.
"""

import asyncio
import pytest

from backend.api.jobs import JobManager


class TestJobManagerCreate:
    def test_create_job_returns_unique_ids(self):
        jm = JobManager()
        ids = {jm.create_job() for _ in range(50)}
        assert len(ids) == 50

    def test_create_job_initial_status(self):
        jm = JobManager()
        job_id = jm.create_job()
        job = jm.get_job(job_id)
        assert job["status"] == "processing"
        assert job["result"] is None
        assert job["error"] is None
        assert job["events"] == []
        assert job["queues"] == []


class TestJobManagerEvents:
    def test_add_event_stores_event(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.add_event(job_id, "DOWNLOAD", "Starting download")
        job = jm.get_job(job_id)
        assert len(job["events"]) == 1
        assert job["events"][0]["stage"] == "DOWNLOAD"
        assert job["events"][0]["detail"] == "Starting download"
        assert "timestamp" in job["events"][0]

    def test_add_event_nonexistent_job_does_not_raise(self):
        jm = JobManager()
        # Should not raise
        jm.add_event("nonexistent-id", "DOWNLOAD", "test")

    def test_add_multiple_events(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.add_event(job_id, "DOWNLOAD", "Step 1")
        jm.add_event(job_id, "TRANSCRIBE", "Step 2")
        jm.add_event(job_id, "ANALYZE", "Step 3")
        assert len(jm.get_job(job_id)["events"]) == 3


class TestJobManagerComplete:
    def test_complete_job_success(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.complete_job(job_id, result={"clips": []})
        job = jm.get_job(job_id)
        assert job["status"] == "completed"
        assert job["result"] == {"clips": []}
        assert job["error"] is None

    def test_complete_job_error(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.complete_job(job_id, error="Something went wrong")
        job = jm.get_job(job_id)
        assert job["status"] == "error"
        assert job["error"] == "Something went wrong"
        # Error should add an ERROR event
        stages = [e["stage"] for e in job["events"]]
        assert "ERROR" in stages

    def test_complete_job_success_adds_done_event(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.complete_job(job_id, result={"data": "ok"})
        stages = [e["stage"] for e in jm.get_job(job_id)["events"]]
        assert "DONE" in stages

    def test_complete_nonexistent_job_no_raise(self):
        jm = JobManager()
        jm.complete_job("nonexistent-id", result={})


class TestJobManagerGetJob:
    def test_get_nonexistent_job_returns_none(self):
        jm = JobManager()
        assert jm.get_job("nonexistent") is None


class TestJobManagerSubscribe:
    @pytest.mark.asyncio
    async def test_subscribe_returns_queue_with_past_events(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.add_event(job_id, "DOWNLOAD", "Downloading")
        jm.add_event(job_id, "TRANSCRIBE", "Transcribing")

        q = await jm.subscribe(job_id)
        events = []
        while not q.empty():
            events.append(await q.get())
        assert len(events) == 2
        assert events[0]["stage"] == "DOWNLOAD"
        assert events[1]["stage"] == "TRANSCRIBE"

    @pytest.mark.asyncio
    async def test_subscribe_completed_job_gets_eof(self):
        jm = JobManager()
        job_id = jm.create_job()
        jm.complete_job(job_id, result={"ok": True})

        q = await jm.subscribe(job_id)
        events = []
        while not q.empty():
            events.append(await q.get())
        # Should have DONE event + EOF
        stages = [e["stage"] for e in events]
        assert "EOF" in stages

    @pytest.mark.asyncio
    async def test_subscribe_nonexistent_job_raises(self):
        jm = JobManager()
        with pytest.raises(ValueError, match="Job not found"):
            await jm.subscribe("nonexistent-id")

    @pytest.mark.asyncio
    async def test_subscribe_receives_live_events(self):
        jm = JobManager()
        job_id = jm.create_job()
        q = await jm.subscribe(job_id)

        # Add events after subscribing
        jm.add_event(job_id, "LIVE", "live event")
        event = await asyncio.wait_for(q.get(), timeout=1.0)
        assert event["stage"] == "LIVE"

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self):
        jm = JobManager()
        job_id = jm.create_job()
        q = await jm.subscribe(job_id)
        assert q in jm.get_job(job_id)["queues"]

        jm.unsubscribe(job_id, q)
        assert q not in jm.get_job(job_id)["queues"]

    @pytest.mark.asyncio
    async def test_unsubscribe_nonexistent_no_raise(self):
        jm = JobManager()
        q = asyncio.Queue()
        jm.unsubscribe("nonexistent", q)  # Should not raise


class TestJobManagerEOFOnComplete:
    """Test that completing a job sends EOF to all subscribed queues."""

    @pytest.mark.asyncio
    async def test_eof_sent_on_complete(self):
        jm = JobManager()
        job_id = jm.create_job()
        q = await jm.subscribe(job_id)

        jm.complete_job(job_id, result={"data": "ok"})

        events = []
        while not q.empty():
            events.append(await q.get())
        stages = [e["stage"] for e in events]
        assert "DONE" in stages
        assert "EOF" in stages

    @pytest.mark.asyncio
    async def test_eof_sent_on_error(self):
        jm = JobManager()
        job_id = jm.create_job()
        q = await jm.subscribe(job_id)

        jm.complete_job(job_id, error="Boom!")

        events = []
        while not q.empty():
            events.append(await q.get())
        stages = [e["stage"] for e in events]
        assert "ERROR" in stages
        assert "EOF" in stages
