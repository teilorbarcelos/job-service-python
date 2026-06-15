import asyncio
import logging

import pytest

from src.core.base_job import BaseJob, JobContext


class _NoopJob(BaseJob):
    name = "noop"
    schedule = "* * * * *"
    description = "A job that does nothing"

    async def handle(self, context: JobContext) -> None:
        return None


class _ErrorJob(BaseJob):
    name = "error-job"
    schedule = "* * * * *"
    description = "A job that raises"

    async def handle(self, context: JobContext) -> None:
        raise RuntimeError("boom")


def test_base_job_exposes_name_schedule_description() -> None:
    job = _NoopJob()
    assert job.name == "noop"
    assert job.schedule == "* * * * *"
    assert job.description == "A job that does nothing"
    assert job.enabled is True


def test_base_job_can_be_disabled() -> None:
    job = _NoopJob()
    job.enabled = False
    assert job.enabled is False


def test_base_job_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseJob()  # type: ignore[abstract]


def test_base_job_logger_uses_name() -> None:
    job = _NoopJob()
    assert job.logger.name == "job.noop"


def test_run_returns_success_when_handle_succeeds(caplog: pytest.LogCaptureFixture) -> None:
    job = _NoopJob()
    signal = asyncio.Event()
    with caplog.at_level(logging.INFO, logger="job.noop"):
        result = asyncio.run(job.run(signal))
    assert result.status == "success"
    assert result.job == "noop"
    assert result.error is None
    assert result.duration_ms >= 0
    assert "Starting job noop" in caplog.text
    assert "finished" in caplog.text


def test_run_returns_skipped_when_disabled(caplog: pytest.LogCaptureFixture) -> None:
    job = _NoopJob()
    job.enabled = False
    signal = asyncio.Event()
    with caplog.at_level(logging.DEBUG, logger="job.noop"):
        result = asyncio.run(job.run(signal))
    assert result.status == "skipped"
    assert result.duration_ms == 0
    assert result.error is None
    assert "Job disabled" in caplog.text
    assert "Starting job" not in caplog.text


def test_run_returns_error_when_handle_raises_exception(caplog: pytest.LogCaptureFixture) -> None:
    job = _ErrorJob()
    signal = asyncio.Event()
    with caplog.at_level(logging.ERROR, logger="job.error-job"):
        result = asyncio.run(job.run(signal))
    assert result.status == "error"
    assert result.job == "error-job"
    assert result.error == "boom"
    assert result.duration_ms >= 0
    assert "Job error-job failed: boom" in caplog.text


def test_run_does_not_catch_baseexception_subclasses() -> None:
    class _SystemExitJob(BaseJob):
        name = "system-exit-job"
        schedule = "* * * * *"
        description = "Raises SystemExit"

        async def handle(self, context: JobContext) -> None:
            raise SystemExit(1)

    job = _SystemExitJob()
    with pytest.raises(SystemExit):
        asyncio.run(job.run(asyncio.Event()))


def test_run_passes_context_with_logger_and_signal() -> None:
    received: list[JobContext] = []

    class _CaptureJob(BaseJob):
        name = "capture"
        schedule = "* * * * *"
        description = "Captures context"

        async def handle(self, context: JobContext) -> None:
            received.append(context)

    job = _CaptureJob()
    signal = asyncio.Event()
    asyncio.run(job.run(signal))
    assert len(received) == 1
    assert received[0].logger.name == "job.capture"
    assert received[0].signal is signal


def test_run_measures_duration_even_on_error() -> None:
    class _SlowErrorJob(BaseJob):
        name = "slow-error"
        schedule = "* * * * *"
        description = "Takes a while then errors"

        async def handle(self, context: JobContext) -> None:
            await asyncio.sleep(0.01)
            raise RuntimeError("late")

    job = _SlowErrorJob()
    result = asyncio.run(job.run(asyncio.Event()))
    assert result.status == "error"
    assert result.duration_ms >= 10
