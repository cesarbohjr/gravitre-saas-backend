"""Tenant Play installation and run contracts.

These records coordinate existing Gravitre primitives. A Play run never executes
connector actions directly; canonical workflow runtime remains execution authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.plays.contracts import PlayMaturity


@dataclass(frozen=True)
class PlayInstallation:
    id: str
    org_id: str
    play_key: str
    play_version: str
    environment_name: str
    operating_mode: PlayMaturity
    status: str
    goal_id: str | None = None
    configuration: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operating_mode"] = self.operating_mode.value
        return payload


@dataclass(frozen=True)
class PlayRun:
    id: str
    org_id: str
    installation_id: str
    play_key: str
    play_version: str
    operating_mode: PlayMaturity
    trigger_type: str
    status: str
    workflow_run_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["operating_mode"] = self.operating_mode.value
        return payload


def canonical_workflow_run_parameters(
    installation: PlayInstallation,
    *,
    play_run_id: str,
) -> dict[str, Any]:
    """Metadata injected into canonical workflow runs for traceability."""
    return {
        "play": {
            "key": installation.play_key,
            "version": installation.play_version,
            "installation_id": installation.id,
            "run_id": play_run_id,
            "operating_mode": installation.operating_mode.value,
            "execution_authority": "canonical_workflow_runtime",
        }
    }
