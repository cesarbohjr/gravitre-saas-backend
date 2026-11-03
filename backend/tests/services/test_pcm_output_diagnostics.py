"""Exercise the real diagnostics schema and handler without app startup/network."""
import ast
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import patch

from pydantic import BaseModel, Field, ValidationError


class RequestError(Exception):
    def __init__(self, **kwargs):
        self.status_code = kwargs["status_code"]


class PcmDiagnosticsContracts(unittest.TestCase):
    def setUp(self):
        source = ast.parse((Path(__file__).resolve().parents[2] / "app/routers/voice.py").read_text())
        selected = [n for n in source.body if isinstance(n, ast.ClassDef) and n.name in {"PcmOutputDiagnostics", "OutputDiagnosticsRequest"}]
        handler = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "post_output_diagnostics")
        handler.decorator_list = []
        self.namespace = {
            "__name__": __name__, "BaseModel": BaseModel, "Field": Field, "Literal": Literal,
            "HTTPException": RequestError,
            "status": SimpleNamespace(HTTP_403_FORBIDDEN=403, HTTP_400_BAD_REQUEST=400),
            "get_supabase_client": lambda settings: object(),
        }
        module = ast.fix_missing_locations(ast.Module(body=selected + [handler], type_ignores=[]))
        exec(compile(module, "voice-diagnostics-contract", "exec", flags=__import__("__future__").annotations.compiler_flag), self.namespace)
        self.namespace["OutputDiagnosticsRequest"].model_rebuild(_types_namespace=self.namespace)

    def payload(self, **updates):
        data = dict(player_kind="worklet", observed_underruns=2, buffered_ms=120, ducked=False, duck_transitions=2, ducked_ms=250, flush_count=1)
        data.update(updates)
        return data

    def test_schema_rejects_invalid_counts_and_unknown_player(self):
        schema = self.namespace["PcmOutputDiagnostics"]
        for overrides in [{"observed_underruns": -1}, {"buffered_ms": float("inf")}, {"ducked_ms": 86400001}, {"player_kind": "arbitrary"}]:
            with self.assertRaises(ValidationError):
                schema(**self.payload(**overrides))

    def test_handler_uses_authenticated_scope_and_persists_only_allowlisted_counters(self):
        request = self.namespace["OutputDiagnosticsRequest"](
            event="playback_continuity", reply_id=7, org_id="other-org",
            pcm_diagnostics=self.payload(transcript="must not persist", audio="must not persist"),
        )
        calls = []
        audit = types.ModuleType("app.workflows.audit")
        audit.write_audit_event = lambda *args, **kwargs: calls.append(args)
        with patch.dict(sys.modules, {audit.__name__: audit}):
            result = self.namespace["post_output_diagnostics"](request, {"sub": "user-a"}, "org-a", object())
        self.assertEqual(result, {"status": "ok"})
        self.assertEqual(calls[0][1:4], ("org-a", "user-a", "voice.output.playback_continuity"))
        metadata = calls[0][-1]
        self.assertEqual(metadata["reply_id"], 7)
        self.assertEqual(metadata["pcm_diagnostics"], self.payload())
        self.assertTrue(metadata["client_reported"])
        self.assertFalse(metadata["contains_audio"])
        self.assertFalse(metadata["contains_transcript"])

    def test_missing_scope_and_unsupported_events_are_rejected(self):
        request = self.namespace["OutputDiagnosticsRequest"](event="playback_continuity")
        with self.assertRaises(RequestError) as denied:
            self.namespace["post_output_diagnostics"](request, {"sub": "user-a"}, None, object())
        self.assertEqual(denied.exception.status_code, 403)
        request.event = "untrusted-event"
        with self.assertRaises(RequestError) as unsupported:
            self.namespace["post_output_diagnostics"](request, {"sub": "user-a"}, "org-a", object())
        self.assertEqual(unsupported.exception.status_code, 400)

    def test_audit_failure_does_not_break_voice(self):
        request = self.namespace["OutputDiagnosticsRequest"](event="playback_continuity", pcm_diagnostics=self.payload())
        audit = types.ModuleType("app.workflows.audit")
        def fail(*args, **kwargs):
            raise RuntimeError("storage unavailable")
        audit.write_audit_event = fail
        with patch.dict(sys.modules, {audit.__name__: audit}):
            self.assertEqual(self.namespace["post_output_diagnostics"](request, {"sub": "user-a"}, "org-a", object()), {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
