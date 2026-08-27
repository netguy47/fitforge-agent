"""Milestone 3A Tests: Google Cloud Firestore Persistence Layer (Offline Verification).

Verified Constraints:
1. In-memory persistence remains the default.
2. Invalid persistence backends are rejected with clean ValueError.
3. Firestore configuration is loaded from environment variables.
4. In-memory mode never constructs a Firestore client.
5. The Firestore client is lazily constructed (never at import or repository init).
6. A workflow is serialized into the configured collection using its workflow_id.
7. A saved workflow is reconstructed as a valid domain WorkflowResult.
8. Missing documents return None.
9. Two repository instances sharing the same fake client demonstrate persistence and recovery.
10. Coordinator state transitions are saved through the repository abstraction.
11. The API can recover a workflow by ID using the selected repository.
12. Firestore exceptions are sanitized into stable categories.
13. Explicit Firestore mode never silently falls back to in-memory storage on error.
14. Two calls to get_repository() with identical settings return the identical repository object (repo1 is repo2).
15. Separately constructed but equivalent Settings resolve to the same cached repository.
16. Different collection/database/project configurations resolve to distinct repositories.
17. Client factory is invoked at most once across repeated repository retrieval and operations.
18. Cache reset creates a fresh repository afterward.
19. Repository override takes precedence without constructing any client.
20. Logs and raised errors exclude workflow ID, collection name, project ID, résumé text, JD text, and raw provider messages.
"""

import logging
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from app.coordinator import WorkflowCoordinator
from app.main import app
from app.models import (
    ApplicantPriorities,
    AuditEvent,
    EvidenceClassification,
    EvidenceItem,
    FitAssessment,
    RecommendationType,
    WorkflowInput,
    WorkflowResult,
    WorkflowState,
)
from app.repositories.base import BaseWorkflowRepository
from app.repositories.factory import (
    get_repository,
    reset_repository_cache,
    set_repository_override,
)
from app.repositories.firestore import (
    FirestoreWorkflowRepository,
    categorize_firestore_error,
)
from app.repositories.in_memory import InMemoryWorkflowRepository
from app.settings import Settings


# -----------------------------------------------------------------------------
# Faithful In-Memory Fake Firestore Client for Offline Testing
# -----------------------------------------------------------------------------

class FakeDocumentReference:
    def __init__(self, collection_dict: Dict[str, Any], doc_id: str):
        self._collection = collection_dict
        self._doc_id = doc_id

    def set(self, data: Dict[str, Any]):
        self._collection[self._doc_id] = dict(data)

    def get(self):
        data = self._collection.get(self._doc_id)
        return FakeDocumentSnapshot(exists=data is not None, data=data, ref=self)

    def delete(self):
        self._collection.pop(self._doc_id, None)


class FakeDocumentSnapshot:
    def __init__(self, exists: bool, data: Optional[Dict[str, Any]], ref: Optional[FakeDocumentReference] = None):
        self.exists = exists
        self._data = data
        self.reference = ref

    def to_dict(self) -> Optional[Dict[str, Any]]:
        return dict(self._data) if self._data is not None else None


class FakeCollectionReference:
    def __init__(self, storage: Dict[str, Dict[str, Any]], name: str):
        self._storage = storage
        self._name = name
        if name not in self._storage:
            self._storage[name] = {}

    def document(self, doc_id: str) -> FakeDocumentReference:
        return FakeDocumentReference(self._storage[self._name], doc_id)

    def stream(self) -> List[FakeDocumentSnapshot]:
        return [
            FakeDocumentSnapshot(
                exists=True,
                data=data,
                ref=FakeDocumentReference(self._storage[self._name], doc_id),
            )
            for doc_id, data in self._storage[self._name].items()
        ]


class FakeFirestoreClient:
    """In-memory fake implementing the Google Cloud Firestore client API surface."""

    def __init__(self):
        self._storage: Dict[str, Dict[str, Any]] = {}
        self.call_count = 0

    def collection(self, name: str) -> FakeCollectionReference:
        self.call_count += 1
        return FakeCollectionReference(self._storage, name)


@pytest.fixture(autouse=True)
def clean_repository_environment():
    """Reset repository cache and global overrides before and after every test."""
    reset_repository_cache()
    yield
    reset_repository_cache()


