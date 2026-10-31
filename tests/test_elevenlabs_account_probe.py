import importlib.util
import io
import json
from pathlib import Path
import unittest
from urllib.error import HTTPError
from unittest.mock import Mock

path = Path(__file__).resolve().parents[1] / "scripts/verify_elevenlabs_account.py"
spec = importlib.util.spec_from_file_location("account_check", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AccountProbeTests(unittest.TestCase):
    def opener(self, data, status=200):
        response = Mock(status=status)
        response.read.return_value = json.dumps(data).encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return Mock(open=Mock(return_value=response))

    def test_uses_exact_key_for_one_read_only_request_and_sanitizes_account(self):
        opener = self.opener({"tier":"starter", "status":"active",
            "character_count":1200, "character_limit":30000,
            "email":"private@example.test", "xi_api_key":"private-key",
            "user_id":"private-user", "workspace_id":"private-workspace",
            "open_invoices":[{"payment_details":"private-billing"}]})
        report = module.probe({"ELEVENLABS_API_KEY":"fixture-key"}, opener)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, module.URL)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("Xi-api-key"), "fixture-key")
        opener.open.assert_called_once()
        self.assertEqual(report["remaining_reported_units"], 28800)
        self.assertTrue(report["tier_matches_reported_starter"])
        self.assertEqual(report["status"], "OBSERVED")
        self.assertEqual(report["key_specific_credit_cap"], "NOT VERIFIED")
        self.assertFalse(report["certified"])
        for private in ("private", "fixture-key"):
            self.assertNotIn(private, json.dumps(report))

    def test_missing_key_makes_no_request(self):
        opener = Mock()
        self.assertEqual(module.probe({}, opener)["status"], "NOT RUN")
        opener.open.assert_not_called()

    def test_read_permissions_failure_does_not_claim_zero_credits(self):
        opener = Mock()
        opener.open.side_effect = HTTPError(module.URL, 403, "secret body", {}, io.BytesIO(b"secret"))
        report = module.probe({"ELEVENLABS_API_KEY":"fixture-key"}, opener)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["http_status"], 403)
        self.assertNotIn("remaining_reported_units", report)
        self.assertNotIn("secret body", json.dumps(report))

    def test_numeric_booleans_negative_and_string_values_are_not_usage(self):
        for invalid in (True, -1, "30000", None, 10**16):
            with self.subTest(invalid=invalid):
                report = module.sanitize_subscription({"tier":"starter",
                    "character_count":invalid, "character_limit":30000})
                self.assertNotIn("character_count", report)
                self.assertNotIn("remaining_reported_units", report)

    def test_other_tier_is_observed_without_claiming_account_identity(self):
        report = module.probe({"ELEVENLABS_API_KEY":"fixture-key"},
            self.opener({"tier":"free", "status":"active", "character_count":0,"character_limit":0}))
        self.assertFalse(report["tier_matches_reported_starter"])
        self.assertEqual(report["workspace_identity"], "NOT VERIFIED")

    def test_invalid_and_oversized_bodies_never_leak(self):
        for body in (b"private-key", b"x"*262145, b"[]"):
            with self.subTest(size=len(body)):
                opener = self.opener({})
                opener.open.return_value.read.return_value = body
                report = module.probe({"ELEVENLABS_API_KEY":"fixture-key"}, opener)
                self.assertEqual(report["status"], "BLOCKED")
                self.assertNotIn("private-key", json.dumps(report))

    def test_cross_origin_redirect_is_not_followed(self):
        self.assertIsNone(module.NoRedirect().redirect_request(
            None,None,302,"redirect",{}, "https://other.example/steal"))

    def test_subscription_rejection_keeps_only_fixed_permission_diagnostic(self):
        opener = Mock()
        body = json.dumps({"detail":{"status":"missing_permissions",
            "message":"fixture-key private-user missing user_read"}}).encode()
        opener.open.side_effect = HTTPError(module.URL, 401, "private", {}, io.BytesIO(body))
        report = module.probe({"ELEVENLABS_API_KEY":"fixture-key"}, opener)
        self.assertEqual(report["provider_reason"], "missing_permissions")
        self.assertEqual(report["required_permission"], "user_read")
        self.assertNotIn("private", json.dumps(report))
        self.assertNotIn("fixture-key", json.dumps(report))
        for malformed in (b"private", b"[]", b'{"detail":[]}', b'{"detail":{"status":["private"]}}'):
            self.assertEqual(module.rejection_reason(malformed), {})

if __name__ == "__main__":
    unittest.main()

