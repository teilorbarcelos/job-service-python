"""Real APScheduler adapter tests (integration with the actual library)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine

import pytest

from src.core.base_job import BaseJob, JobContext
from src.core.scheduler import (
    APSchedulerAdapter,
    JobInfo,
    Scheduler,
    SchedulerOptions,
)


class _NoopJob(BaseJob):
    name = "noop"
    schedule = "*/5 * * * *"
    description = "Does nothing"

    async def handle(self, context: JobContext) -> None:
        return None


class _ErrorJob(BaseJob):
    name = "err"
    schedule = "*/5 * * * *"
    description = "Raises"

    async def handle(self, context: JobContext) -> None:
        raise RuntimeError("boom")


class _DisabledJob(BaseJob):
    name = "off"
    schedule = "*/5 * * * *"
    description = "Disabled"
    enabled = False

    async def handle(self, context: JobContext) -> None:
        return None


def test_apadapter_validate_accepts_valid_expression() -> None:
    adapter = APSchedulerAdapter()
    assert adapter.validate("*/5 * * * *") is True
    assert adapter.validate("0 0 * * *") is True


def test_apadapter_validate_rejects_invalid_expression() -> None:
    adapter = APSchedulerAdapter()
    assert adapter.validate("not-a-cron") is False
    assert adapter.validate("") is False


@pytest.mark.asyncio
async def test_apadapter_schedule_and_shutdown_lifecycle() -> None:
    adapter = APSchedulerAdapter()
    called: list[str] = []

    async def cb() -> None:
        called.append("ran")

    task = adapter.schedule("*/5 * * * *", cb)
    assert task is not None

    adapter.start()
    await asyncio.sleep(0.05)
    adapter.shutdown()


def test_apadapter_shutdown_when_not_started_is_noop() -> None:
    adapter = APSchedulerAdapter()
    adapter.shutdown()  # must not raise


def test_apscheduler_task_stop_swallows_exception_when_job_already_removed() -> None:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from src.core.scheduler import _APSchedulerTask

    scheduler = AsyncIOScheduler()
    task = _APSchedulerTask(scheduler=scheduler, job_id="nonexistent-id")
    task.stop()  # remove_job raises JobLookupError, swallowed by the except


class _RecordingCronAdapter:
    def __init__(self) -> None:
        self.validations: list[str] = []
        self.schedules: list[tuple[str, Callable[[], Coroutine]]] = []
        self.started: bool = False
        self.shutdown_called: bool = False
        self._task = _RecordingTask()

    def validate(self, expression: str) -> bool:
        self.validations.append(expression)
        return expression != "INVALID"

    def schedule(self, expression: str, callback: Callable[[], Coroutine]) -> _RecordingTask:
        self.schedules.append((expression, callback))
        return self._task

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.shutdown_called = True


class _RecordingTask:
    def __init__(self) -> None:
        self.stopped: bool = False

    def stop(self) -> None:
        self.stopped = True


def test_scheduler_rejects_duplicate_job_names() -> None:
    jobs = [_NoopJob(), _NoopJob()]
    with pytest.raises(ValueError, match="Duplicate job name"):
        Scheduler(jobs)


def test_scheduler_list_jobs_returns_all() -> None:
    scheduler = Scheduler([_NoopJob(), _ErrorJob()])
    assert scheduler.list_jobs() == [
        JobInfo(name="noop", schedule="*/5 * * * *", enabled=True, description="Does nothing"),
        JobInfo(name="err", schedule="*/5 * * * *", enabled=True, description="Raises"),
    ]


def test_scheduler_validates_each_job_on_start() -> None:
    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_NoopJob()], SchedulerOptions(cron=cron))
    scheduler.start()
    assert cron.validations == ["*/5 * * * *"]


def test_scheduler_skips_disabled_jobs() -> None:
    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_DisabledJob()], SchedulerOptions(cron=cron))
    scheduler.start()
    assert cron.schedules == []


def test_scheduler_raises_on_invalid_cron() -> None:
    class _BadJob(BaseJob):
        name = "bad"
        schedule = "INVALID"
        description = "Bad cron"

        async def handle(self, context: JobContext) -> None:
            return None

    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_BadJob()], SchedulerOptions(cron=cron))
    with pytest.raises(ValueError, match="Invalid cron expression for job bad"):
        scheduler.start()


def test_scheduler_schedules_enabled_jobs() -> None:
    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_NoopJob()], SchedulerOptions(cron=cron))
    scheduler.start()
    assert len(cron.schedules) == 1
    assert cron.schedules[0][0] == "*/5 * * * *"


def test_scheduler_stop_stops_each_task_and_shuts_down_cron() -> None:
    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_NoopJob(), _ErrorJob()], SchedulerOptions(cron=cron))
    scheduler.start()
    scheduler.stop()
    assert cron.shutdown_called is True
    assert cron._task.stopped is True
    assert scheduler._tasks == {}


@pytest.mark.asyncio
async def test_scheduler_execute_invokes_callback_that_runs_job() -> None:
    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_NoopJob()], SchedulerOptions(cron=cron))
    scheduler.start()
    callback = cron.schedules[0][1]
    await callback()
    assert scheduler.is_running("noop") is False  # cleared in finally


@pytest.mark.asyncio
async def test_scheduler_execute_skips_when_job_already_running() -> None:
    started = asyncio.Event()
    proceed = asyncio.Event()

    class _SlowJob(BaseJob):
        name = "slow"
        schedule = "*/5 * * * *"
        description = "Slow"

        async def handle(self, context: JobContext) -> None:
            started.set()
            await proceed.wait()

    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_SlowJob()], SchedulerOptions(cron=cron, execution_timeout_s=5.0))
    scheduler.start()
    callback = cron.schedules[0][1]

    first = asyncio.create_task(callback())
    await started.wait()
    await callback()  # overlap → skipped
    proceed.set()
    await first
    assert scheduler.is_running("slow") is False


@pytest.mark.asyncio
async def test_scheduler_execute_handles_missing_job() -> None:
    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_NoopJob()], SchedulerOptions(cron=cron))
    scheduler.start()

    async def _fake_callback() -> None:
        await scheduler._execute("ghost")  # noqa: SLF001

    await _fake_callback()
    assert scheduler.is_running("ghost") is False


@pytest.mark.asyncio
async def test_scheduler_execute_times_out_and_sets_signal(caplog: pytest.LogCaptureFixture) -> None:
    class _HangingJob(BaseJob):
        name = "hang"
        schedule = "*/5 * * * *"
        description = "Hangs"

        async def handle(self, context: JobContext) -> None:
            await context.signal.wait()
            raise RuntimeError("should not be reached normally")

    cron = _RecordingCronAdapter()
    scheduler = Scheduler(
        [_HangingJob()], SchedulerOptions(cron=cron, execution_timeout_s=0.05)
    )
    scheduler.start()
    callback = cron.schedules[0][1]

    with caplog.at_level(logging.WARNING, logger="scheduler"):
        await callback()

    assert any("exceeded execution timeout" in m for m in caplog.messages)
    assert scheduler.is_running("hang") is False


@pytest.mark.asyncio
async def test_scheduler_wait_for_running_jobs_blocks_until_done() -> None:
    started = asyncio.Event()
    proceed = asyncio.Event()

    class _Quick(BaseJob):
        name = "quick"
        schedule = "*/5 * * * *"
        description = "q"

        async def handle(self, context: JobContext) -> None:
            started.set()
            await proceed.wait()

    cron = _RecordingCronAdapter()
    scheduler = Scheduler([_Quick()], SchedulerOptions(cron=cron))
    scheduler.start()
    callback = cron.schedules[0][1]

    task = asyncio.create_task(callback())
    await started.wait()
    assert scheduler.is_running("quick") is True
    proceed.set()
    await scheduler.wait_for_running_jobs()
    await task
    assert scheduler.is_running("quick") is False
