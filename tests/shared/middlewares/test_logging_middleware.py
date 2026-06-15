import json
import logging
import pytest
from src.shared.middlewares.logging_middleware import JSONFormatter, get_request_id, get_user_id


def test_get_request_id_default():
    assert get_request_id() == ""


def test_get_user_id_default():
    assert get_user_id() == ""


def test_json_formatter_with_args():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test %s",
        args=("arg_value",),
        exc_info=None,
    )
    output = formatter.format(record)
    data = json.loads(output)
    assert data["message"] == "test arg_value"
    assert data["args"] == "('arg_value',)"


def test_json_formatter_with_exception():
    import traceback

    formatter = JSONFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        exc_info = traceback.format_exc()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error occurred",
            args=(),
            exc_info=(ValueError, ValueError("test error"), None),
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert "exception" in data
        assert "ValueError" in data["exception"]


def test_json_formatter_with_extra_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="with extra",
        args=(),
        exc_info=None,
    )
    record.extra_fields = {"custom": "value"}
    output = formatter.format(record)
    data = json.loads(output)
    assert data["custom"] == "value"
