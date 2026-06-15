from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Protocol

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.core.base_job import BaseJob


class ScheduledTask(Protocol):
    def stop(self) -> None: ...


class CronAdapter(Protocol):
    def validate(self, expression: str) -> bool: ...
    def schedule(self, expression: str, callback: Callable[[], Coroutine]) -> ScheduledTask: ...
    def start(self) -> None: ...
    def shutdown(self) -> None: ...


class APSchedulerAdapter:
    def __init__(self) -> None:
        self._scheduler: AsyncIOScheduler = AsyncIOScheduler()
        self._started: bool = False

    def validate(self, expression: str) -> bool:
        try:
            CronTrigger.from_crontab(expression)
            return True
        except (ValueError, TypeError):
            return False

    def schedule(self, expression: str, callback: Callable[[], Coroutine]) -> ScheduledTask:
        trigger = CronTrigger.from_crontab(expression)
        apscheduler_job = self._scheduler.add_job(callback, trigger)
        return _APSchedulerTask(scheduler=self._scheduler, job_id=apscheduler_job.id)

    def start(self) -> None:
        if not self._started:
            self._scheduler.start()
            self._started = True

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown()
            self._started = False


class _APSchedulerTask:
    def __init__(self, scheduler: AsyncIOScheduler, job_id: str) -> None:
        self._scheduler = scheduler
        self._job_id = job_id

    def stop(self) -> None:
        try:
            self._scheduler.remove_job(self._job_id)
        except Exception:
            pass


@dataclass(frozen=True)
class JobInfo:
    name: str
    schedule: str
    enabled: bool
    description: str


@dataclass(frozen=True)
class SchedulerOptions:
    cron: CronAdapter | None = None
    execution_timeout_s: float = 300.0


class Scheduler:
    def __init__(self, jobs: list[BaseJob], options: SchedulerOptions | None = None) -> None:
        opts = options or SchedulerOptions()
        self._jobs: dict[str, BaseJob] = {}
        self._tasks: dict[str, ScheduledTask] = {}
        self._callbacks: dict[str, Callable[[], Coroutine]] = {}
        self._running: set[str] = set()
        self._cron: CronAdapter = opts.cron or APSchedulerAdapter()
        self._execution_timeout_s: float = opts.execution_timeout_s
        self._logger = logging.getLogger("scheduler")

        for job in jobs:
            if job.name in self._jobs:
                raise ValueError(f"Duplicate job name: {job.name}")
            self._jobs[job.name] = job

    def start(self) -> None:
        for name, job in self._jobs.items():
            if not job.enabled:
                self._logger.info("Job %s disabled, will not be scheduled", name)
                continue
            if not self._cron.validate(job.schedule):
                message = f"Invalid cron expression for job {name}: {job.schedule}"
                self._logger.error(message)
                raise ValueError(message)

            callback = self._make_callback(name)
            task = self._cron.schedule(job.schedule, callback)
            self._tasks[name] = task
            self._callbacks[name] = callback
            self._logger.info(
                "Job %s scheduled (%s): %s", name, job.schedule, job.description
            )
        self._cron.start()

    def stop(self) -> None:
        for name, task in self._tasks.items():
            task.stop()
            self._logger.info("Job %s stopped", name)
        self._tasks.clear()
        self._callbacks.clear()
        self._cron.shutdown()

    def list_jobs(self) -> list[JobInfo]:
        return [
            JobInfo(
                name=j.name,
                schedule=j.schedule,
                enabled=j.enabled,
                description=j.description,
            )
            for j in self._jobs.values()
        ]

    def is_running(self, name: str) -> bool:
        return name in self._running

    async def wait_for_running_jobs(self) -> None:
        while self._running:
            await asyncio.sleep(0.05)

    def _make_callback(self, name: str) -> Callable[[], Coroutine]:
        async def callback() -> None:
            await self._execute(name)

        return callback

    async def _execute(self, name: str) -> None:
        if name in self._running:
            self._logger.warning("Job %s still running, skipping this iteration", name)
            return
        job = self._jobs.get(name)
        if job is None:
            self._logger.error("Job %s not found in registry", name)
            return
        self._running.add(name)
        signal = asyncio.Event()
        try:
            await asyncio.wait_for(job.run(signal), timeout=self._execution_timeout_s)
        except TimeoutError:
            signal.set()
            self._logger.warning(
                "Job %s exceeded execution timeout of %ss",
                name,
                self._execution_timeout_s,
            )
        finally:
            self._running.discard(name)
