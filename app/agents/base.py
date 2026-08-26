"""Base class and interface for specialist workflow agents."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """Abstract base class for all specialist agents."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name identifier of the specialist agent."""
        pass

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the agent task deterministically."""
        pass
