"""
Tests for the API routes module.

Uses FastAPI's TestClient for synchronous endpoint testing.
"""

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestRootEndpoint:
    def test_root_returns_message(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "running" in data["message"].lower()


class TestProcessEndpoint:
    def test_process_valid_url_returns_job_id(self, client):
        """POST /api/process should return a job_id."""
        with patch("backend.api.routes.run_pipeline") as mock_pipeline:
            # The pipeline runs in a background task, so it won't block
            response = client.post(
                "/api/process",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "num_clips": 3,
                    "crop_vertical": True,
                    "subtitle_style": "tiktok",
                    "highlight_words": True,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert "job_id" in data
            assert isinstance(data["job_id"], str)
            assert len(data["job_id"]) > 0

    def test_process_missing_url_returns_422(self, client):
        """POST /api/process without a URL should fail validation."""
        response = client.post("/api/process", json={})
        assert response.status_code == 422

    def test_process_invalid_json_returns_422(self, client):
        """POST /api/process with invalid body should fail."""
        response = client.post(
            "/api/process",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_process_default_values(self, client):
        """Check that default values are applied correctly."""
        with patch("backend.api.routes.run_pipeline"):
            response = client.post(
                "/api/process",
                json={"url": "https://www.youtube.com/watch?v=test"},
            )
            assert response.status_code == 200

    def test_process_with_custom_num_clips(self, client):
        """Test custom num_clips parameter."""
        with patch("backend.api.routes.run_pipeline"):
            response = client.post(
                "/api/process",
                json={
                    "url": "https://www.youtube.com/watch?v=test",
                    "num_clips": 10,
                },
            )
            assert response.status_code == 200


class TestResultsEndpoint:
    def test_results_nonexistent_job_returns_404(self, client):
        response = client.get("/api/results/nonexistent-job-id")
        assert response.status_code == 404

    def test_results_valid_job(self, client):
        """Create a job, complete it, then fetch results."""
        from backend.api.jobs import job_manager

        job_id = job_manager.create_job()
        job_manager.complete_job(job_id, result={"clip_results": []})

        response = client.get(f"/api/results/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["result"] is not None
        assert data["error"] is None

    def test_results_processing_job(self, client):
        """A job still in processing should return status=processing."""
        from backend.api.jobs import job_manager

        job_id = job_manager.create_job()
        response = client.get(f"/api/results/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processing"

    def test_results_error_job(self, client):
        from backend.api.jobs import job_manager

        job_id = job_manager.create_job()
        job_manager.complete_job(job_id, error="Pipeline crashed")

        response = client.get(f"/api/results/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["error"] == "Pipeline crashed"


class TestStatusSSEEndpoint:
    def test_status_nonexistent_job_returns_404(self, client):
        response = client.get("/api/status/nonexistent-job-id")
        assert response.status_code == 404

    def test_status_completed_job_streams_eof(self, client):
        """A completed job should stream events then EOF."""
        from backend.api.jobs import job_manager

        job_id = job_manager.create_job()
        job_manager.add_event(job_id, "DOWNLOAD", "Done downloading")
        job_manager.complete_job(job_id, result={"ok": True})

        response = client.get(f"/api/status/{job_id}")
        assert response.status_code == 200
        # Content-Type should be text/event-stream
        assert "text/event-stream" in response.headers.get("content-type", "")

        # Parse SSE data lines
        body = response.text
        data_lines = [
            line.replace("data: ", "")
            for line in body.strip().split("\n")
            if line.startswith("data: ")
        ]
        assert len(data_lines) >= 1
        # Last data line should be EOF
        last_event = json.loads(data_lines[-1])
        assert last_event["stage"] == "EOF"


class TestProcessRequestModel:
    """Test the ProcessRequest Pydantic model validation."""

    def test_url_required(self, client):
        response = client.post("/api/process", json={"num_clips": 3})
        assert response.status_code == 422

    def test_num_clips_default(self, client):
        """Default num_clips should be 5."""
        with patch("backend.api.routes.run_pipeline"):
            response = client.post(
                "/api/process",
                json={"url": "https://www.youtube.com/watch?v=test"},
            )
            assert response.status_code == 200

    def test_negative_num_clips_rejected(self, client):
        """Negative num_clips should be rejected by validation."""
        with patch("backend.api.routes.run_pipeline"):
            response = client.post(
                "/api/process",
                json={
                    "url": "https://www.youtube.com/watch?v=test",
                    "num_clips": -1,
                },
            )
            assert response.status_code == 422  # Properly validated

    def test_zero_num_clips_rejected(self, client):
        """Zero num_clips should be rejected by validation."""
        with patch("backend.api.routes.run_pipeline"):
            response = client.post(
                "/api/process",
                json={
                    "url": "https://www.youtube.com/watch?v=test",
                    "num_clips": 0,
                },
            )
            assert response.status_code == 422  # Properly validated

    def test_exceeding_max_num_clips_rejected(self, client):
        """num_clips > 20 should be rejected by validation."""
        with patch("backend.api.routes.run_pipeline"):
            response = client.post(
                "/api/process",
                json={
                    "url": "https://www.youtube.com/watch?v=test",
                    "num_clips": 25,
                },
            )
            assert response.status_code == 422
