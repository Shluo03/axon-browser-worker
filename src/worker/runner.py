"""Task runner - executes tasks with proper lifecycle"""

import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict

from src.adspower import AdsPowerClient
from src.browser import BrowserSession
from .tasks import Task, TaskResult

logger = logging.getLogger(__name__)


class TaskRunner:
    """
    Runs tasks with:
    - Proper browser lifecycle (start → run → stop)
    - Artifact collection
    - Structured logging
    - Error handling
    """

    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = Path(artifacts_dir)
        self.adspower = AdsPowerClient()
        self._handlers: Dict[str, Callable] = {}

        # Register built-in handlers
        self._register_builtins()

    def register(self, task_type: str, handler: Callable):
        """Register a task handler"""
        self._handlers[task_type] = handler

    def run(self, task: Task) -> TaskResult:
        """Execute a task and return result"""
        started_at = datetime.utcnow()
        start_time = time.time()

        result = TaskResult(
            success=False,
            task_id=task.task_id,
            started_at=started_at.isoformat() + "Z",
        )

        # Create artifact directory for this run
        artifact_path = self._artifact_path(task.profile_id, started_at)
        artifact_path.mkdir(parents=True, exist_ok=True)

        handler = self._handlers.get(task.task_type)
        if not handler:
            result.error = f"Unknown task_type: {task.task_type}"
            return self._finalize(result, start_time)

        try:
            with BrowserSession(task.profile_id, self.adspower) as session:
                # Run handler
                metrics, artifacts = handler(
                    session.driver,
                    task.params,
                    artifact_path,
                )
                result.success = True
                result.metrics = metrics
                result.artifacts = [str(a) for a in artifacts]

        except Exception as e:
            logger.exception(f"Task failed: {e}")
            result.error = str(e)

        return self._finalize(result, start_time)

    def _finalize(self, result: TaskResult, start_time: float) -> TaskResult:
        result.finished_at = datetime.utcnow().isoformat() + "Z"
        result.duration_ms = int((time.time() - start_time) * 1000)
        return result

    def _artifact_path(self, profile_id: str, dt: datetime) -> Path:
        return self.artifacts_dir / profile_id / dt.strftime("%Y-%m-%dT%H-%M-%S")

    def _register_builtins(self):
        """Register built-in task handlers"""
        from .handlers import page_probe, scroll_probe, perf_probe

        self.register("page_probe", page_probe)
        self.register("scroll_probe", scroll_probe)
        self.register("perf_probe", perf_probe)
