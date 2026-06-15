r"""Signal-based graceful shutdown.

Installs SIGTERM/SIGINT handlers on the running event loop. When a
signal arrives, the handler schedules the user-supplied async
`cleanup` coroutine. If the cleanup doesn't complete within
`settings.shutdown_timeout_s`, the process is stopped with an error
log.

When the `PYTEST_CURRENT_TEST` env var is set (always true under
pytest), the handlers are NOT installed — tests control lifecycle
explicitly. The \`_is_test_mode()\` helper is a function (not an inline
check) so tests can patch it via \`mocker.patch\`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import Awaitable, Callable

from src.shared.config.settings import settings

logger = logging.getLogger("shutdown")


def _is_test_mode() -> bool:
    return "PYTEST_CURRENT_TEST" in os.environ


async def _run_with_timeout(
    handler: Callable[[], Awaitable[None]],
    loop: asyncio.AbstractEventLoop,
    timeout_s: float,
) -> None:
    try:
        await asyncio.wait_for(handler(), timeout=timeout_s)
        logger.info("[Shutdown] Cleanup complete")
    except TimeoutError:
        logger.error(
            "[Shutdown] Cleanup exceeded %ss timeout, forcing exit", timeout_s
        )
    except Exception as exc:
        logger.error("[Shutdown] Error during cleanup: %s", exc, exc_info=exc)
    finally:
        loop.stop()


def register_shutdown_handlers(handler: Callable[[], Awaitable[None]]) -> None:
    r"""Install SIGTERM/SIGINT handlers that run \`handler()\` then stop the loop.

    In test environments (\`_is_test_mode()\` returns True) this is a no-op.
    """
    if _is_test_mode():
        return

    loop = asyncio.get_event_loop()

    def _on_signal(sig: signal.Signals) -> None:
        logger.info("[Shutdown] Signal %s received, starting graceful shutdown", sig.name)
        loop.create_task(
            _run_with_timeout(handler, loop, settings.shutdown_timeout_s)
        )

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _on_signal, sig)
        except NotImplementedError:
            signal.signal(sig, lambda s, f: _on_signal(signal.Signals(s)))
