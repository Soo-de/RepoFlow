"""
Jobs package — in-memory async job execution layer.

This package replaces the Arq/Redis worker setup. It exposes:
  - store: read/write job state (create, update, get)
  - run_job: async function that chains core/ modules
  - JobStatus, Job: data types for job state
"""

from app.jobs.store import JobStatus, Job
from app.jobs import store
from app.jobs.manager import run_job

__all__ = ["JobStatus", "Job", "store", "run_job"]
