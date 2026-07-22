import asyncio
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator


class JobStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    VALIDATING = "validating"
    DONE = "done"
    FAILED = "failed"


STAGE_ORDER = [
    JobStatus.PENDING,
    JobStatus.CLONING,
    JobStatus.ANALYZING,
    JobStatus.GENERATING,
    JobStatus.VALIDATING,
    JobStatus.DONE,
]


@dataclass(frozen=True)
class LogEntry:
    timestamp: str
    stage: str
    message: str


@dataclass
class Job:
    repo_url: str = ""
    status: JobStatus = JobStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    logs: list[LogEntry] = field(default_factory=list)
    _notify: asyncio.Event = field(default_factory=asyncio.Event, repr=False)


_jobs: dict[str, Job] = {}


def create(job_id: str, repo_url: str) -> Job:
    job = Job(repo_url=repo_url)
    _jobs[job_id] = job
    return job


def update(job_id: str, **kwargs: Any) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    for key, value in kwargs.items():
        setattr(job, key, value)
    job._notify.set()
    job._notify.clear()


def append_log(job_id: str, stage: str, message: str) -> None:
    job = _jobs.get(job_id)
    if job is None:
        return
    entry = LogEntry(
        timestamp=datetime.now(timezone.utc).strftime("%H:%M:%S"),
        stage=stage,
        message=message,
    )
    job.logs.append(entry)
    job._notify.set()
    job._notify.clear()


def get(job_id: str) -> Job | None:
    return _jobs.get(job_id)


def list_all() -> dict[str, Job]:
    return dict(_jobs)


async def subscribe(job_id: str) -> AsyncGenerator[LogEntry, None]:
    job = _jobs.get(job_id)
    if job is None:
        return

    cursor = 0
    while True:
        while cursor < len(job.logs):
            yield job.logs[cursor]
            cursor += 1

        if job.status in (JobStatus.DONE, JobStatus.FAILED):
            return

        await job._notify.wait()
