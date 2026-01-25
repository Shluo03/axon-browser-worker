"""Task model - platform agnostic"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import json


@dataclass
class Task:
    """Input task from AXON/Temporal"""
    profile_id: str
    task_type: str  # page_probe, scroll_probe, warmup, post
    params: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[str] = None

    @classmethod
    def from_json(cls, data: Union[str, dict]) -> "Task":
        if isinstance(data, str):
            data = json.loads(data)
        return cls(**data)

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "task_type": self.task_type,
            "params": self.params,
            "task_id": self.task_id,
        }


@dataclass
class TaskResult:
    """Output result to AXON/Temporal"""
    success: bool
    task_id: Optional[str] = None
    artifacts: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    started_at: str = ""
    finished_at: str = ""
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "task_id": self.task_id,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
