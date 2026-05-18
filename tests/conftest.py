"""Shared fixtures and helpers for the test suite."""

from __future__ import annotations

import time

import pytest


@pytest.fixture
def wait_for_exit():
    """Return an awaitable that drives pilot ticks until app exit, or timeout.

    Replaces the duplicated `for _ in range(N): await pilot.pause()` loop.
    """

    async def _wait(app, pilot, timeout: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        while app.is_running:
            if time.monotonic() > deadline:
                return
            await pilot.pause()

    return _wait
