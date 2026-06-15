import logging
from unittest.mock import patch
from src.shared.utils.logging import get_logger, _add_context


def test_add_context_adds_request_id():
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    result = _add_context(record)
    assert hasattr(result, "request_id")


def test_add_context_does_not_overwrite_existing():
    record = logging.LogRecord("test", logging.INFO, "", 0, "msg", (), None)
    record.request_id = "existing-id"
    result = _add_context(record)
    assert result.request_id == "existing-id"


def test_get_logger_returns_logger():
    logger = get_logger("test_logger")
    assert logger.name == "test_logger"
    assert logger.level == logging.NOTSET


def test_get_logger_reuses_existing_handlers():
    logger1 = get_logger("test_reuse")
    logger2 = get_logger("test_reuse")
    assert logger1 is logger2
