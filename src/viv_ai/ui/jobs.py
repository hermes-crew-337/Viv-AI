from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import uuid


@dataclass
class BackgroundJob:
    job_id: str
    task_type: str
    fn: Callable[[Callable[[int, str], None]], Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None
    status: str = 'pending'
    progress: int = 0
    message: str = 'queued'
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'job_id': self.job_id,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'message': self.message,
            'result': self.result,
            'error': self.error,
            'metadata': dict(self.metadata or {}),
        }


class BackgroundJobRunner:
    def __init__(self):
        self.jobs: List[BackgroundJob] = []

    def submit(self, task_type: str, fn: Callable[[Callable[[int, str], None]], Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None) -> BackgroundJob:
        job = BackgroundJob(job_id=str(uuid.uuid4()), task_type=task_type, fn=fn, metadata=dict(metadata or {}))
        self.jobs.append(job)
        return job

    def run_pending(self) -> List[Dict[str, Any]]:
        snapshots: List[Dict[str, Any]] = []
        for job in self.jobs:
            if job.status != 'pending':
                continue
            job.status = 'running'
            job.message = 'running'

            def update(progress: int, message: str) -> None:
                job.progress = progress
                job.message = message

            try:
                result = job.fn(update)
                job.result = result
                job.status = 'completed'
                if job.message in ('queued', 'running'):
                    job.message = 'completed'
            except Exception as exc:
                job.status = 'failed'
                job.error = str(exc)
                job.message = 'failed'
            snapshots.append(job.to_dict())
        return snapshots
