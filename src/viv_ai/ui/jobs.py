"""
Background job runner with optional QThread-based async execution.

Phase R: Adds threaded execution, progress reporting, and cancellation support
to the existing BackgroundJobRunner. Falls back to synchronous execution when
Qt is not available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import uuid

try:
    from PyQt6 import QtCore
except Exception:  # pragma: no cover — optional during headless tests
    try:
        from PyQt5 import QtCore  # type: ignore
    except Exception:  # pragma: no cover — optional during headless tests
        QtCore = None


@dataclass
class BackgroundJob:
    """A single analysis job with progress tracking."""

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


class RunnableJob(QtCore.QObject if QtCore else object):
    """A QObject that runs a job in a worker thread.
    
    Emits progress_changed and finished signals for Qt UI integration.
    Falls back to synchronous execution when Qt is unavailable.
    """

    if QtCore:
        progress_changed = QtCore.pyqtSignal(str, int, str)  # job_id, progress, message
        finished = QtCore.pyqtSignal(str)                     # job_id
    else:
        progress_changed = None
        finished = None

    def __init__(self, job: BackgroundJob):
        super().__init__()
        self.job = job
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    def _update(self, progress: int, message: str) -> None:
        """Progress callback passed to the job function."""
        if self._cancelled:
            return
        self.job.progress = progress
        self.job.message = message
        if self.progress_changed is not None:
            self.progress_changed.emit(self.job.job_id, progress, message)

    def run(self) -> None:
        """Execute the job function and emit finished when done."""
        if self._cancelled:
            self.job.status = 'cancelled'
            self.job.message = 'cancelled'
            if self.finished is not None:
                self.finished.emit(self.job.job_id)
            return

        self.job.status = 'running'
        self.job.message = 'running'

        try:
            result = self.job.fn(self._update)
            if self._cancelled:
                self.job.status = 'cancelled'
                self.job.message = 'cancelled'
            else:
                self.job.result = result
                self.job.status = 'completed'
                if self.job.message in ('queued', 'running'):
                    self.job.message = 'completed'
                self.job.progress = 100
                if self.progress_changed is not None:
                    self.progress_changed.emit(self.job.job_id, 100, 'completed')
        except Exception as exc:
            self.job.status = 'failed'
            self.job.error = str(exc)
            self.job.message = 'failed'

        if self.finished is not None:
            self.finished.emit(self.job.job_id)


class BackgroundJobRunner:
    """Manages a queue of BackgroundJob instances.
    
    In Qt environments, jobs run on QThread workers. Without Qt, jobs run
    synchronously via run_pending().
    """

    def __init__(self):
        self.jobs: List[BackgroundJob] = []
        self._runnables: Dict[str, RunnableJob] = {}
        self._threads: Dict[str, Any] = {}  # QThread objects when Qt available

    def submit(
        self,
        task_type: str,
        fn: Callable[[Callable[[int, str], None]], Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            job_id=str(uuid.uuid4()),
            task_type=task_type,
            fn=fn,
            metadata=dict(metadata or {}),
        )
        self.jobs.append(job)

        # If Qt is available, start the job on a QThread immediately
        if QtCore is not None:
            self._start_threaded(job)

        return job

    def _start_threaded(self, job: BackgroundJob) -> None:
        """Launch a job on a QThread worker."""
        runnable = RunnableJob(job)
        thread = QtCore.QThread()
        runnable.moveToThread(thread)
        thread.started.connect(runnable.run)
        runnable.finished.connect(thread.quit)
        runnable.finished.connect(lambda jid: self._cleanup_thread(jid))
        thread.start()

        self._runnables[job.job_id] = runnable
        self._threads[job.job_id] = thread

    def _cleanup_thread(self, job_id: str) -> None:
        """Remove thread and runnable references after completion."""
        self._runnables.pop(job_id, None)
        self._threads.pop(job_id, None)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job."""
        if job_id in self._runnables:
            self._runnables[job_id].cancel()
            return True
        for job in self.jobs:
            if job.job_id == job_id and job.status == 'pending':
                job.status = 'cancelled'
                job.message = 'cancelled'
                return True
        return False

    def pending_count(self) -> int:
        return sum(1 for j in self.jobs if j.status == 'pending')

    def running_count(self) -> int:
        return sum(1 for j in self.jobs if j.status == 'running')

    def run_pending(self) -> List[Dict[str, Any]]:
        """Run all pending jobs synchronously (fallback when no Qt).
        
        In Qt mode, the threaded runner handles execution and this is a no-op.
        """
        # In Qt mode, pending jobs are launched immediately via submit()
        if QtCore is not None:
            return []

        snapshots: List[Dict[str, Any]] = []
        for job in self.jobs:
            if job.status != 'pending':
                continue
            job.status = 'running'
            job.message = 'running'

            def _update(progress: int, message: str) -> None:
                job.progress = progress
                job.message = message

            try:
                result = job.fn(_update)
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
