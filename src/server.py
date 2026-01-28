"""
HTTP Server for AXON integration.

Exposes the worker as an HTTP service that AXON/Temporal can call.

Endpoints:
    POST /run-task    - Execute a task, returns TaskResult
    GET  /health      - Health check + profile statuses
    GET  /profiles    - List all tracked profiles
    GET  /profiles/{id} - Get specific profile status
    POST /profiles/{id}/resolve - Resolve human intervention
    POST /profiles/{id}/enable  - Re-enable disabled profile
    POST /profiles/{id}/disable - Disable a profile

Run:
    uvicorn src.server:app --host 0.0.0.0 --port 8080
"""

import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.worker import (
    TaskRunner,
    Task,
    TaskPolicy,
    get_circuit_breaker,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global runner instance
runner: Optional[TaskRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize runner on startup"""
    global runner
    runner = TaskRunner()
    logger.info("Worker server started")
    yield
    logger.info("Worker server stopped")


app = FastAPI(
    title="Axon Browser Worker",
    description="HTTP API for browser automation tasks",
    version="1.0.0",
    lifespan=lifespan,
)


# ============ Request/Response Models ============

class TaskRequest(BaseModel):
    """Request body for /run-task"""
    task_id: str
    profile_id: str
    task_type: str
    platform: str = "generic"
    params: dict = {}
    policy: Optional[dict] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_001",
                "profile_id": "k197eg5j",
                "task_type": "page_probe",
                "platform": "generic",
                "params": {
                    "url": "https://github.com/trending",
                    "selector": "//article"
                },
                "policy": {
                    "timeout_seconds": 60,
                    "retry_count": 0
                }
            }
        }


class DisableRequest(BaseModel):
    """Request body for disabling a profile"""
    reason: str


# ============ Endpoints ============

@app.post("/run-task")
async def run_task(request: TaskRequest):
    """
    Execute a browser automation task.
    
    Returns TaskResult with:
    - success: bool
    - blocked: bool
    - next_action: what scheduler should do next
    - profile_status: current profile state
    - metrics: task-specific data
    - artifacts: paths to screenshots/files
    """
    if runner is None:
        raise HTTPException(status_code=503, detail="Worker not initialized")
    
    # Convert request to Task
    task = Task(
        task_id=request.task_id,
        profile_id=request.profile_id,
        task_type=request.task_type,
        platform=request.platform,
        params=request.params,
        policy=TaskPolicy.from_dict(request.policy) if request.policy else None,
    )
    
    logger.info(f"Running task {task.task_id} for profile {task.profile_id}")
    
    # Execute
    result = runner.run(task)
    
    logger.info(
        f"Task {task.task_id} completed: success={result.success}, "
        f"blocked={result.blocked}, next_action={result.next_action}"
    )
    
    return JSONResponse(content=result.to_dict())


@app.get("/health")
async def health():
    """
    Health check endpoint.
    
    Returns:
    - status: "ok" if healthy
    - profiles_summary: count of profiles in each state
    """
    breaker = get_circuit_breaker()
    
    return {
        "status": "ok",
        "profiles_summary": {
            "healthy": len(breaker.get_healthy_profiles()),
            "cooling": len(breaker.get_cooling_profiles()),
            "needs_human": len(breaker.get_needs_human_profiles()),
            "disabled": len(breaker.get_disabled_profiles()),
        }
    }


@app.get("/profiles")
async def list_profiles():
    """
    List all tracked profiles and their states.
    """
    breaker = get_circuit_breaker()
    return {
        "profiles": breaker.get_all_statuses()
    }


@app.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    """
    Get status of a specific profile.
    """
    breaker = get_circuit_breaker()
    status = breaker.get_status(profile_id)
    return status.to_dict()


@app.post("/profiles/{profile_id}/resolve")
async def resolve_profile(profile_id: str):
    """
    Mark profile as resolved after human intervention.
    
    Called by ClawdHub after solving captcha/verification.
    """
    breaker = get_circuit_breaker()
    status = breaker.resolve_human(profile_id)
    logger.info(f"Profile {profile_id} resolved, now {status.state.value}")
    return status.to_dict()


@app.post("/profiles/{profile_id}/enable")
async def enable_profile(profile_id: str):
    """
    Re-enable a disabled profile.
    """
    breaker = get_circuit_breaker()
    status = breaker.enable(profile_id)
    logger.info(f"Profile {profile_id} enabled, now {status.state.value}")
    return status.to_dict()


@app.post("/profiles/{profile_id}/disable")
async def disable_profile(profile_id: str, request: DisableRequest):
    """
    Disable a profile manually.
    """
    breaker = get_circuit_breaker()
    status = breaker.disable(profile_id, request.reason)
    logger.info(f"Profile {profile_id} disabled: {request.reason}")
    return status.to_dict()


# ============ Error Handlers ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__}
    )


# ============ CLI Entry Point ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

