"""Central job registration.

Reads cron schedule and enabled-flag from settings, instantiates
each job with its dependencies, and returns a configured `Scheduler`.
"""

from __future__ import annotations

from src.core import Scheduler, SchedulerOptions
from src.infra.health.default_health_checker import DefaultHealthChecker
from src.jobs.health_check_job import HealthCheckJob
from src.shared.config import settings as settings_module


def register_jobs() -> Scheduler:
    """Instantiate every job and wrap them in a Scheduler."""
    # Read settings dynamically so tests can monkey-patch the module
    # attribute and have register_jobs see the new values.
    cfg = settings_module.settings

    health_check = HealthCheckJob(DefaultHealthChecker(), schedule=cfg.health_check_cron)
    health_check.enabled = cfg.health_check_enabled

    return Scheduler(
        [health_check],
        SchedulerOptions(execution_timeout_s=cfg.job_execution_timeout_s),
    )
