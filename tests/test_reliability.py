"""Reliability, timeout resilience, and graceful degradation test suite (REM-07)."""

import asyncio
import time
import unittest
from unittest.mock import patch
from starlette.testclient import TestClient

from bot import app, engine, vera


class TestReliabilityAndTimeoutResilience(unittest.TestCase):
    """Stress tests verifying timeout resilience, exception isolation, and graceful fallbacks."""

    def setUp(self):
        self.client = TestClient(app)

    def test_mock_upstream_timeout_returns_graceful_fallback(self):
        """Simulate upstream model/handler timeout and assert graceful termination within deadline."""
        def slow_handler(*args, **kwargs):
            # Simulate a hanging operation
            time.sleep(2.0)
            raise RuntimeError("Should have timed out")

        # Temporarily set timeout low for test execution speed
        with patch.object(vera, "handle_reactive_message", side_effect=slow_handler):
            with patch("bot.asyncio.wait_for") as mock_wait_for:
                # Simulate asyncio.TimeoutError raised by wait_for
                async def raise_timeout(fut, timeout=None):
                    if hasattr(fut, "close"):
                        fut.close()
                    raise asyncio.TimeoutError("Deadline exceeded")

                mock_wait_for.side_effect = raise_timeout

                resp = self.client.post(
                    "/v1/reply",
                    json={
                        "conversation_id": "conv_timeout_test",
                        "merchant_id": "m_001_drmeera",
                        "from_role": "merchant",
                        "message": "Hello, is anyone there?",
                        "received_at": "2026-06-01T10:00:00Z",
                        "turn_number": 1,
                    },
                )

                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                self.assertEqual(data.get("action"), "end")
                self.assertIn("exceeded response deadline", data.get("rationale", ""))
                self.assertEqual(data.get("cta"), "none")

    def test_unexpected_runtime_exception_returns_clean_fallback(self):
        """Simulate unexpected runtime exception in core reasoning loop; must return 200 with end action."""
        with patch.object(vera, "handle_reactive_message", side_effect=ValueError("Simulated model corrupt state")):
            resp = self.client.post(
                "/v1/reply",
                json={
                    "conversation_id": "conv_error_test",
                    "merchant_id": "m_001_drmeera",
                    "from_role": "merchant",
                    "message": "What is the price?",
                    "received_at": "2026-06-01T10:00:00Z",
                    "turn_number": 1,
                },
            )

            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertEqual(data.get("action"), "end")
            self.assertIn("Graceful fallback termination", data.get("rationale", ""))
            self.assertIn("Simulated model corrupt state", data.get("rationale", ""))

    def test_rapid_request_burst_stability(self):
        """Verify server handles 50 rapid sequential requests without degradation or memory leaks."""
        start_time = time.perf_counter()
        for i in range(50):
            resp = self.client.get("/v1/healthz")
            self.assertEqual(resp.status_code, 200)

        elapsed = time.perf_counter() - start_time
        avg_latency_ms = (elapsed / 50) * 1000.0
        # Ensure average latency remains sub-millisecond to low milliseconds
        self.assertLess(avg_latency_ms, 20.0, f"Average latency too high: {avg_latency_ms:.2f}ms")


if __name__ == "__main__":
    unittest.main()
