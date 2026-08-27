"""Repository factory with thread-safe application-scoped caching."""

import threading
from typing import Any, Callable, Dict, Optional, Tuple

from app.repositories.base import BaseWorkflowRepository
from app.repositories.firestore import FirestoreWorkflowRepository
from app.repositories.in_memory import InMemoryWorkflowRepository
from app.settings import Settings, get_settings

# Thread lock for cache synchronization
_cache_lock = threading.Lock()

# Application-scoped repository cache keyed by configuration tuple
_repository_cache: Dict[Tuple[str, Optional[str], str, str], BaseWorkflowRepository] = {}

# Stable default in-memory repository instance
_default_in_memory_repo = InMemoryWorkflowRepository()

# Optional global override for test injection
_active_override_repo: Optional[BaseWorkflowRepository] = None


def _make_cache_key(settings: Settings) -> Tuple[str, Optional[str], str, str]:
    """Generate a canonical cache key from settings."""
    return (
        settings.persistence_backend,
        settings.google_cloud_project,
        settings.firestore_database,
        settings.firestore_collection,
    )


def set_repository_override(repo: Optional[BaseWorkflowRepository]) -> None:
    """Set or clear a global repository override for test isolation."""
    global _active_override_repo
    with _cache_lock:
        _active_override_repo = repo


def reset_repository_cache() -> None:
    """Reset repository cache and overrides (used for test isolation)."""
    global _active_override_repo
    with _cache_lock:
        _active_override_repo = None
        _repository_cache.clear()
        _default_in_memory_repo.clear()


def get_repository(
    settings: Optional[Settings] = None,
    client: Optional[Any] = None,
    client_factory: Optional[Callable[[], Any]] = None,
) -> BaseWorkflowRepository:
    """Resolve, cache, and return the configured repository implementation."""
    global _active_override_repo

    # Check for active test override first (without touching settings or building clients)
    with _cache_lock:
        if _active_override_repo is not None:
            return _active_override_repo

    active_settings = settings or get_settings()

    if active_settings.is_in_memory_persistence:
        return _default_in_memory_repo

    cache_key = _make_cache_key(active_settings)

    with _cache_lock:
        # Check if already cached (and if not overriding client in test)
        if cache_key in _repository_cache and client is None and client_factory is None:
            return _repository_cache[cache_key]

        # Construct new repository instance (client creation remains lazy inside repo)
        repo = FirestoreWorkflowRepository(
            settings=active_settings,
            client=client,
            client_factory=client_factory,
        )
        _repository_cache[cache_key] = repo
        return repo
