"""Tests for the shutdown module."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from unittest.mock import MagicMock

import pytest

from src.shared.utils import shutdown


def test_register_shutdown_handlers_is_noop_in_test_mode(
    mocker: pytest.MockerFixture,
) -> None:
    mocker.patch("src.shared.utils.shutdown._is_test_mode", return_value=True)
    loop_mock = MagicMock()
    mocker.patch("src.shared.utils.shutdown.asyncio.get_event_loop", return_value=loop_mock)
    shutdown.register_shutdown_handlers(handler=MagicMock())
    loop_mock.add_signal_handler.assert_not_called()


def test_register_shutdown_handlers_registers_sigterm_and_sigint(
    mocker: pytest.MockerFixture,
) -> None:
    mocker.patch("src.shared.utils.shutdown._is_test_mode", return_value=False)
    loop_mock = MagicMock()
    mocker.patch("src.shared.utils.shutdown.asyncio.get_event_loop", return_value=loop_mock)
    shutdown.register_shutdown_handlers(handler=MagicMock())
    assert loop_mock.add_signal_handler.call_count == 2
    registered = {call.args[0] for call in loop_mock.add_signal_handler.call_args_list}
    assert registered == {signal.SIGTERM, signal.SIGINT}


def test_register_shutdown_handlers_falls_back_to_signal_when_add_signal_handler_not_implemented(
    mocker: pytest.MockerFixture,
) -> None:
    mocker.patch("src.shared.utils.shutdown._is_test_mode", return_value=False)
    loop_mock = MagicMock()
    loop_mock.add_signal_handler.side_effect = NotImplementedError
    mocker.patch("src.shared.utils.shutdown.asyncio.get_event_loop", return_value=loop_mock)
    signal_signal = mocker.patch("src.shared.utils.shutdown.signal.signal")
    shutdown.register_shutdown_handlers(handler=MagicMock())
    assert signal_signal.call_count == 2


def test_signal_handler_invokes_async_cleanup(
    mocker: pytest.MockerFixture,
) -> None:
    mocker.patch("src.shared.utils.shutdown._is_test_mode", return_value=False)
    loop_mock = MagicMock()
    mocker.patch("src.shared.utils.shutdown.asyncio.get_event_loop", return_value=loop_mock)
    shutdown.register_shutdown_handlers(handler=MagicMock())
    signal_handler = loop_mock.add_signal_handler.call_args_list[0].args[1]
    signal_handler(signal.SIGTERM)
    loop_mock.create_task.assert_called_once()


def test_is_test_mode_returns_true_when_pytest_current_test_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert shutdown._is_test_mode() is True


def test_is_test_mode_returns_false_when_pytest_current_test_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ.pop("PYTEST_CURRENT_TEST", None)
    assert shutdown._is_test_mode() is False


@pytest.mark.asyncio
async def test_run_with_timeout_stops_loop_on_success(
    mocker: pytest.MockerFixture,
) -> None:
    loop_mock = MagicMock()
    completed = False

    async def handler() -> None:
        nonlocal completed
        completed = True

    await shutdown._run_with_timeout(handler=handler, loop=loop_mock, timeout_s=1.0)
    assert completed is True
    loop_mock.stop.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_timeout_stops_loop_on_error(
    mocker: pytest.MockerFixture,
) -> None:
    loop_mock = MagicMock()

    async def handler() -> None:
        raise RuntimeError("cleanup fail")

    await shutdown._run_with_timeout(handler=handler, loop=loop_mock, timeout_s=1.0)
    loop_mock.stop.assert_called_once()


@pytest.mark.asyncio
async def test_run_with_timeout_stops_loop_on_timeout(
    mocker: pytest.MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    loop_mock = MagicMock()

    async def slow() -> None:
        await asyncio.sleep(2.0)

    with caplog.at_level(logging.ERROR, logger="shutdown"):
        await shutdown._run_with_timeout(handler=slow, loop=loop_mock, timeout_s=0.01)
    loop_mock.stop.assert_called_once()
    assert any("timeout" in m.lower() for m in caplog.messages)
