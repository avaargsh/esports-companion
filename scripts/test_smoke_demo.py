"""Regression tests for the HTTP smoke readiness boundary."""
import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from smoke_demo import SmokeError, wait_ready


class Response(io.BytesIO):
    status = 200


class ReadinessTests(unittest.TestCase):
    def test_retries_incomplete_responses_until_ready(self):
        responses = [Response(body) for body in (
            b"", b"<html>warming</html>", b"{broken", b"\xff", b"[]",
            b"null", b"true", b'{"status":"starting"}',
            b'{"status":"ready"}', b'{"status":"ready","dependencies":[]}',
            b'{"status":"ready","dependencies":{}}',
        )]
        with patch("smoke_demo.urlopen", side_effect=responses) as request, \
             patch("smoke_demo.time.sleep") as sleep:
            self.assertEqual(wait_ready(), {"status": "ready", "dependencies": {}})
        self.assertEqual(request.call_count, len(responses))
        self.assertEqual(sleep.call_count, len(responses) - 1)

    def test_http_error_body_is_not_in_readiness_failure(self):
        error = HTTPError("http://localhost/readyz", 503, "Unavailable", {},
                          io.BytesIO(b"private-response-marker"))
        with patch("smoke_demo.urlopen", side_effect=error), \
             patch("smoke_demo.time.time", side_effect=[0, 0, 46]), \
             patch("smoke_demo.time.sleep"):
            with self.assertRaises(SmokeError) as raised:
                wait_ready()
        self.assertIn("503", str(raised.exception))
        self.assertNotIn("private-response-marker", str(raised.exception))

    def test_invalid_json_body_is_not_in_readiness_failure(self):
        with patch("smoke_demo.urlopen", return_value=Response(b"private-response-marker")), \
             patch("smoke_demo.time.time", side_effect=[0, 0, 46]), \
             patch("smoke_demo.time.sleep"):
            with self.assertRaises(SmokeError) as raised:
                wait_ready()
        self.assertIn("invalid JSON", str(raised.exception))
        self.assertNotIn("private-response-marker", str(raised.exception))

    def test_retries_socket_timeout(self):
        with patch("smoke_demo.urlopen", side_effect=[TimeoutError(), Response(b'{"status":"ready","dependencies":{}}')]), \
             patch("smoke_demo.time.sleep"):
            self.assertEqual(wait_ready(), {"status": "ready", "dependencies": {}})


if __name__ == "__main__":
    unittest.main()