@pytest.fixture
def sample_workflow():
    return WorkflowResult(
        workflow_id="wf-test-secret-12345",
        state=WorkflowState.COMPLETED,
        execution_mode="deterministic",
        inputs=WorkflowInput(
            resume_text="Senior Regional Director with 10 years experience overseeing multi-unit hospitality",
            job_description_text="District Manager needed for restaurant operations oversight and P&L",
            priorities=ApplicantPriorities(min_compensation="$100k"),
        ),
        fit_assessment=FitAssessment(
            fit_score=90,
            recommendation=RecommendationType.PURSUE,
            score_explanation="Candidate matches core criteria",
            uncertainty_explanation="Low uncertainty",
        ),
        evidence_matrix=[
            EvidenceItem(
                requirement="P&L management",
                category="Operations",
                classification=EvidenceClassification.DIRECT,
                resume_evidence="Managed $20M P&L across 12 units",
                reasoning="Direct match",
            )
        ],
    )


# -----------------------------------------------------------------------------
# Configuration Tests
# -----------------------------------------------------------------------------

def test_1_in_memory_persistence_is_default(monkeypatch):
    """1. Verify in-memory persistence is default when PERSISTENCE_BACKEND is unset."""
    monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
    s = Settings.from_env()
    assert s.persistence_backend == "in_memory"
    assert s.is_in_memory_persistence is True
    assert s.is_firestore_persistence is False


def test_2_invalid_persistence_backend_rejected():
    """2. Verify invalid persistence backends raise ValueError."""
    with pytest.raises(ValueError, match="Invalid PERSISTENCE_BACKEND"):
        Settings(persistence_backend="invalid_backend")


def test_3_firestore_configuration_loaded_from_env(monkeypatch):
    """3. Verify Firestore configuration is loaded from environment variables."""
    monkeypatch.setenv("PERSISTENCE_BACKEND", "firestore")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "test-gcp-project")
    monkeypatch.setenv("FIRESTORE_DATABASE", "fitforge-db")
    monkeypatch.setenv("FIRESTORE_COLLECTION", "custom_workflows")

    s = Settings.from_env()
    assert s.persistence_backend == "firestore"
    assert s.is_firestore_persistence is True
    assert s.google_cloud_project == "test-gcp-project"
    assert s.firestore_database == "fitforge-db"
    assert s.firestore_collection == "custom_workflows"


# -----------------------------------------------------------------------------
# Lazy Initialization & Lifecycle Caching Tests
# -----------------------------------------------------------------------------

def test_4_in_memory_mode_never_constructs_firestore_client():
    """4. Verify in-memory repository factory does not instantiate a Firestore client."""
    settings = Settings(persistence_backend="in_memory")
    repo = get_repository(settings=settings)
    assert isinstance(repo, InMemoryWorkflowRepository)
    assert not hasattr(repo, "_client")


def test_5_firestore_client_lazily_constructed():
    """5. Verify Firestore client is not constructed until a database operation is called."""
    settings = Settings(
        persistence_backend="firestore",
        google_cloud_project="test-project",
    )
    repo = FirestoreWorkflowRepository(settings=settings)
    assert repo._client is None  # Uninitialized prior to first operation


def test_14_get_repository_returns_identical_cached_instance_for_same_config():
    """14. Verify repeated calls to get_repository() with identical settings return the same object."""
    settings = Settings(
        persistence_backend="firestore",
        google_cloud_project="my-proj",
        firestore_database="(default)",
        firestore_collection="workflows",
    )
    repo1 = get_repository(settings=settings)
    repo2 = get_repository(settings=settings)
    assert repo1 is repo2


def test_15_separately_constructed_equivalent_settings_resolve_to_same_repository():
    """15. Verify separately constructed Settings with matching config share the cached repository."""
    s1 = Settings(
        persistence_backend="firestore",
        google_cloud_project="proj-alpha",
        firestore_database="db-1",
        firestore_collection="wf-col",
    )
    s2 = Settings(
        persistence_backend="firestore",
        google_cloud_project="proj-alpha",
        firestore_database="db-1",
        firestore_collection="wf-col",
    )
    repo1 = get_repository(settings=s1)
    repo2 = get_repository(settings=s2)
    assert repo1 is repo2


