"""In-memory repository for storing and retrieving workflow instances."""

from typing import Dict, List, Optional
from app.models import WorkflowResult
from app.repositories.base import BaseWorkflowRepository


class InMemoryWorkflowRepository(BaseWorkflowRepository):
    """Thread-safe in-memory storage for workflow state and audit history."""

    def __init__(self) -> None:
        self._storage: Dict[str, WorkflowResult] = {}

    def save(self, workflow: WorkflowResult) -> WorkflowResult:
        """Save or update a workflow instance."""
        self._storage[workflow.workflow_id] = workflow
        return workflow

    def get(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Retrieve a workflow by ID, returning a copy if present."""
        workflow = self._storage.get(workflow_id)
        if workflow is None:
            return None
        return workflow.model_copy(deep=True)

    def list_all(self) -> List[WorkflowResult]:
        """List all stored workflows."""
        return [w.model_copy(deep=True) for w in self._storage.values()]

    def clear(self) -> None:
        """Clear all stored workflows (primarily used in test fixtures)."""
        self._storage.clear()


# Backward compatibility aliases
WorkflowRepository = InMemoryWorkflowRepository
workflow_repo = InMemoryWorkflowRepository()
