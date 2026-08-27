"""Automated tests for demo rate controls, instance concurrency guards, and Cloud Run production settings."""

import json
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rate_limiter import DemoRateLimiter, rate_limiter
from app.settings import Settings


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter state before and after each test."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.fixture
def sample_payload():
    return {
        "resume_text": "Experienced District Manager with 10+ years driving multi-unit restaurant operations, P&L management, food safety compliance, and team development across 15 locations.",
        "job_description_text": "Seeking a District Manager to oversee 12 franchise locations. Must have 5+ years multi-unit experience, strong P&L leadership, and food safety certifications.",
        "priorities": {
            "min_compensation": "$95,000",
            "location_preference": "Chicago, IL",
            "desired_role_type": "District Manager",
            "non_negotiables": ["Multi-unit oversight"],
        },
    }


def test_health_endpoint_is_never_rate_limited():
    """Requirement: /health is never limited by the demo rate limiter and returns hardened payload."""
    client = TestClient(app)
    # Execute multiple rapid health checks
    for _ in range(10):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data == {"status": "healthy", "version": "0.3.0"}


def test_first_workflow_accepted_and_immediate_repeat_rejected_with_429(sample_payload):
    """Requirement: First workflow accepted; immediate repeat returns 429 with Retry-After header."""
    client = TestClient(app)

    # 1. First workflow should be accepted (200 OK in deterministic mode)
    resp1 = client.post("/api/workflows", json=sample_payload, headers={"X-Forwarded-For": "203.0.113.195"})
    assert resp1.status_code == 200
    assert resp1.json()["state"] == "completed"

    # 2. Immediate repeat from same client IP should be rejected with 429
    resp2 = client.post("/api/workflows", json=sample_payload, headers={"X-Forwarded-For": "203.0.113.195"})
    assert resp2.status_code == 429
    assert "Retry-After" in resp2.headers
    retry_after = int(resp2.headers["Retry-After"])
    assert 1 <= retry_after <= 60
    assert "Rate limit exceeded" in resp2.json()["detail"]


def test_different_clients_have_independent_cooldowns(sample_payload):
    """Requirement: Rate limiter tracks distinct client IPs independently."""
    client = TestClient(app)

    # Client A executes
    resp_a = client.post("/api/workflows", json=sample_payload, headers={"X-Forwarded-For": "198.51.100.10"})
    assert resp_a.status_code == 200

    # Client B executes immediately afterward from different IP
    resp_b = client.post("/api/workflows", json=sample_payload, headers={"X-Forwarded-For": "198.51.100.20"})
    assert resp_b.status_code == 200


def test_instance_concurrency_lock_rejects_simultaneous_execution():
    """Requirement: Concurrency guard permits no more than one active workflow per instance."""
    limiter = DemoRateLimiter(cooldown_seconds=60)

    # Client 1 acquires lock
    limiter.acquire("192.0.2.1")

    # Client 2 attempts acquisition while Client 1 is active
    with pytest.raises(Exception) as exc_info:
        limiter.acquire("192.0.2.2")

    assert exc_info.value.status_code == 429
    assert "currently being processed" in exc_info.value.detail
    assert exc_info.value.headers["Retry-After"] == "10"

    # Client 1 finishes and releases
    limiter.release()

    # Client 2 can now acquire
    limiter.acquire("192.0.2.2")
    limiter.release()


def test_memory_pruning_bounds_storage():
    """Requirement: Rate limiter prunes expired timestamps to maintain bounded memory."""
    limiter = DemoRateLimiter(cooldown_seconds=10)
    # Manually inject old timestamp beyond cutoff (cutoff = 100 - 20 = 80)
    limiter._client_timestamps["old_client_hash"] = 50.0
    limiter._client_timestamps["recent_client_hash"] = 95.0

    # Trigger acquire at time 100.0 (simulated via _prune_expired)
    limiter._prune_expired(now=100.0)

    assert "old_client_hash" not in limiter._client_timestamps
    assert "recent_client_hash" in limiter._client_timestamps


def test_no_external_network_calls_in_offline_tests(sample_payload):
    """Requirement: Normal tests run entirely in deterministic mode with no external calls."""
    client = TestClient(app)
    resp = client.post("/api/workflows", json=sample_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["execution_mode"] == "deterministic"
    assert data["state"] == "completed"
    assert data["fit_assessment"] is not None


def test_production_cloud_run_configuration_defaults():
    """Requirement: Settings support Cloud Run deployment guardrails."""
    settings = Settings.from_env()
    assert settings.firestore_database == "(default)"
    assert settings.firestore_collection == "workflows"
    assert settings.gemini_model in {"gemini-3.5-flash", "gemini-2.5-flash", "gemini-1.5-flash"}
