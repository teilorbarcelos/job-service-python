"""Core abstractions for the job runner.

Exports the building blocks that every job and the scheduler itself depend on:
- BaseJob: the abstract class every job must extend
- JobContext, JobResult: data classes passed around the lifecycle
- Scheduler: orchestrates all jobs with cron + overlap + timeout protection
- CronAdapter, ScheduledTask: protocols for the cron library abstraction
- APSchedulerAdapter: the default (real) implementation
- SchedulerOptions, JobInfo: config + introspection
"""

from src.core.base_job import (
    BaseJob,
    JobContext,
    JobResult,
    JobStatus,
)
from src.core.scheduler import (
    APSchedulerAdapter,
    CronAdapter,
    JobInfo,
    ScheduledTask,
    Scheduler,
    SchedulerOptions,
)

__all__ = [
    "APSchedulerAdapter",
    "BaseJob",
    "CronAdapter",
    "JobContext",
    "JobInfo",
    "JobResult",
    "JobStatus",
    "ScheduledTask",
    "Scheduler",
    "SchedulerOptions",
]
