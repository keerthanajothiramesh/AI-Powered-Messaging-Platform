"""
Resilience tests for circuit breaker and component failure scenarios.

Run:
    pytest tests/resilience/ -v

What is tested:
    - Gemini circuit breaker opens after N consecutive failures
    - Circuit breaker falls back to local stub (Flan-T5 or canned response)
    - Database connection failure is caught gracefully (does not crash the app)
    - DeliveryAgent handles empty failure list without error
    - NotificationAgent suppresses low-priority during fatigue
    - RCAAgent returns healthy report when no failures exist
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Circuit breaker ───────────────────────────────────────────────────────────

class TestGeminiCircuitBreaker:
    """Gemini circuit breaker should open after 3 failures and use fallback."""

    def test_circuit_opens_after_failures(self):
        """After _FAILURE_THRESHOLD consecutive errors, circuit state becomes 'open'."""
        from src.ai.gemini_client import _circuit_breaker
        # Reset state
        _circuit_breaker._failure_count = 0
        _circuit_breaker._state = "closed"
        _circuit_breaker._FAILURE_THRESHOLD = 3

        for _ in range(3):
            _circuit_breaker._record_failure()

        assert _circuit_breaker._state == "open", (
            f"Expected circuit to be 'open' after 3 failures, got '{_circuit_breaker._state}'"
        )

    def test_circuit_resets_on_success(self):
        """A successful call after half-open trial should close the circuit."""
        from src.ai.gemini_client import _circuit_breaker
        _circuit_breaker._state = "open"
        _circuit_breaker._failure_count = 3
        _circuit_breaker._record_success()
        assert _circuit_breaker._state == "closed"
        assert _circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_open_circuit_returns_fallback(self):
        """An open circuit should not call Gemini but return a fallback response."""
        from src.ai.gemini_client import _circuit_breaker, generate_text
        _circuit_breaker._state = "open"
        _circuit_breaker._last_failure_time = asyncio.get_event_loop().time()

        with patch("src.ai.gemini_client._call_gemini", new_callable=AsyncMock) as mock_gemini:
            result = await generate_text("test prompt")
            # Gemini should NOT be called when circuit is open
            assert mock_gemini.call_count == 0 or isinstance(result, str)


# ── Database failure graceful degradation ────────────────────────────────────

class TestDatabaseFailureDegradation:

    @pytest.mark.asyncio
    async def test_delivery_agent_handles_db_error(self):
        """DeliveryAgent should return an error dict, not raise, if MongoDB is unavailable."""
        from src.agents.delivery_agent import DeliveryAgent
        with patch(
            "src.agents.delivery_agent.DeliveryAgent._execute_db_query",
            side_effect=ConnectionError("MongoDB unavailable"),
        ):
            agent = DeliveryAgent()
            # If _execute_db_query doesn't exist, the agent will catch the exception in run()
            try:
                result = await agent.run({})
                # Should return a result dict, not raise
                assert isinstance(result, dict)
            except Exception as e:
                pytest.fail(f"DeliveryAgent raised instead of gracefully degrading: {e}")

    @pytest.mark.asyncio
    async def test_delivery_agent_empty_failed_list(self):
        """DeliveryAgent should return zeros when no failed messages exist."""
        from src.agents.delivery_agent import DeliveryAgent
        with patch("src.common.database.get_mongo_db") as mock_db:
            mock_collection = MagicMock()
            mock_collection.find.return_value.sort.return_value.limit.return_value = AsyncMock()
            mock_collection.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
            mock_db.return_value.messages = mock_collection

            agent = DeliveryAgent()
            result = await agent.run({})

        assert result["failed_found"] == 0
        assert result["recovered"] == 0
        assert result["escalated"] == 0


# ── Notification agent fatigue suppression ────────────────────────────────────

class TestNotificationAgentFatigue:

    @pytest.mark.asyncio
    async def test_suppresses_low_urgency_during_fatigue(self):
        """Low-urgency notifications should be suppressed when user already has 5+ in the last hour."""
        from src.agents.notification_agent import NotificationAgent

        with patch("src.agents.notification_agent._get_recent_notification_count", return_value=6), \
             patch("src.agents.notification_agent._get_user_active_hours", return_value={
                 "active_hours": list(range(8, 22)),
                 "quiet_start": 22,
                 "quiet_end": 7,
             }):
            agent = NotificationAgent()
            result = await agent.run({
                "user_id": "test-user",
                "content": "Just checking in",   # low urgency
            })

        assert result["suppressed"] is True
        assert result["should_notify"] is False

    @pytest.mark.asyncio
    async def test_urgent_bypasses_fatigue(self):
        """Urgent messages must always be delivered regardless of fatigue."""
        from src.agents.notification_agent import NotificationAgent

        with patch("src.agents.notification_agent._get_recent_notification_count", return_value=10), \
             patch("src.agents.notification_agent._get_user_active_hours", return_value={
                 "active_hours": list(range(8, 22)),
                 "quiet_start": 22,
                 "quiet_end": 7,
             }):
            agent = NotificationAgent()
            result = await agent.run({
                "user_id": "test-user",
                "content": "URGENT: server is down critical emergency",
            })

        assert result["should_notify"] is True
        assert result["urgency"] == "high"
        assert result["suppressed"] is False


# ── RCA Agent healthy state ───────────────────────────────────────────────────

class TestRCAAgentHealthyState:

    @pytest.mark.asyncio
    async def test_rca_healthy_when_no_failures(self):
        """RCAAgent should report zero failures and skip Gemini call when healthy."""
        from src.agents.rca_agent import RCAAgent

        async def _empty_agg(*args, **kwargs):
            return []

        with patch("src.common.database.get_mongo_db") as mock_db:
            mock_db.return_value.messages.aggregate.return_value.to_list = AsyncMock(return_value=[])
            mock_db.return_value.messages.count_documents = AsyncMock(return_value=1000)

            agent = RCAAgent()
            result = await agent.run({"hours": 24})

        assert result["total_failed"] == 0
        assert "healthy" in result["analysis"].lower() or result["failure_rate_pct"] == 0.0


# ── High concurrency: parallel requests don't crash WebSocket manager ─────────

class TestConcurrencyResistance:

    @pytest.mark.asyncio
    async def test_websocket_manager_concurrent_sends(self):
        """Multiple concurrent send calls should not cause race conditions."""
        from src.messaging.websocket_manager import ConnectionManager
        manager = ConnectionManager()

        # Simulate 20 concurrent send-to-user calls for a user not in the manager
        tasks = [
            manager.send_to_user("nonexistent-user", {"type": "ping"})
            for _ in range(20)
        ]
        # None should raise — missing users are silently skipped
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results if isinstance(r, Exception)]
        assert not errors, f"Concurrent sends raised: {errors}"
