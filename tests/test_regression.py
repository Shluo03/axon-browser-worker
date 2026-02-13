"""
Regression tests for browser worker - stable public sites only.

These tests use stable, public websites to verify core functionality:
1. GitHub Trending - page loading + element detection
2. Wikipedia - page loading + scrolling
3. Example.com - basic connectivity

Run with: pytest tests/test_regression.py -v
"""

import pytest
from pathlib import Path
from datetime import datetime

from src.worker import TaskRunner, Task


# Test configuration
PROFILE_ID = "k197eg5j"  # Your AdsPower profile
ARTIFACTS_DIR = "artifacts/regression"


@pytest.fixture(scope="module")
def runner():
    """Create task runner for tests"""
    return TaskRunner(artifacts_dir=ARTIFACTS_DIR)


class TestPageProbe:
    """Test page_probe handler with stable sites"""
    
    def test_example_com_basic(self, runner):
        """Simplest possible test - example.com always works"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="page_probe",
            params={"url": "https://example.com"},
            task_id="test_example_basic",
        )
        
        result = runner.run(task)
        
        assert result.success, f"Failed: {result.error}"
        assert result.metrics.get("blocked") is False
        assert "example" in result.metrics.get("title", "").lower()
        assert result.artifacts, "Should have screenshot"
        
        # Verify result.json was created
        result_json_exists = any("result.json" in a for a in result.artifacts)
        assert result_json_exists, "Should save result.json"
    
    def test_github_trending(self, runner):
        """GitHub trending - stable, no auth required"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="page_probe",
            params={
                "url": "https://github.com/trending",
                "selector": "//article[@class='Box-row']",
            },
            task_id="test_github_trending",
        )
        
        result = runner.run(task)
        
        assert result.success, f"Failed: {result.error}"
        assert result.metrics.get("blocked") is False
        assert result.metrics.get("element_count", 0) > 0, "Should find trending repos"
        assert "github" in result.metrics.get("final_url", "").lower()
    
    def test_wikipedia_main(self, runner):
        """Wikipedia - extremely stable"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="page_probe",
            params={
                "url": "https://en.wikipedia.org/wiki/Main_Page",
                "selector": "//div[@id='mp-tfa']",  # Today's featured article
            },
            task_id="test_wikipedia_main",
        )
        
        result = runner.run(task)
        
        assert result.success, f"Failed: {result.error}"
        assert result.metrics.get("blocked") is False
        assert "wikipedia" in result.metrics.get("title", "").lower()


class TestScrollProbe:
    """Test scroll_probe handler with scrollable pages"""
    
    def test_github_trending_scroll(self, runner):
        """GitHub trending with scrolling"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="scroll_probe",
            params={
                "url": "https://github.com/trending",
                "selector": "//article[@class='Box-row']",
                "scroll_count": 2,
            },
            task_id="test_github_scroll",
        )
        
        result = runner.run(task)
        
        assert result.success, f"Failed: {result.error}"
        assert result.metrics.get("blocked") is False
        assert result.metrics.get("initial_count", 0) > 0
        assert len(result.artifacts) >= 2, "Should have scroll screenshots"
    
    def test_wikipedia_scroll(self, runner):
        """Wikipedia article with scrolling"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="scroll_probe",
            params={
                "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
                "selector": "//p",  # Paragraphs
                "scroll_count": 3,
            },
            task_id="test_wiki_scroll",
        )
        
        result = runner.run(task)
        
        assert result.success, f"Failed: {result.error}"
        assert result.metrics.get("blocked") is False


class TestBlockDetection:
    """Test blocked detection (without actually getting blocked)"""
    
    def test_detection_fields_present(self, runner):
        """Verify all detection fields are in metrics"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="page_probe",
            params={"url": "https://example.com"},
            task_id="test_detection_fields",
        )
        
        result = runner.run(task)
        
        # Check required fields exist
        assert "blocked" in result.metrics
        assert "block_reason" in result.metrics
        assert "final_url" in result.metrics
        assert "page_fingerprint" in result.metrics
        
        # Fingerprint should have counts
        fp = result.metrics.get("page_fingerprint", {})
        assert "element_count" in fp
    
    def test_result_json_contains_detection(self, runner):
        """Verify result.json has detection info"""
        task = Task(
            profile_id=PROFILE_ID,
            task_type="page_probe",
            params={"url": "https://example.com"},
            task_id="test_result_json",
        )
        
        result = runner.run(task)
        
        # Find result.json
        result_json_path = None
        for artifact in result.artifacts:
            if "result.json" in artifact:
                result_json_path = Path(artifact)
                break
        
        assert result_json_path and result_json_path.exists(), "result.json should exist"
        
        import json
        content = json.loads(result_json_path.read_text())
        assert "detection" in content
        assert content["detection"]["blocked"] is False


class TestCircuitBreaker:
    """Test circuit breaker behavior (unit tests, no browser)"""
    
    def test_circuit_breaker_cooldown(self):
        """Test that blocks trigger cooldown"""
        from src.worker import CircuitBreaker, ProfileState
        
        breaker = CircuitBreaker()
        profile = "test_profile_1"
        
        # Initially can run
        can_run, _ = breaker.can_run(profile)
        assert can_run
        
        # Record a block
        status = breaker.record_block(profile, "test_block")
        
        # Should be in cooling state
        assert status.state == ProfileState.COOLING
        assert status.consecutive_blocks == 1
        
        # Should not be able to run
        can_run, reason = breaker.can_run(profile)
        assert not can_run
        assert "cooling" in reason.lower()
    
    def test_circuit_breaker_flagged(self):
        """Test that 3 blocks triggers flagged state"""
        from src.worker import CircuitBreaker, ProfileState
        
        breaker = CircuitBreaker()
        profile = "test_profile_2"
        
        # Simulate 3 consecutive blocks
        for i in range(3):
            # Force state to healthy for testing
            breaker.get_status(profile).state = ProfileState.HEALTHY
            breaker.get_status(profile).cooldown_until = None
            breaker.record_block(profile, f"block_{i+1}")
        
        status = breaker.get_status(profile)
        assert status.state == ProfileState.FLAGGED
        assert status.consecutive_blocks == 3
        
        # Should not be able to run when flagged
        can_run, reason = breaker.can_run(profile)
        assert not can_run
        assert "flagged" in reason.lower()
    
    def test_circuit_breaker_success_reduces_blocks(self):
        """Test that success reduces consecutive block count"""
        from src.worker import CircuitBreaker, ProfileState
        
        breaker = CircuitBreaker()
        profile = "test_profile_3"
        
        # Record a block
        breaker.record_block(profile, "test")
        assert breaker.get_status(profile).consecutive_blocks == 1
        
        # Record success (need to clear cooldown first)
        breaker.get_status(profile).state = ProfileState.HEALTHY
        breaker.get_status(profile).cooldown_until = None
        breaker.record_success(profile)
        
        # Consecutive blocks should decrease
        assert breaker.get_status(profile).consecutive_blocks == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



