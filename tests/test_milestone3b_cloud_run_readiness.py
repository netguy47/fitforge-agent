"""Milestone 3B Tests: Offline Cloud Run Readiness & Runtime Validation.

Verified Constraints:
1. Dockerfile does not contain hardcoded API keys or secrets.
2. Dockerfile binds server host to 0.0.0.0.
3. Dockerfile uses dynamic environment variable expansion ${PORT:-8080}.
4. Default container exposed port is 8080 (not hardcoded to 8000).
5. .dockerignore excludes secrets (.env), virtual environments (.venv), git metadata, caches, tests, and archives.
6. Runtime validation rejects Firestore mode when GOOGLE_CLOUD_PROJECT is missing.
7. Runtime validation rejects Gemini mode when GEMINI_API_KEY credential is missing.
8. Runtime validation succeeds when valid Firestore and Gemini configurations are provided.
"""

from pathlib import Path
import pytest
from app.settings import Settings


REPO_ROOT = Path(__file__).parent.parent


def test_dockerfile_does_not_contain_secrets():
    """Verify Dockerfile does not contain hardcoded API keys, tokens, or credentials."""
    dockerfile_path = REPO_ROOT / "Dockerfile"
    assert dockerfile_path.exists(), "Dockerfile must exist at repository root."

    content = dockerfile_path.read_text(encoding="utf-8")
    lower_content = content.lower()

    # Check that secrets are not hardcoded
    assert "gemini_api_key" not in lower_content
    assert "google_api_key" not in lower_content
    assert "api_key=" not in lower_content
    assert "secret" not in lower_content
    assert "password" not in lower_content
    assert "bearer" not in lower_content


def test_dockerfile_uses_injected_port_and_binds_to_0_0_0_0():
    """Verify Dockerfile configures server for Cloud Run's injected PORT on 0.0.0.0."""
    dockerfile_path = REPO_ROOT / "Dockerfile"
    content = dockerfile_path.read_text(encoding="utf-8")

    assert "0.0.0.0" in content, "Dockerfile must bind host to 0.0.0.0."
    assert "${PORT:-8080}" in content or "$PORT" in content, "Dockerfile must use dynamic PORT environment variable."
    assert "EXPOSE 8080" in content, "Dockerfile must expose default container port 8080."
    assert "--port 8000" not in content, "Dockerfile must not hardcode port 8000 in CMD."


def test_dockerignore_excludes_secrets_and_local_artifacts():
    """Verify .dockerignore excludes secrets, venvs, caches, tests, and local build artifacts."""
    dockerignore_path = REPO_ROOT / ".dockerignore"
    assert dockerignore_path.exists(), ".dockerignore must exist at repository root."

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

    required_patterns = [
        ".git",
        ".venv",
        ".env",
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        "tests/",
        "*.zip",
        "*.log",
    ]

    for pattern in required_patterns:
        assert pattern in lines, f".dockerignore must contain pattern '{pattern}'."


def test_runtime_validation_rejects_firestore_mode_without_project(monkeypatch):
    """Verify runtime validation raises ValueError when PERSISTENCE_BACKEND='firestore' without GOOGLE_CLOUD_PROJECT."""
    monkeypatch.setenv("PERSISTENCE_BACKEND", "firestore")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)

    s = Settings.from_env()
    assert s.is_firestore_persistence is True
    assert s.google_cloud_project is None

    with pytest.raises(ValueError, match="GOOGLE_CLOUD_PROJECT environment variable is required"):
        s.validate_credentials()


def test_runtime_validation_rejects_gemini_mode_without_credential(monkeypatch):
    """Verify runtime validation raises ValueError when EXECUTION_MODE='gemini' without GEMINI_API_KEY."""
    monkeypatch.setenv("EXECUTION_MODE", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    s = Settings.from_env()
    assert s.is_gemini_mode is True
    assert s.gemini_api_key is None

    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is required"):
        s.validate_credentials()


def test_runtime_validation_accepts_valid_firestore_and_gemini_config(monkeypatch):
    """Verify runtime validation passes when valid Gemini key and GCP project are provided."""
    monkeypatch.setenv("EXECUTION_MODE", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-secure-test-key-12345")
    monkeypatch.setenv("PERSISTENCE_BACKEND", "firestore")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "fitforge-agent-2026")

    s = Settings.from_env()
    s.validate_credentials()  # Should not raise any error

    sanitized = s.sanitized_dict()
    assert sanitized["execution_mode"] == "gemini"
    assert sanitized["has_api_key"] is True
    assert sanitized["persistence_backend"] == "firestore"
    assert sanitized["google_cloud_project"] == "fitforge-agent-2026"
    assert "fake-secure-test-key-12345" not in str(sanitized)
