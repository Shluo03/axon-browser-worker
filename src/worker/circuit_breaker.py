"""Circuit breaker and cooldown management for profiles"""

import time
import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ProfileState(Enum):
    """Profile health states"""
    HEALTHY = "healthy"         
    COOLING = "cooling"           # In cooldown period  
    NEEDS_HUMAN = "needs_human"   # ClawdHub intervention required
    DISABLED = "disabled"         # Profile should not be used      


@dataclass
class ProfileStatus:
    """Tracks a profile's health and cooldown status"""
    profile_id: str
    state: ProfileState = ProfileState.HEALTHY
    consecutive_blocks: int = 0
    consecutive_failures: int = 0  
    total_blocks: int = 0
    total_tasks: int = 0
    last_block_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    needs_human_at: Optional[datetime] = None  
    disabled_at: Optional[datetime] = None 
    disabled_reason: Optional[str] = None
    last_success_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "state": self.state.value,
            "consecutive_blocks": self.consecutive_blocks,
            "consecutive_failures": self.consecutive_failures,
            "total_blocks": self.total_blocks,
            "total_tasks": self.total_tasks,
            "last_block_at": self.last_block_at.isoformat() if self.last_block_at else None,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "needs_human_at": self.needs_human_at.isoformat() if self.needs_human_at else None,
            "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
            "disabled_reason": self.disabled_reason,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
        }
    
    @property
    def next_action(self) -> str:
        """Get the next action for scheduler based on current state"""
        from .tasks import NextAction
        return {
            ProfileState.HEALTHY: NextAction.CONTINUE.value,
            ProfileState.COOLING: NextAction.COOLDOWN.value,
            ProfileState.NEEDS_HUMAN: NextAction.NEEDS_HUMAN.value,
            ProfileState.DISABLED: NextAction.DISABLE_PROFILE.value,
        }[self.state]


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior"""
    # Cooldown durations (in seconds) based on consecutive blocks
    cooldown_tiers: Dict[int, tuple] = field(default_factory=lambda: {
        1: (15 * 60, 30 * 60),      
        2: (2 * 3600, 6 * 3600),   
        3: (0, 0),                   # 3+ blocks: FLAGGED (no auto-retry)
    })
    
    max_consecutive_blocks: int = 3
    
    reset_after_successes: int = 3
    
    min_request_interval: int = 5  


class CircuitBreaker:
    """
    Manages profile health, cooldowns, and circuit breaker logic.
    
    Usage:
        breaker = CircuitBreaker()
        
        # Before running task
        if breaker.can_run("profile_123"):
            result = run_task(...)
            if result.blocked:
                breaker.record_block("profile_123", result.block_reason)
            else:
                breaker.record_success("profile_123")
    """
    
    def __init__(self, config: CircuitBreakerConfig = None):
        self.config = config or CircuitBreakerConfig()
        self._profiles: Dict[str, ProfileStatus] = {}
    
    def get_status(self, profile_id: str) -> ProfileStatus:
        """Get or create profile status"""
        if profile_id not in self._profiles:
            self._profiles[profile_id] = ProfileStatus(profile_id=profile_id)
        return self._profiles[profile_id]
    
    def can_run(self, profile_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if profile can run a task.
        
        Returns:
            (can_run, reason) - reason is set if can_run is False
        """
        status = self.get_status(profile_id)
        now = datetime.utcnow()
        
        # Check if disabled
        if status.state == ProfileState.DISABLED:
            return False, f"Profile disabled: {status.disabled_reason}"
        
        # Check if needs human intervention
        if status.state == ProfileState.NEEDS_HUMAN:
            return False, f"Profile needs human intervention since {status.needs_human_at}"
        
        # Check if in cooldown
        if status.state == ProfileState.COOLING:
            if status.cooldown_until and now < status.cooldown_until:
                remaining = (status.cooldown_until - now).total_seconds()
                return False, f"Profile cooling down. {remaining/60:.1f} minutes remaining."
            else:
                # Cooldown expired, reset to healthy
                status.state = ProfileState.HEALTHY
                status.cooldown_until = None
                logger.info(f"Profile {profile_id} cooldown expired, now healthy")
        
        return True, None
    
    def record_block(self, profile_id: str, reason: str = None) -> ProfileStatus:
        """
        Record a block event for a profile.
        
        This triggers cooldown or NEEDS_HUMAN based on consecutive blocks.
        """
        status = self.get_status(profile_id)
        now = datetime.utcnow()
        
        status.consecutive_blocks += 1
        status.total_blocks += 1
        status.total_tasks += 1
        status.last_block_at = now
        # Reset failure count on block (different failure mode)
        status.consecutive_failures = 0
        
        logger.warning(
            f"Profile {profile_id} blocked (#{status.consecutive_blocks}). Reason: {reason}"
        )
        
        # Determine action based on consecutive blocks
        if status.consecutive_blocks >= self.config.max_consecutive_blocks:
            # Needs human intervention (ClawdHub)
            status.state = ProfileState.NEEDS_HUMAN
            status.needs_human_at = now
            logger.error(
                f"Profile {profile_id} NEEDS_HUMAN after {status.consecutive_blocks} consecutive blocks"
            )
        else:
            # Apply cooldown with exponential backoff
            cooldown_seconds = self._calculate_cooldown(status.consecutive_blocks)
            status.state = ProfileState.COOLING
            status.cooldown_until = now + timedelta(seconds=cooldown_seconds)
            logger.info(
                f"Profile {profile_id} cooling down for {cooldown_seconds/60:.1f} minutes"
            )
        
        return status
    
    def record_failure(self, profile_id: str, error: str = None) -> ProfileStatus:
        """
        Record a technical failure (not a block).
        
        5 consecutive failures → DISABLED
        """
        status = self.get_status(profile_id)
        now = datetime.utcnow()
        
        status.consecutive_failures += 1
        status.total_tasks += 1
        
        logger.warning(
            f"Profile {profile_id} failed (#{status.consecutive_failures}). Error: {error}"
        )
        
        # 5 consecutive failures → disable
        if status.consecutive_failures >= 5:
            status.state = ProfileState.DISABLED
            status.disabled_at = now
            status.disabled_reason = f"5 consecutive failures. Last: {error}"
            logger.error(f"Profile {profile_id} DISABLED after 5 consecutive failures")
        
        return status
    
    def record_success(self, profile_id: str) -> ProfileStatus:
        """
        Record a successful task for a profile.
        
        Multiple successes can reset the consecutive block counter.
        """
        status = self.get_status(profile_id)
        status.last_success_at = datetime.utcnow()
        status.total_tasks += 1
        
        # Reset failure count
        status.consecutive_failures = 0
        
        # Gradually decrease consecutive_blocks on success
        if status.consecutive_blocks > 0:
            status.consecutive_blocks = max(0, status.consecutive_blocks - 1)
            logger.info(
                f"Profile {profile_id} success. Consecutive blocks: {status.consecutive_blocks}"
            )
        
        # If was cooling and now healthy, clear cooldown
        if status.state == ProfileState.COOLING:
            status.state = ProfileState.HEALTHY
            status.cooldown_until = None
        
        return status
    
    def resolve_human(self, profile_id: str) -> ProfileStatus:
        """
        Mark profile as resolved after human intervention (ClawdHub).
        
        Resets the profile to healthy state.
        """
        status = self.get_status(profile_id)
        
        if status.state == ProfileState.NEEDS_HUMAN:
            status.state = ProfileState.HEALTHY
            status.consecutive_blocks = 0
            status.needs_human_at = None
            logger.info(f"Profile {profile_id} resolved by human, now healthy")
        
        return status
    
    def disable(self, profile_id: str, reason: str) -> ProfileStatus:
        """
        Manually disable a profile.
        """
        status = self.get_status(profile_id)
        status.state = ProfileState.DISABLED
        status.disabled_at = datetime.utcnow()
        status.disabled_reason = reason
        logger.info(f"Profile {profile_id} disabled: {reason}")
        return status
    
    def enable(self, profile_id: str) -> ProfileStatus:
        """
        Re-enable a disabled profile.
        """
        status = self.get_status(profile_id)
        
        if status.state == ProfileState.DISABLED:
            status.state = ProfileState.HEALTHY
            status.disabled_at = None
            status.disabled_reason = None
            status.consecutive_blocks = 0
            status.consecutive_failures = 0
            logger.info(f"Profile {profile_id} re-enabled")
        
        return status
    
    # Keep unflag as alias for backwards compatibility
    def unflag(self, profile_id: str) -> ProfileStatus:
        """Alias for resolve_human (backwards compatibility)"""
        return self.resolve_human(profile_id)
    
    def _calculate_cooldown(self, consecutive_blocks: int) -> int:
        """Calculate cooldown duration with jitter"""
        tier = min(consecutive_blocks, max(self.config.cooldown_tiers.keys()))
        min_cooldown, max_cooldown = self.config.cooldown_tiers.get(tier, (30 * 60, 60 * 60))
        
        # Add random jitter (±20%)
        base = random.uniform(min_cooldown, max_cooldown)
        jitter = base * random.uniform(-0.2, 0.2)
        
        return int(base + jitter)
    
    def get_all_statuses(self) -> Dict[str, dict]:
        """Get status of all tracked profiles"""
        return {pid: status.to_dict() for pid, status in self._profiles.items()}
    
    def get_needs_human_profiles(self) -> list[str]:
        """Get list of profiles needing human intervention"""
        return [
            pid for pid, status in self._profiles.items()
            if status.state == ProfileState.NEEDS_HUMAN
        ]
    
    def get_disabled_profiles(self) -> list[str]:
        """Get list of disabled profiles"""
        return [
            pid for pid, status in self._profiles.items()
            if status.state == ProfileState.DISABLED
        ]
    
    def get_cooling_profiles(self) -> list[str]:
        """Get list of profiles in cooldown"""
        now = datetime.utcnow()
        return [
            pid for pid, status in self._profiles.items()
            if status.state == ProfileState.COOLING and 
               status.cooldown_until and now < status.cooldown_until
        ]
    
    def get_healthy_profiles(self) -> list[str]:
        """Get list of healthy profiles ready for tasks"""
        return [
            pid for pid, status in self._profiles.items()
            if status.state == ProfileState.HEALTHY
        ]
    
    def get_flagged_profiles(self) -> list[str]:
        """Alias for get_needs_human_profiles"""
        return self.get_needs_human_profiles()


# Global instance for convenience
_default_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker instance"""
    global _default_breaker
    if _default_breaker is None:
        _default_breaker = CircuitBreaker()
    return _default_breaker

