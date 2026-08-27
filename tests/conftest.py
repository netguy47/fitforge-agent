"""Pytest configuration and network isolation fixtures for FitForge Agent."""

import socket
import pytest

from app.rate_limiter import rate_limiter


@pytest.fixture(autouse=True)
def network_isolation_tripwire(monkeypatch):
    """Network isolation fixture blocking all external socket and HTTP connections.

    Permits only loopback (127.0.0.1, localhost, ::1). Any outbound network call
    to external hosts/APIs will immediately fail the test with an AssertionError.
    """
    orig_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        allowed_hosts = {"127.0.0.1", "localhost", "::1", 0, "0.0.0.0"}
        if isinstance(host, str) and host not in allowed_hosts and not host.startswith("127."):
            raise AssertionError(
                f"Network isolation tripwire triggered! Outbound connection attempted to unauthorized host: {host}"
            )
        return orig_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    yield


@pytest.fixture(autouse=True)
def reset_rate_limiter_state():
    """Reset rate limiter state before and after each test."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()
