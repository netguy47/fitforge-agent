"""Base repository interface for workflow persistence."""

from abc import ABC, abstractmethod
from typing import List, Optional
from app.models import WorkflowResult


class BaseWorkflowRepository(ABC):
    """Abstract interface defining required repository persistence operations."""

    @abstractmethod
    def save(self, workflow: WorkflowResult) -> WorkflowResult:
        """Persist or update a workflow instance."""
        pass

    @abstractmethod
    def get(self, workflow_id: str) -> Optional[WorkflowResult]:
        """Retrieve a workflow instance by ID, returning None if not found."""
        pass

    @abstractmethod
    def list_all(self) -> List[WorkflowResult]:
        """List all stored workflow instances."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored workflows (used primarily for test isolation)."""
        pass