def test_16_different_configurations_do_not_share_cached_repositories():
    """16. Verify different collections/projects produce separate repository instances."""
    s1 = Settings(persistence_backend="firestore", firestore_collection="col_a")
    s2 = Settings(persistence_backend="firestore", firestore_collection="col_b")

    repo1 = get_repository(settings=s1)
    repo2 = get_repository(settings=s2)
    assert repo1 is not repo2


def test_17_real_client_factory_invoked_at_most_once_across_retrieval_and_operations(sample_workflow):
    """17. Verify client factory is invoked at most once across repeated repository retrieval and calls."""
    client_creations = 0
    fake_client = FakeFirestoreClient()

    def client_factory():
        nonlocal client_creations
        client_creations += 1
        return fake_client

    settings = Settings(persistence_backend="firestore", firestore_collection="cached_test")

    repo1 = get_repository(settings=settings, client_factory=client_factory)
    assert client_creations == 0  # Still lazy

    repo1.save(sample_workflow)
    assert client_creations == 1  # Constructed on first op

    repo2 = get_repository(settings=settings)
    assert repo2 is repo1
    repo2.get(sample_workflow.workflow_id)
    assert client_creations == 1  # Reused, NOT recreated


def test_18_cache_reset_creates_fresh_repository_afterward():
    """18. Verify reset_repository_cache() forces construction of a fresh repository."""
    settings = Settings(persistence_backend="firestore", firestore_collection="reset_test")
    repo1 = get_repository(settings=settings)

    reset_repository_cache()
    repo2 = get_repository(settings=settings)
    assert repo1 is not repo2


def test_19_repository_override_takes_precedence_without_constructing_client(sample_workflow):
    """19. Verify explicit repository override takes precedence without client instantiation."""
    fake_override = InMemoryWorkflowRepository()
    fake_override.save(sample_workflow)

    set_repository_override(fake_override)

    settings = Settings(persistence_backend="firestore", google_cloud_project="never-connected")
    repo = get_repository(settings=settings)

    assert repo is fake_override
    recovered = repo.get(sample_workflow.workflow_id)
    assert recovered is not None
    assert recovered.workflow_id == sample_workflow.workflow_id


# -----------------------------------------------------------------------------
# Serialization, Persistence & Recovery Tests
# -----------------------------------------------------------------------------

def test_6_workflow_serialized_into_configured_collection(sample_workflow):
    """6. Verify workflow is serialized into the configured collection using workflow_id."""
    fake_client = FakeFirestoreClient()
    settings = Settings(
        persistence_backend="firestore",
        firestore_collection="app_workflows",
    )
    repo = FirestoreWorkflowRepository(settings=settings, client=fake_client)

    saved = repo.save(sample_workflow)
    assert saved.workflow_id == sample_workflow.workflow_id

    # Verify underlying storage structure
    assert "app_workflows" in fake_client._storage
    assert sample_workflow.workflow_id in fake_client._storage["app_workflows"]
    doc_data = fake_client._storage["app_workflows"][sample_workflow.workflow_id]
    assert doc_data["workflow_id"] == sample_workflow.workflow_id
    assert doc_data["state"] == "completed"
    assert doc_data["fit_assessment"]["fit_score"] == 90


def test_7_saved_workflow_reconstructed_as_valid_model(sample_workflow):
    """7. Verify saved workflow is reconstructed as a fully valid WorkflowResult."""
    fake_client = FakeFirestoreClient()
    settings = Settings(persistence_backend="firestore")
    repo = FirestoreWorkflowRepository(settings=settings, client=fake_client)

    repo.save(sample_workflow)
    recovered = repo.get(sample_workflow.workflow_id)

    assert recovered is not None
    assert isinstance(recovered, WorkflowResult)
    assert recovered.workflow_id == sample_workflow.workflow_id
    assert recovered.state == WorkflowState.COMPLETED
    assert recovered.fit_assessment.fit_score == 90
    assert recovered.evidence_matrix[0].requirement == "P&L management"


def test_8_missing_document_returns_none():
    """8. Verify querying a non-existent document ID returns None."""
    fake_client = FakeFirestoreClient()
    settings = Settings(persistence_backend="firestore")
    repo = FirestoreWorkflowRepository(settings=settings, client=fake_client)

    result = repo.get("non-existent-wf-id")
    assert result is None


