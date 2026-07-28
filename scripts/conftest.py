"""Pytest options and fixtures shared by the scripts/ test suite."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

DOCS = Path(__file__).parent.parent / "docs"


def pytest_addoption(parser) -> None:
    parser.addoption("--snapshot-update", action="store_true",
                     help="Rewrite the rendered baseline instead of asserting against it")


def _pick_free_port() -> int:
    """Ask the OS for an unused TCP port instead of hardcoding one.

    A hardcoded port can collide with an unrelated process already bound to
    it (observed during development: stray http.server processes lingering
    on a fixed port), causing confusing failures or a false pass against
    the wrong server.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    """Poll until something accepts TCP connections on host:port.

    A fixed sleep proved flaky in this environment (the child http.server
    process can take longer than 1.5s to start accepting connections under
    pytest), so we poll instead of guessing a delay.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1.0)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.2)
    raise RuntimeError(f"server on {host}:{port} did not become reachable within {timeout}s")


@pytest.fixture(scope="session")
def server():
    """Serve docs/ over HTTP for the browser-driven frontend tests.

    Session-scoped because several test modules need it and starting one
    http.server per module is pure overhead — the server is read-only and
    holds no per-test state.
    """
    port = _pick_free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(port), "-d", str(DOCS)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port("127.0.0.1", port)
    except RuntimeError:
        proc.terminate()
        proc.wait(timeout=5)
        raise
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=5)
