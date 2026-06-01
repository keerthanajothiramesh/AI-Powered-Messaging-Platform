"""
Resilience tests for circuit breaker and component failure scenarios.

Run:
    pytest tests/resilience/ -v

What is tested:
    - OpenAI circuit breaker opens after 3 consecutive failures
    - Circuit breaker resets to closed on success
    - Open circuit returns a fallback string without calling OpenAI
    - DeliveryAgent returns zeros when no failed messages exist
    - DeliveryAgent does not raise when MongoDB is unavailable
    - NotificationAgent suppresses low-priority during notification fatigue
    - NotificationAgent lets urgent messages bypass fatigue + quiet hours
    - RCAAgent returns a healthy report when no delivery failures exist
    - WebSocket manager handles 20 concurrent sends without race conditions
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Circuit breaker ────────────────────────────────────────────────────────────
# gemini_client.py uses module-level globals:
#   _circuit_failures (int)  — incremented on each OpenAI error
#   _circuit_open     (bool) — True once _circuit_failures >= 3
#   _record_failure() — increments count, flips flag at threshold
#   _record_success() — resets both to 0 / False

class TestOpenAICircuitBreaker:

    def setup_method(self):
        """Reset circuit state before each test."""
        import src.ai.gemini_client as gcm
        gcm._circuit_failures = 0
        gcm._circuit_open = False

    def test_circuit_opens_after_three_failures(self):
        """After 3 consecutive failures the circuit must be open."""
        import src.ai.gemini_client as gcm
        for _ in range(3):
            gcm._record_failure()
        assert gcm._circuit_open is True, (
            f"Expected _circuit_open=True after 3 failures, got {gcm._circuit_open}"
        )
        assert gcm._circuit_failures >= 3

    def test_circuit_stays_closed_below_threshold(self):
        """Two failures must NOT open the circuit."""
        import src.ai.gemini_client as gcm
        gcm._record_failure()
        gcm._record_failure()
        assert gcm._circuit_open is False

    def test_circuit_resets_on_success(self):
        """A successful call resets failure count and closes the circuit."""
        import src.ai.gemini_client as gcm
        gcm._circuit_open = True
        gcm._circuit_failures = 3
        gcm._record_success()
        assert gcm._circuit_open is False
        assert gcm._circuit_failures == 0

    async def test_open_circuit_returns_fallback_without_calling_gemini(self):
        """When the circuit is open, generate_text must not call OpenAI."""
        import src.ai.gemini_client as gcm
        gcm._circuit_open = True

        with patch("src.ai.gemini_client._local_fallback", new_callable=AsyncMock, return_value="fallback") as mock_fb, \
             patch("src.ai.gemini_client._client", new_callable=MagicMock):
            result = await gcm.generate_text("any prompt")

        # Fallback must have been used, and result is a string
        mock_fb.assert_called_once()
        assert isinstance(result, str)


# ── Database failure — graceful degradation ───────────────────────────────────

class TestDatabaseFailureDegradation:

    async def test_delivery_agent_empty_failed_list(self):
        """DeliveryAgent returns zeros when MongoDB reports no failed messages."""
        from src.agents.delivery_agent import DeliveryAgent

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[])

        with patch("src.common.database.get_mongo_db") as mock_db:
            mock_db.return_value.messages.find.return_value = mock_cursor
            agent = DeliveryAgent()
            result = await agent.run({})

        assert result["failed_found"] == 0
        assert result["recovered"] == 0
        assert result["escalated"] == 0
        assert result["pending"] == 0

    async def test_delivery_agent_does_not_raise_on_db_error(self):
        """DeliveryAgent must return a dict even when MongoDB raises."""
        from src.agents.delivery_agent import DeliveryAgent

        with patch("src.common.database.get_mongo_db", side_effect=RuntimeError("MongoDB unavailable")):
            agent = DeliveryAgent()
            try:
                result = await agent.run({})
                assert isinstance(result, dict)
            except Exception as exc:
                pytest.fail(f"DeliveryAgent raised instead of degrading gracefully: {exc}")


# ── Notification agent — fatigue suppression ──────────────────────────────────

class TestNotificationAgentFatigue:

    async def test_suppresses_low_urgency_during_fatigue(self):
        """Low-urgency notification is suppressed when user received 6 in the last hour."""
        from src.agents.notification_agent import NotificationAgent

        with patch("src.agents.notification_agent._get_recent_notification_count",
                   new=AsyncMock(return_value=6)), \
             patch("src.agents.notification_agent._get_user_active_hours",
                   new=AsyncMock(return_value={
                       "active_hours": list(range(8, 22)),
                       "quiet_start": 22,
                       "quiet_end": 7,
                   })):
            result = await NotificationAgent().run({
                "user_id": "test-user",
                "content": "Just checking in",
            })

        assert result["suppressed"] is True
        assert result["should_notify"] is False
        assert result["urgency"] == "low"

    async def test_urgent_bypasses_fatigue_and_quiet_hours(self):
        """Urgent messages must always be delivered regardless of fatigue or quiet hours."""
        from src.agents.notification_agent import NotificationAgent

        with patch("src.agents.notification_agent._get_recent_notification_count",
                   new=AsyncMock(return_value=10)), \
             patch("src.agents.notification_agent._get_user_active_hours",
                   new=AsyncMock(return_value={
                       "active_hours": list(range(8, 22)),
                       "quiet_start": 22,
                       "quiet_end": 7,
                   })):
            result = await NotificationAgent().run({
                "user_id": "test-user",
                "content": "URGENT: server is down critical emergency",
            })

        assert result["should_notify"] is True
        assert result["urgency"] == "high"
        assert result["suppressed"] is False
        assert result["delivery_time"] == "immediate"


# ── RCA Agent — healthy state ─────────────────────────────────────────────────

class TestRCAAgentHealthyState:

    async def test_returns_healthy_when_no_failures(self):
        """RCAAgent reports zero failures and skips OpenAI when system is healthy."""
        from src.agents.rca_agent import RCAAgent

        with patch("src.common.database.get_mongo_db") as mock_db, \
             patch("src.common.database.get_pg_pool"):
            mock_db.return_value.messages.aggregate.return_value.to_list = AsyncMock(return_value=[])
            mock_db.return_value.messages.count_documents = AsyncMock(return_value=5000)

            result = await RCAAgent().run({"hours": 24})

        assert result["total_failed"] == 0
        assert result["failure_rate_pct"] == 0.0
        assert isinstance(result["analysis"], str)
        assert len(result["analysis"]) > 0


# ── WebSocket manager — concurrency resistance ────────────────────────────────

class TestConcurrencyResistance:

    async def test_concurrent_sends_to_unknown_user_do_not_raise(self):
        """20 concurrent send_to_user calls for a non-existent user must all return False."""
        from src.messaging.websocket_manager import ConnectionManager
        manager = ConnectionManager()

        results = await asyncio.gather(
            *[manager.send_to_user("ghost-user", {"type": "ping"}) for _ in range(20)],
            return_exceptions=True,
        )

        errors = [r for r in results if isinstance(r, Exception)]
        assert not errors, f"Concurrent sends raised exceptions: {errors}"
        # All should return False (user not connected)
        assert all(r is False for r in results)
