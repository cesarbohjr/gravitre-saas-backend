"""Network-free tests for paid acceptance inference preflight and evidence privacy."""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_acceptance_inference import classify_http, probe  # noqa: E402


class _Response:
    status = 200

    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit):
        return json.dumps({"content": [{"type": "text", "text": self.text}]}).encode()


class AcceptanceInferenceTests(unittest.TestCase):
    def test_missing_key_blocks_without_network(self):
        with patch("verify_acceptance_inference.urlopen") as request:
            self.assertEqual(probe(key="")["category"], "acceptance_credential_missing")
            request.assert_not_called()

    def test_real_success_requires_expected_model_text(self):
        with patch("verify_acceptance_inference.urlopen", return_value=_Response("READY")) as request:
            result = probe(key="acceptance-only")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["category"], "inference_verified")
        self.assertEqual(request.call_args.kwargs["timeout"], 25)
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(json.loads(sent.data)["max_tokens"], 24)

    def test_http_200_but_incomplete_response_fails_closed(self):
        with patch("verify_acceptance_inference.urlopen", return_value=_Response("Which item did you mean?")):
            result = probe(key="acceptance-only")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["category"], "unexpected_model_response")

    def test_402_and_401_are_sanitized(self):
        for code, category in ((401, "unauthorized"), (402, "insufficient_credits"), (429, "rate_limited_or_quota")):
            exception = HTTPError("https://api.anthropic.com/v1/messages", code, "SECRET RESPONSE TEXT", {}, io.BytesIO(b"secret"))
            with patch("verify_acceptance_inference.urlopen", side_effect=exception):
                result = probe(key="sk-secret")
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["category"], category)
            self.assertNotIn("secret", json.dumps(result).lower())

    def test_http_mapping_is_bounded(self):
        self.assertEqual(classify_http(403), "permission_denied")
        self.assertEqual(classify_http(404), "model_not_found")
        self.assertEqual(classify_http(503), "provider_error")


if __name__ == "__main__":
    unittest.main()
