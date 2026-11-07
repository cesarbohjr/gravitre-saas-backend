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
