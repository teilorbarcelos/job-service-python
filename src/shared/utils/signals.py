r"""Async timeout helpers.

The Scheduler uses \`asyncio.wait_for\` internally to enforce per-job
timeouts. This module provides a thin wrapper that's easier to test
and that returns an explicit \`asyncio.TimeoutError\` on expiration.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


async def wait_with_timeout[T](coro: Awaitable[T], timeout_s: float) -> T:
    r"""Await `coro` with a hard timeout.

    Returns the coroutine's result. Raises `asyncio.TimeoutError` if
    the timeout expires before the coroutine completes.
    """
    return await asyncio.wait_for(coro, timeout=timeout_s)
