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
