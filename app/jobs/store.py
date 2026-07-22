"""
In-memory job state store.

Holds job status and results in a process-level dictionary. State is lost
on server restart — acceptable for MVP, can be swapped for Redis/DB later
without touching any other module.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class JobStatus(str, Enum):
    """Pipeline generation lifecycle stages, used by HTMX polling to render progress."""
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    """Mutable snapshot of a single pipeline generation run."""
    status: JobStatus = JobStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None


# Process-global store — every function below operates on this dict.
# Thread-safe as long as we stay on a single asyncio event loop (which uvicorn does).
_jobs: dict[str, Job] = {}


def create(job_id: str) -> Job:
    """Register a new job. Called by routes/generate.py before launching the async task."""
    job = Job()
    _jobs[job_id] = job
    return job


def update(job_id: str, **kwargs: Any) -> None:
    """Patch any field on an existing job. Called by jobs/manager.py as the pipeline progresses."""
    job = _jobs.get(job_id)
    if job is None:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)


def get(job_id: str) -> Job | None:
    """Retrieve current job state. Called by routes/status.py on each HTMX poll."""
    return _jobs.get(job_id)
