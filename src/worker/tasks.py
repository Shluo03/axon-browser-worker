"""Task contract - stable schema for AXON/Temporal integration"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from enum import Enum
import json


class NextAction(str, Enum):
    """What the scheduler should do next"""
    CONTINUE = "continue"           # Keep going, profile is healthy
    COOLDOWN = "cooldown"           # Wait before next task
    NEEDS_HUMAN = "needs_human"     # ClawdHub intervention required
    DISABLE_PROFILE = "disable_profile"  # Stop using this profile


class Platform(str, Enum):
    """Supported platforms"""
    GENERIC = "generic"
    XIAOHONGSHU = "xiaohongshu"
    INSTAGRAM = "instagram"
    DOUYIN = "douyin"
    WEIBO = "weibo"
    FACEBOOK = "facebook"


class TaskType(str, Enum):
    """Task types"""
    PAGE_PROBE = "page_probe"
    SCROLL_PROBE = "scroll_probe"
    PERF_PROBE = "perf_probe"
    WARMUP = "warmup"
    POST = "post"
    SCRAPE = "scrape"


@dataclass
class TaskPolicy:
    """Execution policy for a task"""
    timeout_seconds: int = 60           # Max execution time
    retry_count: int = 0                # How many retries on failure
    cooldown_on_block_seconds: int = 1800  # 30min default cooldown
    save_artifacts: bool = True         # Save screenshots/html
    
    @classmethod
    def from_dict(cls, data: dict) -> "TaskPolicy":
        if data is None:
            return cls()
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> dict:
        return {
            "timeout_seconds": self.timeout_seconds,
            "retry_count": self.retry_count,
            "cooldown_on_block_seconds": self.cooldown_on_block_seconds,
            "save_artifacts": self.save_artifacts,
        }


@dataclass
class Task:
    """
    Input task from AXON/Temporal.
    
    This is the contract - AXON sends this, worker executes it.
    """
    task_id: str                        # Unique task identifier (required)
    profile_id: str                     # AdsPower profile to use (required)
    task_type: str                      # page_probe/scroll_probe/warmup/post/scrape
    platform: str = "generic"           # xhs/instagram/douyin/generic
    params: Dict[str, Any] = field(default_factory=dict)  # Task-specific params
    policy: Optional[TaskPolicy] = None # Execution policy
    
    def __post_init__(self):
        # Ensure policy is TaskPolicy instance
        if isinstance(self.policy, dict):
            self.policy = TaskPolicy.from_dict(self.policy)
        elif self.policy is None:
            self.policy = TaskPolicy()

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> "Task":
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "profile_id": self.profile_id,
            "task_type": self.task_type,
            "platform": self.platform,
            "params": self.params,
            "policy": self.policy.to_dict() if self.policy else None,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class TaskResult:
    """
    Output result to AXON/Temporal.
    
    This is the contract - worker returns this after execution.
    """
    # Core fields
    task_id: str
    success: bool
    
    # Block detection (top-level for easy access)
    blocked: bool = False
    block_reason: Optional[str] = None
    
    # Scheduler directive
    next_action: str = NextAction.CONTINUE.value
    
    # Detailed metrics
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    # Files produced
    artifacts: List[str] = field(default_factory=list)
    
    # Profile state after task
    profile_status: Optional[Dict[str, Any]] = None
    
    # Error info
    error: Optional[str] = None
    
    # Timing
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "next_action": self.next_action,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "profile_status": self.profile_status,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    @classmethod
    def error_result(cls, task_id: str, error: str, next_action: str = NextAction.CONTINUE.value) -> "TaskResult":
        """Factory for error results"""
        return cls(
            task_id=task_id,
            success=False,
            error=error,
            next_action=next_action,
        )
    
    @classmethod
    def blocked_result(
        cls, 
        task_id: str, 
        block_reason: str,
        metrics: Dict = None,
        artifacts: List[str] = None,
        profile_status: Dict = None,
        next_action: str = NextAction.COOLDOWN.value,
    ) -> "TaskResult":
        """Factory for blocked results"""
        return cls(
            task_id=task_id,
            success=False,
            blocked=True,
            block_reason=block_reason,
            next_action=next_action,
            metrics=metrics or {},
            artifacts=artifacts or [],
            profile_status=profile_status,
        )
