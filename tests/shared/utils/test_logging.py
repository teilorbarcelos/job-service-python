"""Tests for the JSON logger setup and helpers."""

from __future__ import annotations

import json
import logging

import pytest

from src.shared.utils.logging import JsonFormatter, get_logger, setup_logging


def teardown_function() -> None:
    """Reset root logger handlers between tests."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.setLevel(logging.WARNING)


def test_setup_logging_replaces_handlers() -> None:
    setup_logging("INFO")
    setup_logging("DEBUG")
    assert len(logging.getLogger().handlers) == 1


def test_setup_logging_sets_level() -> None:
    setup_logging("WARNING")
    assert logging.getLogger().level == logging.WARNING


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("my.module")
    assert logger.name == "my.module"
    assert isinstance(logger, logging.Logger)


def test_json_formatter_emits_required_fields() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    output = formatter.format(record)
    payload = json.loads(output)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "x"
    assert payload["message"] == "hello"
    assert "timestamp" in payload


def test_json_formatter_includes_exception() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="x",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
        output = formatter.format(record)
    payload = json.loads(output)
    assert payload["level"] == "ERROR"
    assert "exception" in payload
    assert "ValueError" in payload["exception"]
    assert "boom" in payload["exception"]


def test_json_formatter_includes_extra_fields() -> None:
    setup_logging("INFO")
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="with extra",
        args=(),
        exc_info=None,
    )
    record.job_name = "cleanup"
    record.duration_ms = 42
    payload = json.loads(formatter.format(record))
    assert payload["job_name"] == "cleanup"
    assert payload["duration_ms"] == 42


def test_json_formatter_skips_reserved_attrs() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="plain message",
        args=(),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert "name" not in payload
    assert "msg" not in payload
    assert "args" not in payload
    assert "levelname" not in payload


def test_get_logger_used_after_setup_emits_json_to_stdout(capsys: pytest.CaptureFixture) -> None:
    setup_logging("INFO")
    get_logger("json.test").info("hello stdout")
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["message"] == "hello stdout"
    assert payload["logger"] == "json.test"
    assert payload["level"] == "INFO"
