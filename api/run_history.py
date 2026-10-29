"""Bounded process-local history for jobs and webhook deliveries."""

import asyncio
import time
from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime

from .logging_config import request_id
from .schemas import JobRun


class RunHistory:
    def __init__(self, limit: int = 200):
        self._runs: deque[JobRun] = deque(maxlen=limit)

    def all(self) -> list[JobRun]:
        return list(reversed(self._runs))

    @contextmanager
    def track(self, job: str, trigger: str, target: str | None = None):
        run = JobRun(
            job=job,
            trigger=trigger,
            target=target,
            started_at=datetime.now(UTC),
            request_id=request_id.get(),
        )
        started = time.monotonic()
        try:
            yield run
        except asyncio.CancelledError:
            run.result = "cancelled"
            raise
        except Exception as error:
            run.result = "error"
            run.error = type(error).__name__
            raise
        finally:
            run.duration_seconds = time.monotonic() - started
            self._runs.append(run)


run_history = RunHistory()