def test_9_two_repositories_share_persistence_via_same_client(sample_workflow):
    """9. Verify two repository instances sharing the same client demonstrate persistence/recovery."""
    fake_client = FakeFirestoreClient()
    settings = Settings(persistence_backend="firestore")

    repo1 = FirestoreWorkflowRepository(settings=settings, client=fake_client)
    repo2 = FirestoreWorkflowRepository(settings=settings, client=fake_client)

    repo1.save(sample_workflow)
    recovered = repo2.get(sample_workflow.workflow_id)

    assert recovered is not None
    assert recovered.workflow_id == sample_workflow.workflow_id


# -----------------------------------------------------------------------------
# Coordinator & API Integration Tests
# -----------------------------------------------------------------------------

def test_10_coordinator_state_transitions_saved_through_repository():
    """10. Verify coordinator persists state transitions through the repository abstraction."""
    fake_client = FakeFirestoreClient()
    settings = Settings(persistence_backend="firestore")
    repo = FirestoreWorkflowRepository(settings=settings, client=fake_client)
    coordinator = WorkflowCoordinator(repo=repo, settings=settings)

    inp = WorkflowInput(
        resume_text="Results-driven Multi-Unit Leader with 8+ years experience managing 7 restaurant units with $16.5M revenue. ServSafe Certified.",
        job_description_text="District Manager needed for 8-10 restaurants. P&L oversight, ServSafe certification, and valid driver's license required.",
        priorities=ApplicantPriorities(),
    )

    wf = coordinator.execute_workflow(inp)
    assert wf.state == WorkflowState.COMPLETED

    stored = repo.get(wf.workflow_id)
    assert stored is not None
    assert stored.state == WorkflowState.COMPLETED
    assert len(stored.audit_trail) >= 5


def test_11_api_can_recover_workflow_using_selected_repository(sample_workflow):
    """11. Verify FastAPI endpoint recovers workflow by ID using configured repository."""
    fake_client = FakeFirestoreClient()
    settings = Settings(persistence_backend="firestore")
    repo = FirestoreWorkflowRepository(settings=settings, client=fake_client)
    repo.save(sample_workflow)

    set_repository_override(repo)
    client = TestClient(app)

    response = client.get(f"/api/workflows/{sample_workflow.workflow_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"] == sample_workflow.workflow_id
    assert data["state"] == "completed"
    assert data["fit_assessment"]["fit_score"] == 90


# -----------------------------------------------------------------------------
# Error Handling, Sanitization & Non-Fallback Tests
# -----------------------------------------------------------------------------

def test_12_firestore_error_categorization_and_sanitization():
    """12. Verify Firestore exceptions are categorized without exposing raw exception text or secrets."""
    assert categorize_firestore_error(RuntimeError("401 Unauthenticated: Missing token")) == "firestore_authentication_failed"
    assert categorize_firestore_error(RuntimeError("403 PermissionDenied: Access to project foo denied")) == "firestore_permission_denied"
    assert categorize_firestore_error(RuntimeError("404 NotFound: Document does not exist")) == "firestore_not_found"
    assert categorize_firestore_error(RuntimeError("503 Service Unavailable: Socket connection closed")) == "firestore_unavailable"
    assert categorize_firestore_error(TimeoutError("DeadlineExceeded after 10s")) == "firestore_timeout"
    assert categorize_firestore_error(ValueError("Corrupted document data")) == "firestore_data_invalid"
    assert categorize_firestore_error(Exception("Unknown internal error")) == "firestore_operation_failed"


def test_13_explicit_firestore_mode_never_silently_falls_back():
    """13. Verify explicit Firestore mode raises RuntimeError on failure and does not silently use in-memory."""
    class FailingClient:
        def collection(self, name):
            raise RuntimeError("503 Service Unavailable: Network Failure")

    settings = Settings(persistence_backend="firestore")
    repo = FirestoreWorkflowRepository(settings=settings, client=FailingClient())

    with pytest.raises(RuntimeError) as exc_info:
        repo.save(WorkflowResult(workflow_id="wf-fail", state=WorkflowState.CREATED, inputs=WorkflowInput(resume_text="r", job_description_text="j")))

    assert "Firestore persistence failed: firestore_unavailable" in str(exc_info.value)
    # Ensure sensitive details are not leaked
    assert "FailingClient" not in str(exc_info.value)
    assert "Network Failure" not in str(exc_info.value)


