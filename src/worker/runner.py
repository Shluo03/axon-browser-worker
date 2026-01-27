"""Task runner - executes tasks with proper lifecycle"""

import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

from src.adspower import AdsPowerClient
from src.browser import BrowserSession
from .tasks import Task, TaskResult
from .circuit_breaker import CircuitBreaker, get_circuit_breaker, ProfileState

logger = logging.getLogger(__name__)


class TaskRunner:
    """
    Runs tasks with:
    - Proper browser lifecycle (start → run → stop)
    - Artifact collection
    - Structured logging
    - Error handling
    - Circuit breaker integration (blocked detection → cooldown)
    """

    def __init__(
        self, 
        artifacts_dir: str = "artifacts",
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.artifacts_dir = Path(artifacts_dir)
        self.adspower = AdsPowerClient()
        self._handlers: Dict[str, Callable] = {}
        self.circuit_breaker = circuit_breaker or get_circuit_breaker()

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

        # Check circuit breaker FIRST
        can_run, cooldown_reason = self.circuit_breaker.can_run(task.profile_id)
        if not can_run:
            result.error = f"Circuit breaker: {cooldown_reason}"
            result.metrics = {
                "skipped": True,
                "skip_reason": "circuit_breaker",
                "profile_status": self.circuit_breaker.get_status(task.profile_id).to_dict(),
            }
            logger.warning(f"Task skipped for {task.profile_id}: {cooldown_reason}")
            return self._finalize(result, start_time)

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
                result.metrics = metrics
                result.artifacts = [str(a) for a in artifacts]
                
                # Check if blocked and update circuit breaker
                if metrics.get("blocked"):
                    block_reason = metrics.get("block_reason", "unknown")
                    status = self.circuit_breaker.record_block(
                        task.profile_id, 
                        reason=block_reason
                    )
                    result.success = False  # Blocked = not successful
                    result.error = f"Blocked: {block_reason}"
                    
                    # Add circuit breaker status to metrics
                    result.metrics["profile_status"] = status.to_dict()
                    
                    logger.warning(
                        f"Profile {task.profile_id} blocked. "
                        f"State: {status.state.value}, "
                        f"Consecutive: {status.consecutive_blocks}"
                    )
                else:
                    # Success - record it
                    self.circuit_breaker.record_success(task.profile_id)
                    result.success = True

        except Exception as e:
            logger.exception(f"Task failed: {e}")
            result.error = str(e)
            # Don't record as block - this is a technical failure, not a captcha

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
