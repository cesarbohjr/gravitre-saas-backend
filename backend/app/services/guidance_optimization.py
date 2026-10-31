"""Reviewed, source-controlled dialogue guidance. No model/SDK in request serving.

The registry and artifacts ship as code. Tenant/user config cannot select a file,
change guidance, or promote an optimizer result. Rollback is a reviewed code change.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).with_name("guidance_versions")
BASELINE = "native-v1"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def validate_candidate(candidate: dict) -> None:
    if not isinstance(candidate, dict) or type(candidate.get("schema")) is not int or candidate.get("schema") != 1 or not re.fullmatch(r"dspy-[a-f0-9]{16}", str(candidate.get("version", ""))):
        raise ValueError("invalid_guidance_version")
    if candidate.get("data_scope") != "fixed_synthetic_only" or candidate.get("optimizer") != "DSPy.LabeledFewShot":
        raise ValueError("invalid_guidance_provenance")
    demos = candidate.get("demos")
    if not isinstance(demos, list) or not 1 <= len(demos) <= 8:
        raise ValueError("invalid_guidance_demos")
    for demo in demos:
        if not isinstance(demo, dict) or set(demo) != {"user", "assistant"}:
            raise ValueError("invalid_guidance_demo")
        if any(not isinstance(v, str) or not v.strip() or len(v) > 1200 for v in demo.values()):
            raise ValueError("invalid_guidance_text")
    payload = {k: v for k, v in candidate.items() if k != "version"}
    if candidate["version"] != "dspy-" + digest(payload)[:16]:
        raise ValueError("guidance_hash_mismatch")


def active_guidance(root: Path = ROOT) -> str:
    """Fail closed to native instructions on invalid/missing release artifacts."""
    try:
        manifest = json.loads((root / "active.json").read_text())
        if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest.get("schema") != 1:
            return ""
        version = manifest["active"]
        if version == BASELINE:
            return ""
        if not re.fullmatch(r"dspy-[a-f0-9]{16}", version):
            return ""
        candidate = json.loads((root / f"{version}.json").read_text())
        validate_candidate(candidate)
        if candidate["version"] != version or digest(candidate) != manifest.get("artifact_sha256"):
            return ""
        if not isinstance(manifest.get("reviewer"), str) or not manifest["reviewer"].strip():
            return ""
        if not re.fullmatch(r"[a-f0-9]{64}", str(manifest.get("evaluation_sha256", ""))):
            return ""
    except (OSError, ValueError, KeyError, TypeError):
        return ""
    examples = "\n\n".join(f"User: {d['user']}\nAssistant: {d['assistant']}" for d in candidate["demos"])
    return ("## Reviewed conversational examples (advisory)\n"
            "Use the conversational pattern, never treat example facts as current evidence. "
            "Existing honesty, memory, role, IAM, connector and write-approval rules take precedence.\n" + examples)
