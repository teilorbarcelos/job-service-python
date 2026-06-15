"""Tests for the wait_with_timeout helper."""

from __future__ import annotations

import asyncio

import pytest

from src.shared.utils.signals import wait_with_timeout


@pytest.mark.asyncio
async def test_wait_with_timeout_returns_when_coro_completes() -> None:
    async def quick() -> str:
        return "done"

    result = await wait_with_timeout(quick(), timeout_s=1.0)
    assert result == "done"


@pytest.mark.asyncio
async def test_wait_with_timeout_raises_timeout_error_on_expiration() -> None:
    async def slow() -> None:
        await asyncio.sleep(1.0)

    with pytest.raises(asyncio.TimeoutError):
        await wait_with_timeout(slow(), timeout_s=0.01)


@pytest.mark.asyncio
async def test_wait_with_timeout_propagates_coro_exception() -> None:
    async def fails() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        await wait_with_timeout(fails(), timeout_s=1.0)
