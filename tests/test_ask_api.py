import os
import unittest
from unittest.mock import patch

from api import ask


class AskApiTests(unittest.TestCase):
    def test_default_cors_allowlist_is_exact(self):
        request = object.__new__(ask.handler)
        request.headers = {"Origin": "https://projectfiner.com"}
        self.assertTrue(request._origin_is_allowed())

        request.headers = {"Origin": "https://projectfiner.com.attacker.example"}
        self.assertFalse(request._origin_is_allowed())

    def test_deployment_can_add_an_origin_explicitly(self):
        with patch.dict(os.environ, {"ALLOWED_ORIGINS": "http://localhost:4321"}):
            self.assertIn("http://localhost:4321", ask._allowed_origins())

    def test_state_detection_avoids_cross_state_queries(self):
        self.assertEqual(ask.detect_state_in_query("KCC totals in Assam"), "Assam")
        self.assertIsNone(ask.detect_state_in_query("Compare Assam and Meghalaya"))

    def test_request_budget_enforces_client_and_global_limits(self):
        with patch.dict(os.environ, {
            "ASK_MAX_REQUESTS_PER_CLIENT": "2",
            "ASK_CLIENT_WINDOW_SECONDS": "60",
            "ASK_MAX_REQUESTS_PER_WINDOW": "3",
            "ASK_TOTAL_WINDOW_SECONDS": "60",
        }):
            ask._reset_rate_limit_state()
            try:
                allowed, retry_after, scope, remaining = (
                    ask._consume_request_budget("client-a", now=100)
                )
                self.assertTrue(allowed)
                self.assertEqual(scope, "")
                self.assertEqual(remaining, 1)

                allowed, retry_after, scope, remaining = (
                    ask._consume_request_budget("client-a", now=101)
                )
                self.assertTrue(allowed)
                self.assertEqual(remaining, 0)

                allowed, retry_after, scope, remaining = (
                    ask._consume_request_budget("client-a", now=102)
                )
                self.assertFalse(allowed)
                self.assertEqual(scope, "client")
                self.assertGreaterEqual(retry_after, 1)

                allowed, retry_after, scope, remaining = (
                    ask._consume_request_budget("client-b", now=103)
                )
                self.assertTrue(allowed)

                allowed, retry_after, scope, remaining = (
                    ask._consume_request_budget("client-c", now=104)
                )
                self.assertFalse(allowed)
                self.assertEqual(scope, "global")
                self.assertGreaterEqual(retry_after, 1)
            finally:
                ask._reset_rate_limit_state()

    def test_invalid_rate_limit_environment_values_use_safe_bounds(self):
        with patch.dict(os.environ, {
            "ASK_MAX_REQUESTS_PER_CLIENT": "not-an-int",
            "ASK_CLIENT_WINDOW_SECONDS": "0",
            "ASK_MAX_REQUESTS_PER_WINDOW": "999999",
            "ASK_TOTAL_WINDOW_SECONDS": "1",
        }):
            config = ask._rate_limit_config()
            self.assertEqual(config["client_limit"], 10)
            self.assertEqual(config["client_window"], 1)
            self.assertEqual(config["total_limit"], 10000)
            self.assertEqual(config["total_window"], 60)

    def test_index_load_is_lazy_and_cached(self):
        old_chunks, old_bm25 = ask.CHUNKS, ask.BM25
        ask.CHUNKS = None
        ask.BM25 = None
        chunks = [{"state": "Assam"}]
        bm25 = {"n_docs": 1}
        try:
            with patch.object(ask, "_fetch_json", side_effect=[chunks, bm25]) as fetch:
                ask._load_index()
                ask._load_index()
                self.assertEqual(fetch.call_count, 2)
            self.assertIs(ask.CHUNKS, chunks)
            self.assertIs(ask.BM25, bm25)
        finally:
            ask.CHUNKS, ask.BM25 = old_chunks, old_bm25


if __name__ == "__main__":
    unittest.main()
