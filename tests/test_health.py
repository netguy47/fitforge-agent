"""Tests for service health check and basic index route."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    """Verify GET /health returns 200 OK and expected structure."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["milestone"] in ["1", "2"]
    assert data["mode"] == "deterministic_local_slice"


def test_index_page(client):
    """Verify GET / returns 200 and loads HTML interface."""
    response = client.get("/")
    assert response.status_code == 200
    assert "FitForge Agent" in response.text
    assert "Privacy & Security Advisory" in response.text
    assert "Load Sample" in response.text


def test_sample_api_endpoint(client):
    """Verify GET /api/sample returns valid restaurant district manager JSON."""
    response = client.get("/api/sample")
    assert response.status_code == 200
    data = response.json()
    assert "resume_text" in data
    assert "job_description_text" in data
    assert "priorities" in data
    assert "Apex Hospitality Group" in data["resume_text"]
