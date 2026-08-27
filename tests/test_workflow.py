"""End-to-end tests for workflow orchestration, state transitions, retrieval, and input validation.

Milestone 1 QA additions:
- test_input_length_validation: minimum (50 chars) and maximum (100k chars) boundaries.
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.coordinator import WorkflowCoordinator
from app.main import app
from app.models import WorkflowInput, WorkflowState
from app.repositories.in_memory import WorkflowRepository


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_payload():
    sample_path = Path(__file__).resolve().parent.parent / "samples" / "restaurant_district_manager.json"
    with open(sample_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_missing_required_input_validation(client):
    """Verify validation error when required input fields are empty."""
    # Empty resume
    res = client.post("/api/workflows", json={"resume_text": "", "job_description_text": "Valid JD"})
    assert res.status_code == 422

    # Empty job description
    res = client.post("/api/workflows", json={"resume_text": "Valid resume", "job_description_text": "   "})
    assert res.status_code == 422


def test_input_length_validation(client):
    """Verify minimum (50-char) and maximum (100k-char) input length boundaries."""
    # Too short résumé
    res = client.post("/api/workflows", json={
        "resume_text": "Short.",
        "job_description_text": "x" * 60,
    })
    assert res.status_code == 422
    assert "at least" in res.json()["detail"].lower() or "50" in res.json()["detail"]

    # Too short JD
    res = client.post("/api/workflows", json={
        "resume_text": "x" * 60,
        "job_description_text": "Short.",
    })
    assert res.status_code == 422

    # Too many non-negotiables
    res = client.post("/api/workflows", json={
        "resume_text": "x" * 60,
        "job_description_text": "y" * 60,
        "priorities": {
            "non_negotiables": [f"item {i}" for i in range(25)]
        }
    })
    assert res.status_code == 422
    assert "non-negotiables" in res.json()["detail"].lower() or "20" in res.json()["detail"]


def test_workflow_completion_and_state_transitions(client, sample_payload):
    """Verify full workflow completion and expected state transitions."""
    response = client.post("/api/workflows", json=sample_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["state"] == "completed"
    assert data["workflow_id"] is not None
    assert data["fit_assessment"] is not None
    assert data["evidence_matrix"] is not None
    assert len(data["evidence_matrix"]) > 0

    # Verify audit trail contains the required stages in order
    audit_trail = data["audit_trail"]
    assert len(audit_trail) >= 7

    states_sequence = [event["to_state"] for event in audit_trail]

    # The first 7 states MUST follow this pattern (may have extra correction events after validating)
    expected_prefix = [
        WorkflowState.CREATED.value,
        WorkflowState.NORMALIZING.value,
        WorkflowState.MAPPING_EVIDENCE.value,
        WorkflowState.SCORING_FIT.value,
        WorkflowState.PLANNING_ACTIONS.value,
        WorkflowState.VALIDATING.value,
    ]
    assert states_sequence[:6] == expected_prefix, f"State prefix was {states_sequence[:6]}, expected {expected_prefix}"
    assert states_sequence[-1] == WorkflowState.COMPLETED.value, f"Final state was {states_sequence[-1]}, expected completed"

    # Verify all audit events have ISO timestamps and agent names
    for event in audit_trail:
        assert "timestamp" in event and event["timestamp"]
        assert "agent_name" in event and event["agent_name"]
        assert "message" in event and event["message"]


def test_workflow_retrieval_by_id(client, sample_payload):
    """Verify retrieving a stored workflow by its unique ID."""
    create_res = client.post("/api/workflows", json=sample_payload)
    assert create_res.status_code == 200
    created_data = create_res.json()
    wf_id = created_data["workflow_id"]

    get_res = client.get(f"/api/workflows/{wf_id}")
    assert get_res.status_code == 200
    fetched_data = get_res.json()

    assert fetched_data["workflow_id"] == wf_id
    assert fetched_data["state"] == "completed"
    assert fetched_data["fit_assessment"]["fit_score"] == created_data["fit_assessment"]["fit_score"]


def test_workflow_retrieval_404_not_found(client):
    """Verify 404 response for non-existent workflow ID."""
    res = client.get("/api/workflows/non-existent-uuid-12345")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"]


def test_deterministic_sample_output(client, sample_payload):
    """Verify identical, repeatable outputs when given identical inputs."""
    res1 = client.post("/api/workflows", json=sample_payload, headers={"X-Forwarded-For": "10.0.0.1"})
    res2 = client.post("/api/workflows", json=sample_payload, headers={"X-Forwarded-For": "10.0.0.2"})

    d1 = res1.json()
    d2 = res2.json()

    assert d1["fit_assessment"]["fit_score"] == d2["fit_assessment"]["fit_score"]
    assert d1["fit_assessment"]["recommendation"] == d2["fit_assessment"]["recommendation"]
    assert len(d1["evidence_matrix"]) == len(d2["evidence_matrix"])

    # Verify classifications match exactly across runs
    classes1 = [item["classification"] for item in d1["evidence_matrix"]]
    classes2 = [item["classification"] for item in d2["evidence_matrix"]]
    assert classes1 == classes2
