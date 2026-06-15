import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

JobStatus = Literal["success", "error", "skipped"]


@dataclass(frozen=True)
class JobContext:
    logger: logging.Logger
    signal: asyncio.Event


@dataclass
class JobResult:
    job: str
    status: JobStatus
    duration_ms: int
    error: str | None = None


class BaseJob(ABC):
    name: str = ""
    schedule: str = ""
    description: str = ""
    enabled: bool = True

    def __init__(self) -> None:
        self._logger = logging.getLogger(f"job.{self.name}")

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @abstractmethod
    async def handle(self, context: JobContext) -> None:
        ...

    async def run(self, signal: asyncio.Event) -> JobResult:
        if not self.enabled:
            self._logger.debug("Job disabled, skipping execution")
            return JobResult(job=self.name, status="skipped", duration_ms=0)

        started_at = time.monotonic()
        self._logger.info("Starting job %s", self.name)

        try:
            await self.handle(JobContext(logger=self._logger, signal=signal))
        except Exception as error:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            error_message = str(error)
            self._logger.error(
                "Job %s failed: %s", self.name, error_message, exc_info=error
            )
            return JobResult(
                job=self.name, status="error", duration_ms=duration_ms, error=error_message
            )

        duration_ms = int((time.monotonic() - started_at) * 1000)
        self._logger.info("Job %s finished in %dms", self.name, duration_ms)
        return JobResult(job=self.name, status="success", duration_ms=duration_ms)
