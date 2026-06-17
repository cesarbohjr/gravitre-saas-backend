"""MKT-3.2: marketplace install variable resolution."""
from __future__ import annotations

import pytest

from app.marketplace.schemas import InstallVariable
from app.marketplace.variables import (
    VariableResolutionError,
    extract_install_var_keys,
    resolve_variables,
)


def test_extract_install_var_keys_nested():
    keys = extract_install_var_keys(
        {
            "config": {
                "portal": "{{INSTALL_VAR_HUBSPOT_PORTAL}}",
                "tags": ["{{INSTALL_VAR_TEAM_NAME}}"],
            }
        }
    )
    assert keys == {"HUBSPOT_PORTAL", "TEAM_NAME"}


def test_resolve_variables_replaces_nested_json():
    resolved = resolve_variables(
        {
            "name": "Team {{INSTALL_VAR_TEAM_NAME}} playbook",
            "metadata": {"portal": "{{INSTALL_VAR_HUBSPOT_PORTAL}}"},
        },
        {"team_name": "Revenue", "HUBSPOT_PORTAL": "12345"},
        declared=[
            InstallVariable(key="TEAM_NAME", label="Team", required=True),
            InstallVariable(key="HUBSPOT_PORTAL", label="Portal", required=True),
        ],
    )
    assert resolved["name"] == "Team Revenue playbook"
    assert resolved["metadata"]["portal"] == "12345"


def test_resolve_variables_applies_defaults():
    resolved = resolve_variables(
        "{{INSTALL_VAR_TEAM_NAME}}",
        {},
        declared=[
            InstallVariable(
                key="TEAM_NAME",
                label="Team",
                required=True,
                default="Default Team",
            )
        ],
    )
    assert resolved == "Default Team"


def test_resolve_variables_blocks_missing_required():
    with pytest.raises(VariableResolutionError) as exc:
        resolve_variables(
            {"portal": "{{INSTALL_VAR_HUBSPOT_PORTAL}}"},
            {},
            declared=[
                InstallVariable(key="HUBSPOT_PORTAL", label="Portal", required=True),
            ],
        )
    assert any(err.startswith("missing:") for err in exc.value.errors)


def test_resolve_variables_blocks_unresolved_tokens():
    with pytest.raises(VariableResolutionError) as exc:
        resolve_variables(
            {"portal": "{{INSTALL_VAR_HUBSPOT_PORTAL}}"},
            {"OTHER": "value"},
            declared=[
                InstallVariable(key="HUBSPOT_PORTAL", label="Portal", required=False),
            ],
        )
    assert exc.value.errors
