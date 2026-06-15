import logging

from src.shared.middlewares.logging_middleware import JSONFormatter, get_request_id, get_user_id


def _add_context(record: logging.LogRecord) -> logging.LogRecord:
    if not hasattr(record, "request_id"):
        record.request_id = get_request_id()
    if not hasattr(record, "user_id"):
        record.user_id = get_user_id()
    return record


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger
