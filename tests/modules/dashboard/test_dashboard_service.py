import pytest
import logging
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.modules.dashboard.dashboard_service import parse_start_date, parse_end_date, dashboard_service
from src.main import MetricsLogFilter


def test_parse_invalid_dates():

    start = parse_start_date("invalid-date")
    assert isinstance(start, datetime)

    end = parse_end_date("invalid-date")
    assert isinstance(end, datetime)


@pytest.mark.asyncio
async def test_dashboard_service_postgres_dialect():

    mock_session = AsyncMock()
    mock_session.bind = MagicMock()
    mock_session.bind.dialect = MagicMock()
    mock_session.bind.dialect.name = "postgresql"

    mock_result_users = MagicMock()
    mock_result_users.all.return_value = [MagicMock(date="2026-05-23", count=5)]

    mock_result_products = MagicMock()
    mock_result_products.all.return_value = [MagicMock(date="2026-05-23", count=10)]

    mock_result_per_user = MagicMock()
    mock_result_per_user.all.return_value = [MagicMock(userId="user-1", userName="User One", count=15)]

    mock_session.execute.side_effect = [mock_result_users, mock_result_products, mock_result_per_user]

    stats = await dashboard_service.get_stats(mock_session, "2026-05-01", "2026-05-31")

    assert len(stats.userCreationStats) == 1
    assert stats.userCreationStats[0].date == "2026-05-23"
    assert stats.userCreationStats[0].count == 5

    assert len(stats.productCreationStats) == 1
    assert stats.productCreationStats[0].date == "2026-05-23"
    assert stats.productCreationStats[0].count == 10

    assert len(stats.productsPerUser) == 1
    assert stats.productsPerUser[0].userId == "user-1"
    assert stats.productsPerUser[0].userName == "User One"
    assert stats.productsPerUser[0].count == 15

    assert mock_session.execute.call_count == 3


def test_metrics_log_filter():
    filt = MetricsLogFilter()

    rec1 = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "GET /metrics HTTP/1.1", (), None)
    assert filt.filter(rec1) is False

    rec2 = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "GET /v1/product HTTP/1.1", (), None)
    assert filt.filter(rec2) is True


def test_metric_service_no_labels():
    from src.infra.metrics.metric_service import metric_service

    metric_service.record_timer("test_timer_no_labels", 123.4)
