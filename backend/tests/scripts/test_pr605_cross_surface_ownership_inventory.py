"""Offline source-inventory contracts: no app import or provider requests."""
from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pr605_cross_surface_ownership_inventory.py"
spec = importlib.util.spec_from_file_location("pr605_cross_surface_ownership_inventory", SCRIPT)
assert spec and spec.loader
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def test_literal_routes_and_config_only_names():
    result = inventory.inspect_text(
        "apps/web/lib/fixture.ts",
        'import { a } from "@/lib/a"\n'
        'const url = "/api/voice/pipecat/ws"\n'
        'const secret = process.env.API_PRIVATE_KEY\n'
        'const mode = process.env.NEXT_PUBLIC_VOICE_WS_BASE\n'
    )
    assert "/api/voice/pipecat/ws" in result["literal_api_paths"]
    assert "@/lib/a" in result["imports"]
    assert result["environment_variable_names"] == ["NEXT_PUBLIC_VOICE_WS_BASE"]
    assert "API_PRIVATE_KEY" not in repr(result)


def test_python_legacy_import_and_dynamic_dispatch_candidates():
    result = inventory.inspect_text(
        "backend/app/services/x.py",
        "from app.services import model_router\n"
        "from importlib import import_module\n"
        "handler = import_module('app.handlers')\n"
    )
    assert "app.services" in result["imports"]
    assert any(e["kind"] == "dynamic_python_dispatch_candidate" for e in result["dynamic_dispatch_candidates"])


def test_registered_target_paths_exist_and_retirement_stays_uncertified():
    report = inventory.collect()
    assert not report["missing_sources"]
    assert report["candidate_source_count"] == len(inventory.TARGETS)
    assert all(report["critical_source_assertions"].values())
    assert report["retirement_certified"] is False
    assert report["unknowns"]


def test_rpc_candidates_preserve_line_and_name_without_payload():
    result = inventory.inspect_text(
        "backend/app/services/fixture.py",
        "# client.rpc('comment_only')\n"
        "client.rpc('claim_write', {'token': 'private-payload'})\n"
        "client.rpc(fn='settle_write', params={'user': 'private-user'})\n",
    )
    assert result["rpc_call_candidates"] == [
        {"line": 2, "kind": "literal_python_rpc_candidate", "target": "claim_write"},
        {"line": 3, "kind": "literal_python_rpc_candidate", "target": "settle_write"},
    ]
    assert "private-payload" not in repr(result)
    assert "private-user" not in repr(result)
    assert "comment_only" not in repr(result)


def test_computed_or_non_identifier_rpc_names_remain_unknown():
    result = inventory.inspect_text(
        "backend/app/services/fixture.py",
        "client.rpc(selected_name, payload)\n"
        "client.rpc('customer@example.invalid', payload)\n"
        "client.rpc()\n",
    )
    assert len(result["rpc_call_candidates"]) == 3
    assert all(call["target"] is None for call in result["rpc_call_candidates"])
    assert all(call["kind"] == "unresolved_python_rpc_candidate"
               for call in result["rpc_call_candidates"])
    assert "customer@example.invalid" not in repr(result)
    assert "selected_name" not in repr(result)


def test_inventory_covers_governed_callers_without_runtime_certification():
    report = inventory.collect()
    owners = {item["candidate_owner"] for item in report["source_files"]}
    assert {
        "agent_intelligence", "play_router", "workflow_router",
        "canvas_write_authority", "workflow_worker", "workflow_recovery",
    } <= owners
    assert report["retirement_certified"] is False
    assert all(item["source_type"] == "static_source_only"
               for item in report["source_files"])


def test_route_and_worker_registration_candidates_do_not_export_arguments():
    result = inventory.inspect_text("backend/app/fixture.py",
        "@router.websocket('/ws')\nasync def handler():\n    asyncio.create_task(work('private-payload'))\n"
        "app.include_router(router)\nclient.enqueue('private-job')\n")
    assert result["route_registration_candidates"] == [{"line": 1, "method": "WEBSOCKET", "target": "/ws", "handler": "handler"}]
    assert {item["kind"] for item in result["entrypoint_candidates"]} == {"create_task", "include_router", "enqueue"}
    assert "private-payload" not in repr(result) and "private-job" not in repr(result)


def test_frontend_transport_and_backend_registration_are_inventoried():
    report = inventory.collect()
    by_owner = {item["candidate_owner"]: item for item in report["source_files"]}
    assert any(item["kind"] == "new WebSocket" for item in by_owner["voice_duplex_hook"]["entrypoint_candidates"])
    assert any(item["kind"] == "include_router" for item in by_owner["backend_router_registration"]["entrypoint_candidates"])
    assert any(item["method"] == "WEBSOCKET" and item["target"] == "/ws" for item in by_owner["voice_ws_router"]["route_registration_candidates"])
    assert "agent_job_worker" in by_owner
    assert report["runtime_dispatch_verified"] is False
    assert report["retirement_certified"] is False
