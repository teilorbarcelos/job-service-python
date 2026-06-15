"""Tests for the HealthCheckJob."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pytest

from src.core import JobContext
from src.jobs.health_check_job import HealthCheckJob, HealthCheckResult


@dataclass
class _FakeChecker:
    postgres: HealthCheckResult
    redis: HealthCheckResult
    rabbit: HealthCheckResult

    async def check_postgres(self) -> HealthCheckResult:
        return self.postgres

    async def check_redis(self) -> HealthCheckResult:
        return self.redis

    async def check_rabbitmq(self) -> HealthCheckResult:
        return self.rabbit


def _all_up() -> _FakeChecker:
    return _FakeChecker(
        postgres=HealthCheckResult(status="up", latency_ms=5),
        redis=HealthCheckResult(status="up", latency_ms=1),
        rabbit=HealthCheckResult(status="up"),
    )


def test_health_check_job_has_defaults() -> None:
    job = HealthCheckJob(checker=_all_up())
    assert job.name == "health-check"
    assert job.schedule == "*/1 * * * *"
    assert "PostgreSQL" in job.description
    assert "Redis" in job.description
    assert "RabbitMQ" in job.description
    assert job.enabled is True


def test_health_check_job_schedule_is_configurable() -> None:
    job = HealthCheckJob(checker=_all_up(), schedule="0 9 * * *")
    assert job.schedule == "0 9 * * *"


def test_health_check_job_can_be_disabled() -> None:
    job = HealthCheckJob(checker=_all_up())
    job.enabled = False
    assert job.enabled is False


@pytest.mark.asyncio
async def test_handle_reports_healthy_when_all_up(
    caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture
) -> None:
    import asyncio

    job = HealthCheckJob(checker=_all_up())
    logger = logging.getLogger("job.health-check")
    with caplog.at_level(logging.INFO, logger="job.health-check"):
        await job.handle(JobContext(logger=logger, signal=asyncio.Event()))
    assert any("healthy" in str(getattr(r, "msg", "")) or "healthy" in str(r.__dict__) for r in caplog.records)
    captured = capsys.readouterr()
    assert "postgres=up" in captured.out
    assert "redis=up" in captured.out
    assert "rabbitmq=up" in captured.out


@pytest.mark.asyncio
async def test_handle_reports_degraded_when_postgres_down(
    capsys: pytest.CaptureFixture,
) -> None:
    import asyncio

    checker = _FakeChecker(
        postgres=HealthCheckResult(status="down", error="conn refused"),
        redis=HealthCheckResult(status="up"),
        rabbit=HealthCheckResult(status="up"),
    )
    job = HealthCheckJob(checker=checker)
    logger = logging.getLogger("job.health-check")
    await job.handle(JobContext(logger=logger, signal=asyncio.Event()))
    captured = capsys.readouterr()
    assert "postgres=down" in captured.out


@pytest.mark.asyncio
async def test_handle_reports_degraded_when_redis_down(
    capsys: pytest.CaptureFixture,
) -> None:
    import asyncio

    checker = _FakeChecker(
        postgres=HealthCheckResult(status="up"),
        redis=HealthCheckResult(status="down", error="redis down"),
        rabbit=HealthCheckResult(status="up"),
    )
    job = HealthCheckJob(checker=checker)
    await job.handle(JobContext(logger=logging.getLogger("test"), signal=asyncio.Event()))
    captured = capsys.readouterr()
    assert "redis=down" in captured.out


@pytest.mark.asyncio
async def test_handle_reports_degraded_when_rabbit_down(
    capsys: pytest.CaptureFixture,
) -> None:
    import asyncio

    checker = _FakeChecker(
        postgres=HealthCheckResult(status="up"),
        redis=HealthCheckResult(status="up"),
        rabbit=HealthCheckResult(status="down", error="rabbit down"),
    )
    job = HealthCheckJob(checker=checker)
    await job.handle(JobContext(logger=logging.getLogger("test"), signal=asyncio.Event()))
    captured = capsys.readouterr()
    assert "rabbitmq=down" in captured.out


@pytest.mark.asyncio
async def test_handle_runs_all_three_checks_in_parallel() -> None:
    """If the checks were sequential, total time = sum. Parallel = max."""
    import asyncio

    class _SlowChecker:
        async def check_postgres(self) -> HealthCheckResult:
            await asyncio.sleep(0.05)
            return HealthCheckResult(status="up")

        async def check_redis(self) -> HealthCheckResult:
            await asyncio.sleep(0.05)
            return HealthCheckResult(status="up")

        async def check_rabbitmq(self) -> HealthCheckResult:
            await asyncio.sleep(0.05)
            return HealthCheckResult(status="up")

    job = HealthCheckJob(checker=_SlowChecker())
    start = asyncio.get_event_loop().time()
    await job.handle(JobContext(logger=logging.getLogger("test"), signal=asyncio.Event()))
    elapsed = asyncio.get_event_loop().time() - start
    # Parallel: ~0.05s. Sequential: ~0.15s. Allow generous margin.
    assert elapsed < 0.12


@pytest.mark.asyncio
async def test_handle_logs_event_with_status_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import asyncio

    job = HealthCheckJob(checker=_all_up())
    logger = logging.getLogger("job.health-check")
    with caplog.at_level(logging.INFO, logger="job.health-check"):
        await job.handle(JobContext(logger=logger, signal=asyncio.Event()))
    info_records = [r for r in caplog.records if r.levelname == "INFO"]
    assert len(info_records) >= 1
    record = info_records[0]
    msg = record.getMessage()
    assert "event" in msg or getattr(record, "event", None) == "health-check"
