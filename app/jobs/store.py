from enum import Enum
from dataclasses import dataclass, field
from typing import Any


class JobStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"


@dataclass
class Job:
    status: JobStatus = JobStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None


_jobs: dict[str, Job] = {}


def create(job_id: str) -> Job:
    job = Job()
    _jobs[job_id] = job
    return job


def update(job_id: str, **kwargs: Any) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)
