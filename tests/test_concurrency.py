"""Concurrency and multi-threaded stress test suite (REM-05)."""

import concurrent.futures
import threading
import unittest
from starlette.testclient import TestClient

from bot import app, engine
from vera.context.engine import ContextEngine
from vera.models.conversation import State
from vera.trigger.suppression import SuppressionStore


class TestConcurrencyAndThreadSafety(unittest.TestCase):
    """Stress tests verifying thread safety under concurrent requests and ingestion."""

    def setUp(self):
        self.client = TestClient(app)
        self.context_engine = ContextEngine()

    def _sample_category(self, slug: str) -> dict:
        return {
            "slug": slug,
            "display_name": f"Category {slug}",
            "voice": {"tone": "clinical"},
            "offer_catalog": [],
            "peer_stats": {
                "avg_rating": 4.4,
                "avg_review_count": 62,
                "avg_ctr": 0.030,
            },
            "digest": [],
        }

    def _sample_merchant(self, mid: str, name: str = "Conflict Clinic") -> dict:
        return {
            "merchant_id": mid,
            "category_slug": "dentists",
            "identity": {
                "name": name,
                "city": "Delhi",
                "locality": "Lajpat Nagar",
                "verified": True,
            },
            "subscription": {
                "status": "active",
                "plan": "Pro",
                "days_remaining": 60,
            },
            "performance": {
                "window_days": 30,
                "views": 2000,
                "calls": 25,
                "directions": 45,
                "ctr": 0.021,
            },
            "customer_aggregate": {
                "total_unique_ytd": 450,
                "lapsed_180d_plus": 40,
                "retention_6mo_pct": 0.42,
            },
        }

    def test_50_concurrent_context_pushes_via_api(self):
        """Verify 50 concurrent context ingestion requests execute without data corruption."""
        def push_category(index: int):
            cat_payload = self._sample_category(f"cat_concurrent_{index}")
            resp = self.client.post(
                "/v1/context",
                json={
                    "scope": "category",
                    "context_id": f"cat_concurrent_{index}",
                    "version": 1,
                    "payload": cat_payload,
                    "delivered_at": "2026-06-01T10:00:00Z",
                },
            )
            return resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(push_category, i) for i in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All 50 pushes must succeed
        for status_code, body in results:
            self.assertEqual(status_code, 200)
            self.assertTrue(body.get("accepted"))

    def test_concurrent_version_conflict_resolution(self):
        """Verify parallel ingestion of conflicting versions reliably rejects stale updates with 409."""
        # Initial ingestion of version 5
        base_payload = self._sample_merchant("m_conflict_test", "Conflict Dental Clinic v5")
        resp_init = self.client.post(
            "/v1/context",
            json={
                "scope": "merchant",
                "context_id": "m_conflict_test",
                "version": 5,
                "payload": base_payload,
                "delivered_at": "2026-06-01T10:00:00Z",
            },
        )
        self.assertEqual(resp_init.status_code, 200)

        # Attempt 20 concurrent updates: 10 with stale version 3, 10 with version 6
        def push_version(ver: int):
            payload = self._sample_merchant("m_conflict_test", f"Conflict Dental Clinic v{ver}")
            resp = self.client.post(
                "/v1/context",
                json={
                    "scope": "merchant",
                    "context_id": "m_conflict_test",
                    "version": ver,
                    "payload": payload,
                    "delivered_at": "2026-06-01T10:00:00Z",
                },
            )
            return ver, resp.status_code, resp.json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # 10 stale requests with version 3, 10 requests with version 6
            tasks = [3] * 10 + [6] * 10
            futures = [executor.submit(push_version, v) for v in tasks]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify all version 3 attempts were strictly rejected with 409 CONFLICT
        stale_results = [r for r in results if r[0] == 3]
        for ver, status_code, body in stale_results:
            self.assertEqual(status_code, 409)
            self.assertFalse(body.get("accepted"))
            self.assertEqual(body.get("reason"), "stale_version")

        # Exactly one or more version 6 attempts should succeed, and subsequent version 6 attempts become stale/rejected
        v6_results = [r for r in results if r[0] == 6]
        success_count = sum(1 for _, code, _ in v6_results if code == 200)
        conflict_count = sum(1 for _, code, _ in v6_results if code == 409)
        self.assertGreaterEqual(success_count, 1)
        self.assertEqual(success_count + conflict_count, 10)

    def test_concurrent_conversation_state_machine_turns(self):
        """Verify thread safety when 50 concurrent conversations transition states simultaneously."""
        def run_conversation(conv_idx: int):
            cid = f"conv_thread_{conv_idx}"
            conv = self.context_engine.create_or_get_conversation(
                conversation_id=cid,
                merchant_id="m_001_drmeera",
                trigger_id="trg_001",
            )
            # Add initial turn
            self.context_engine.add_turn(cid, from_role="vera", message="Pitch message")
            # Transition
            trans = self.context_engine.transition_conversation(cid, user_intent="inquiry")
            return trans.to_state if trans else None

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(run_conversation, i) for i in range(50)]
            outcomes = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(outcomes), 50)
        for state_val in outcomes:
            self.assertEqual(state_val, State.QUESTION)

    def test_suppression_store_concurrent_access(self):
        """Verify thread safety of SuppressionStore with 100 concurrent read/write threads."""
        store = SuppressionStore()
        errors = []

        def worker(idx: int):
            try:
                key = f"suppression:key:{idx % 5}"
                store.record_suppression(key=key, trigger_id=f"trg_{idx}")
                is_supp = store.is_suppressed(key)
                if not is_supp:
                    errors.append(f"Key {key} expected to be suppressed")
                keys = store.get_active_keys()
                if not isinstance(keys, list):
                    errors.append("Keys not a list")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Suppression store errors under load: {errors}")


if __name__ == "__main__":
    unittest.main()