def test_20_logs_and_errors_exclude_sensitive_and_context_details(caplog, sample_workflow):
    """20. Verify logs and raised errors exclude workflow ID, collection name, project ID, résumé, JD, and raw error."""
    caplog.set_level(logging.DEBUG)

    class SecretLeakingClient:
        def collection(self, name):
            raise RuntimeError(f"RAW_SECRET_LEAK_IN_PROVIDER_EXCEPTION on project-secret-id and collection {name}")

    settings = Settings(
        persistence_backend="firestore",
        google_cloud_project="project-secret-id",
        firestore_collection="secret_collection_name",
    )
    repo = FirestoreWorkflowRepository(settings=settings, client=SecretLeakingClient())

    with pytest.raises(RuntimeError) as exc_info:
        repo.save(sample_workflow)

    err_msg = str(exc_info.value)
    # Check error message cleanliness
    assert "project-secret-id" not in err_msg
    assert "secret_collection_name" not in err_msg
    assert "RAW_SECRET_LEAK_IN_PROVIDER_EXCEPTION" not in err_msg
    assert sample_workflow.workflow_id not in err_msg
    assert sample_workflow.inputs.resume_text not in err_msg
    assert sample_workflow.inputs.job_description_text not in err_msg

    # Check log output cleanliness
    log_text = caplog.text
    assert "project-secret-id" not in log_text
    assert "secret_collection_name" not in log_text
    assert "RAW_SECRET_LEAK_IN_PROVIDER_EXCEPTION" not in log_text
    assert sample_workflow.workflow_id not in log_text
    assert sample_workflow.inputs.resume_text not in log_text
    assert sample_workflow.inputs.job_description_text not in log_text


# -----------------------------------------------------------------------------
# Concurrency & Lock Resilience Tests
# -----------------------------------------------------------------------------

def test_21_concurrent_first_operations_construct_exactly_one_client(sample_workflow):
    """21. Verify concurrent threads calling operations construct the client exactly once."""
    import concurrent.futures
    import threading
    import time

    num_threads = 10
    barrier = threading.Barrier(num_threads)
    client_creations = 0
    fake_client = FakeFirestoreClient()

    def client_factory():
        nonlocal client_creations
        client_creations += 1
        time.sleep(0.05)  # Enlarge race window
        return fake_client

    settings = Settings(
        persistence_backend="firestore",
        firestore_collection="concurrency_test",
    )
    repo = get_repository(settings=settings, client_factory=client_factory)

    results = []
    errors = []

    def worker_task(thread_id: int):
        try:
            barrier.wait(timeout=5.0)
            repo.save(sample_workflow)
            results.append(repo._client)
        except Exception as exc:
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_task, i) for i in range(num_threads)]
        concurrent.futures.wait(futures)

    assert not errors, f"Errors encountered during concurrent execution: {errors}"
    assert len(results) == num_threads
    assert client_creations == 1  # Factory invoked exactly once
    assert all(c is fake_client for c in results)  # All threads received identical instance


def test_22_client_factory_failure_releases_lock_and_does_not_deadlock(sample_workflow):
    """22. Verify client factory failures release the lock and do not deadlock subsequent calls."""
    should_fail = True
    fake_client = FakeFirestoreClient()

    def buggy_factory():
        nonlocal should_fail
        if should_fail:
            raise RuntimeError("503 Service Unavailable: Simulated Init Failure")
        return fake_client

    settings = Settings(
        persistence_backend="firestore",
        firestore_collection="deadlock_test",
    )
    repo = FirestoreWorkflowRepository(settings=settings, client_factory=buggy_factory)

    # First call should fail with sanitized category and release lock
    with pytest.raises(RuntimeError) as exc_info:
        repo.save(sample_workflow)
    assert "firestore_unavailable" in str(exc_info.value)

    # Second call after resolving failure condition should succeed without deadlock
    should_fail = False
    saved = repo.save(sample_workflow)
    assert saved.workflow_id == sample_workflow.workflow_id
    assert repo._client is fake_client
