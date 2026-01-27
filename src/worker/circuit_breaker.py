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
    COOLING = "cooling"      
    FLAGGED = "flagged"      


@dataclass
class ProfileStatus:
    """Tracks a profile's health and cooldown status"""
    profile_id: str
    state: ProfileState = ProfileState.HEALTHY
    consecutive_blocks: int = 0
    total_blocks: int = 0
    last_block_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    flagged_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "state": self.state.value,
            "consecutive_blocks": self.consecutive_blocks,
            "total_blocks": self.total_blocks,
            "last_block_at": self.last_block_at.isoformat() if self.last_block_at else None,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "flagged_at": self.flagged_at.isoformat() if self.flagged_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
        }


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
        
        # Check if flagged
        if status.state == ProfileState.FLAGGED:
            return False, f"Profile flagged at {status.flagged_at}. Manual intervention required."
        
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
        
        This triggers cooldown or flagging based on consecutive blocks.
        """
        status = self.get_status(profile_id)
        now = datetime.utcnow()
        
        status.consecutive_blocks += 1
        status.total_blocks += 1
        status.last_block_at = now
        
        logger.warning(
            f"Profile {profile_id} blocked (#{status.consecutive_blocks}). Reason: {reason}"
        )
        
        # Determine action based on consecutive blocks
        if status.consecutive_blocks >= self.config.max_consecutive_blocks:
            # Flag for manual intervention
            status.state = ProfileState.FLAGGED
            status.flagged_at = now
            logger.error(
                f"Profile {profile_id} FLAGGED after {status.consecutive_blocks} consecutive blocks"
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
    
    def record_success(self, profile_id: str) -> ProfileStatus:
        """
        Record a successful task for a profile.
        
        Multiple successes can reset the consecutive block counter.
        """
        status = self.get_status(profile_id)
        status.last_success_at = datetime.utcnow()
        
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
    
    def unflag(self, profile_id: str) -> ProfileStatus:
        """
        Manually unflag a profile (after human intervention).
        
        Resets the profile to healthy state.
        """
        status = self.get_status(profile_id)
        
        if status.state == ProfileState.FLAGGED:
            status.state = ProfileState.HEALTHY
            status.consecutive_blocks = 0
            status.cooldown_until = None
            logger.info(f"Profile {profile_id} manually unflagged")
        
        return status
    
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
    
    def get_flagged_profiles(self) -> list[str]:
        """Get list of flagged profile IDs"""
        return [
            pid for pid, status in self._profiles.items()
            if status.state == ProfileState.FLAGGED
        ]
    
    def get_cooling_profiles(self) -> list[str]:
        """Get list of profiles in cooldown"""
        now = datetime.utcnow()
        return [
            pid for pid, status in self._profiles.items()
            if status.state == ProfileState.COOLING and 
               status.cooldown_until and now < status.cooldown_until
        ]


# Global instance for convenience
_default_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get the global circuit breaker instance"""
    global _default_breaker
    if _default_breaker is None:
        _default_breaker = CircuitBreaker()
    return _default_breaker

