"""Google Cloud Firestore repository for workflow persistence."""

import logging
import threading
from typing import Any, Callable, List, Optional
from pydantic import ValidationError

from app.models import WorkflowResult
from app.repositories.base import BaseWorkflowRepository
from app.settings import Settings, get_settings

logger = logging.getLogger("fitforge.repository.firestore")


def categorize_firestore_error(exc: Exception) -> str:
    """Classify Firestore provider exceptions into sanitized, stable error categories."""
    err_str = str(exc).lower()
    err_type = type(exc).__name__.lower()

    if any(k in err_str or k in err_type for k in ["unauthenticated", "auth", "invalid credential", "401"]):
        return "firestore_authentication_failed"
    if any(k in err_str or k in err_type for k in ["permission", "forbidden", "accessdenied", "403"]):
        return "firestore_permission_denied"
    if any(k in err_str or k in err_type for k in ["notfound", "not_found", "404"]):
        return "firestore_not_found"
    if any(k in err_str or k in err_type for k in ["unavailable", "503", "connection", "socket", "network"]):
        return "firestore_unavailable"
    if any(k in err_str or k in err_type for k in ["deadline", "timeout", "timeouterror", "504"]):
        return "firestore_timeout"
    if any(k in err_str or k in err_type for k in ["validation", "invalid", "corrupt", "unsupported"]):
        return "firestore_data_invalid"
    return "firestore_operation_failed"


class FirestoreWorkflowRepository(BaseWorkflowRepository):
    """Google Cloud Firestore persistence implementation for FitForge workflows."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[Any] = None,
        client_factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self._client_factory = client_factory
        self._client_lock = threading.Lock()
        self.collection_name = self.settings.firestore_collection

    def _get_client(self) -> Any:
        """Lazily initialize the Firestore client with double-checked thread-safe locking."""
        if self._client is not None:
            return self._client

        with self._client_lock:
            if self._client is not None:
                return self._client

            if self._client_factory is not None:
                try:
                    self._client = self._client_factory()
                    return self._client
                except Exception as exc:
                    category = categorize_firestore_error(exc)
                    logger.error("Firestore client initialization failed with category: %s", category)
                    raise RuntimeError(f"Firestore persistence failed: {category}") from None

            try:
                import google.cloud.firestore as firestore
                self._client = firestore.Client(
                    project=self.settings.google_cloud_project,
                    database=self.settings.firestore_database,
                )
                return self._client
            except Exception as exc:
                category = categorize_firestore_error(exc)
                logger.error("Firestore client initialization failed with category: %s", category)
                raise RuntimeError(f"Firestore persistence failed: {category}") from None

    def save(self, workflow: WorkflowResult) -> WorkflowResult:
        """Persist or update a workflow document in Firestore."""
        doc_id = workflow.workflow_id
        try:
            client = self._get_client()
            payload = workflow.model_dump(mode="json")
            client.collection(self.collection_name).document(doc_id).set(payload)
            logger.info("Firestore operation 'save' succeeded")
            return workflow
        except Exception as exc:
            category = categorize_firestore_error(exc)
            logger.error("Firestore operation 'save' failed with category: %s", category)
            raise RuntimeError(f"Firestore persistence failed: {category}") from None

    def get(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Retrieve and reconstruct a workflow document from Firestore by ID."""
        try:
            client = self._get_client()
            doc_ref = client.collection(self.collection_name).document(workflow_id)
            snapshot = doc_ref.get()

            # Handle both real Firestore DocumentSnapshot and test mock snapshots
            exists = getattr(snapshot, "exists", None)
            if exists is False:
                logger.info("Firestore operation 'get' succeeded (document not found)")
                return None

            to_dict_fn = getattr(snapshot, "to_dict", None)
            data = to_dict_fn() if callable(to_dict_fn) else None

            if not data:
                logger.info("Firestore operation 'get' succeeded (document empty)")
                return None

            result = WorkflowResult.model_validate(data)
            logger.info("Firestore operation 'get' succeeded")
            return result
        except ValidationError as val_err:
            logger.error("Firestore operation 'get' failed with category: firestore_data_invalid")
            raise RuntimeError("Firestore persistence failed: firestore_data_invalid") from None
        except Exception as exc:
            category = categorize_firestore_error(exc)
            logger.error("Firestore operation 'get' failed with category: %s", category)
            raise RuntimeError(f"Firestore persistence failed: {category}") from None

    def list_all(self) -> List[WorkflowResult]:
        """List and reconstruct all stored workflows."""
        try:
            client = self._get_client()
            docs = client.collection(self.collection_name).stream()
            results = []
            for doc in docs:
                data = doc.to_dict() if callable(getattr(doc, "to_dict", None)) else None
                if data:
                    try:
                        results.append(WorkflowResult.model_validate(data))
                    except ValidationError:
                        continue
            logger.info("Firestore operation 'list_all' succeeded")
            return results
        except Exception as exc:
            category = categorize_firestore_error(exc)
            logger.error("Firestore operation 'list_all' failed with category: %s", category)
            raise RuntimeError(f"Firestore persistence failed: {category}") from None

    def clear(self) -> None:
        """Delete all documents in the configured collection (for test fixtures)."""
        try:
            client = self._get_client()
            docs = client.collection(self.collection_name).stream()
            for doc in docs:
                doc.reference.delete()
            logger.info("Firestore operation 'clear' succeeded")
        except Exception as exc:
            category = categorize_firestore_error(exc)
            logger.error("Firestore operation 'clear' failed with category: %s", category)
            raise RuntimeError(f"Firestore persistence failed: {category}") from None
