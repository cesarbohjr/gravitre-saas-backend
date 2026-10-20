"""Non-secret account inputs for headless OAuth, reviewed against Nango templates.

Source: NangoHQ/nango packages/providers/providers.yaml, retrieved 2026-10-20.
Keep credentials, automated fields and arbitrary auth URLs out of this contract.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

_INPUTS = json.loads(Path(__file__).with_suffix(".json").read_text())


def oauth_input_fields(vendor: str) -> list[dict]:
    return _INPUTS.get(vendor, [])


def validate_oauth_inputs(vendor: str, values: dict[str, str]) -> dict[str, str]:
    fields = oauth_input_fields(vendor)
    if set(values) - {field["key"] for field in fields}:
        raise ValueError("Unsupported account setting")
    result = {}
    for field in fields:
        value = values.get(field["key"], "").strip()
        if not value and field["required"]:
            raise ValueError(f"{field['label']} is required")
        if not value:
            continue
        if len(value) > 253 or (field.get("enum") and value not in field["enum"]):
            raise ValueError(f"Invalid {field['label']}")
        if field.get("pattern") and not re.fullmatch(field["pattern"], value):
            raise ValueError(f"Invalid {field['label']}")
        if field.get("format") == "hostname":
            if not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", value):
                raise ValueError(f"Enter a hostname for {field['label']}")
            # These inputs form authorization/token hosts; never accept arbitrary origins.
            suffixes = {"servicenow": (".service-now.com",), "wrike": (".wrike.com", ".wrike.eu")}
            if vendor in suffixes and not any(value.lower().endswith(s) for s in suffixes[vendor]):
                raise ValueError(f"Enter a supported {field['label']}")
        result[field["key"]] = value
    return result
