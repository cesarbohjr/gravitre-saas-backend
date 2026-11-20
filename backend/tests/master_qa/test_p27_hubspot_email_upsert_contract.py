"""HubSpot P27 email upsert compatibility and receipt regression."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "scripts/p27_hubspot_sandbox_readback.py"


def test_email_batch_upsert_does_not_include_trace_id():
    tree = ast.parse(SOURCE.read_text())
    payloads = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value == "idProperty" for k in node.keys if k)
    ]
    assert payloads
    for payload in payloads:
        keys = [k.value for k in payload.keys if isinstance(k, ast.Constant)]
        assert "objectWriteTraceId" not in keys
        assert "idProperty" in keys
        assert "properties" in keys
