"""Tests for the central job registration."""

from __future__ import annotations

import pytest

from src.core import Scheduler
from src.jobs.register_jobs import register_jobs as register_jobs_fn


def test_register_jobs_returns_scheduler_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = register_jobs_fn()
    assert isinstance(scheduler, Scheduler)


def test_register_jobs_includes_health_check_job(monkeypatch: pytest.MonkeyPatch) -> None:
    scheduler = register_jobs_fn()
    job_names = [j.name for j in scheduler.list_jobs()]
    assert "health-check" in job_names


def test_register_jobs_uses_health_check_cron_from_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTH_CHECK_CRON", "0 12 * * *")
    from src.shared.config import settings as settings_module
    from src.shared.config.settings import build_settings

    settings_module.settings = build_settings()

    scheduler = register_jobs_fn()
    health = next(j for j in scheduler.list_jobs() if j.name == "health-check")
    assert health.schedule == "0 12 * * *"


def test_register_jobs_respects_health_check_enabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEALTH_CHECK_ENABLED", "false")
    from src.shared.config import settings as settings_module
    from src.shared.config.settings import build_settings

    settings_module.settings = build_settings()

    scheduler = register_jobs_fn()
    health = next(j for j in scheduler.list_jobs() if j.name == "health-check")
    assert health.enabled is False
