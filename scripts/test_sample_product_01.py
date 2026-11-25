"""Regression tests for the sample product readiness boundary."""
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from sample_product_01 import ScenarioError, wait_ready


class Response(io.BytesIO):
    status = 200


class ReadinessTests(unittest.TestCase):
    def test_retries_nonready_responses_until_ready_object(self):
        responses = [Response(body) for body in (
            b"", b"<html>warming</html>", b"{broken", b"\xff", b"[]",
            b"null", b"true", b'{"status":"starting"}', b'{"status":"ready"}',
        )]
        with patch("sample_product_01.urlopen", side_effect=responses) as request, \
             patch("sample_product_01.time.sleep") as sleep:
            self.assertEqual(wait_ready("http://localhost"), {"status": "ready"})
        self.assertEqual(request.call_count, len(responses))
        self.assertEqual(sleep.call_count, len(responses) - 1)

    def test_http_error_body_is_not_in_readiness_failure(self):
        error = HTTPError("http://localhost/readyz", 503, "Unavailable", {},
                          io.BytesIO(b"private-response-marker"))
        with patch("sample_product_01.urlopen", side_effect=error), \
             patch("sample_product_01.time.time", side_effect=[0, 0, 46]), \
             patch("sample_product_01.time.sleep"):
            with self.assertRaises(ScenarioError) as raised:
                wait_ready("http://localhost")
        self.assertIn("503", str(raised.exception))
        self.assertNotIn("private-response-marker", str(raised.exception))

    def test_invalid_json_body_is_not_in_readiness_failure(self):
        with patch("sample_product_01.urlopen", return_value=Response(b"private-response-marker")), \
             patch("sample_product_01.time.time", side_effect=[0, 0, 46]), \
             patch("sample_product_01.time.sleep"):
            with self.assertRaises(ScenarioError) as raised:
                wait_ready("http://localhost")
        self.assertIn("invalid JSON", str(raised.exception))
        self.assertNotIn("private-response-marker", str(raised.exception))

    def test_retries_socket_timeout(self):
        with patch("sample_product_01.urlopen", side_effect=[TimeoutError(), Response(b'{"status":"ready"}')]), \
             patch("sample_product_01.time.sleep"):
            self.assertEqual(wait_ready("http://localhost"), {"status": "ready"})


if __name__ == "__main__":
    unittest.main()
