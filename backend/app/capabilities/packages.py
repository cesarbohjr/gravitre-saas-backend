"""Portable capability packages for Agent Skills, MCP and plugin manifests.

This is an ingestion/normalization layer only. Imported packages never execute
code directly; execution remains owned by Gravitre's canonical tool/workflow
runtime, approval policy and verified-write lifecycle.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
import re

PackageFormat = Literal["agent_skill", "openai_plugin", "claude_plugin", "gravitre", "mcp", "unknown"]
RiskLevel = Literal["low", "moderate", "high", "blocked"]

_REUSABLE_LICENSES = {
    "apache-2.0", "apache 2.0", "mit", "bsd-2-clause", "bsd-3-clause",
    "isc", "mpl-2.0", "cc-by-4.0",
}
_REVIEW_LICENSES = {"gpl-2.0", "gpl-3.0", "agpl-3.0", "lgpl-3.0"}
_BLOCKED_LICENSE_MARKERS = ("proprietary", "all rights reserved", "no redistribution", "no derivative")


@dataclass(frozen=True)
class PackageComponent:
    kind: Literal["skill", "mcp", "connector", "agent", "play", "template", "command", "hook", "ui_extension"]
    name: str
    source: str | None = None
    executable: bool = False


@dataclass(frozen=True)
class PackageInspection:
    format: PackageFormat
    name: str
    version: str | None
    description: str | None
    license: str | None
    license_policy: Literal["allow", "review", "block"]
    components: tuple[PackageComponent, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    network_hosts: tuple[str, ...] = field(default_factory=tuple)
    has_executable_code: bool = False
    has_write_tools: bool = False
    risk: RiskLevel = "low"
    findings: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["components"] = [asdict(c) for c in self.components]
        return row


def _clean_license(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def license_policy(value: Any) -> Literal["allow", "review", "block"]:
    lic = (_clean_license(value) or "").lower()
    if not lic:
        return "review"
    if any(marker in lic for marker in _BLOCKED_LICENSE_MARKERS):
        return "block"
    if lic in _REUSABLE_LICENSES:
        return "allow"
    if lic in _REVIEW_LICENSES:
        return "review"
    return "review"


def _frontmatter(skill_md: str | None) -> dict[str, str]:
    text = str(skill_md or "")
    if not text.startswith("---"):
        return {}
    try:
        block = text.split("---", 2)[1]
    except IndexError:
        return {}
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _components_from_manifest(manifest: dict[str, Any], skill_md: str | None) -> list[PackageComponent]:
    out: list[PackageComponent] = []
    fm = _frontmatter(skill_md)
    if skill_md:
        out.append(PackageComponent("skill", fm.get("name") or str(manifest.get("name") or "skill"), "SKILL.md"))
    aliases = {
        "skills": "skill", "mcpServers": "mcp", "mcp_servers": "mcp",
        "connectors": "connector", "agents": "agent", "plays": "play",
        "templates": "template", "commands": "command", "hooks": "hook",
        "apps": "ui_extension", "extensions": "ui_extension",
    }
    for key, kind in aliases.items():
        value = manifest.get(key)
        if isinstance(value, dict):
            for name, spec in value.items():
                executable = kind in {"hook", "command"} or (
                    isinstance(spec, dict) and bool(spec.get("command") or spec.get("script"))
                )
                out.append(PackageComponent(kind, str(name), key, executable))  # type: ignore[arg-type]
        elif isinstance(value, list):
            for index, spec in enumerate(value):
                if isinstance(spec, str):
                    name = spec
                    executable = kind in {"hook", "command"}
                elif isinstance(spec, dict):
                    name = str(spec.get("name") or spec.get("id") or f"{key}-{index + 1}")
                    executable = kind in {"hook", "command"} or bool(spec.get("command") or spec.get("script"))
                else:
                    continue
                out.append(PackageComponent(kind, name, key, executable))  # type: ignore[arg-type]
    return out


def detect_format(manifest: dict[str, Any], skill_md: str | None = None) -> PackageFormat:
    marker = " ".join(str(manifest.get(k) or "") for k in ("schema", "format", "kind", "type")).lower()
    if "gravitre" in marker:
        return "gravitre"
    if "claude" in marker or manifest.get("claude"):
        return "claude_plugin"
    if "codex" in marker or "openai" in marker or manifest.get("apps") is not None:
        return "openai_plugin"
    if manifest.get("mcpServers") is not None or manifest.get("mcp_servers") is not None:
        return "mcp" if not skill_md else "agent_skill"
    if skill_md:
        return "agent_skill"
    return "unknown"


def inspect_package(manifest: dict[str, Any] | None = None, *, skill_md: str | None = None) -> PackageInspection:
    manifest = dict(manifest or {})
    fm = _frontmatter(skill_md)
    name = str(manifest.get("name") or fm.get("name") or "unnamed-capability").strip()
    description = str(manifest.get("description") or fm.get("description") or "").strip() or None
    version = str(manifest.get("version") or "").strip() or None
    lic = _clean_license(manifest.get("license") or fm.get("license"))
    policy = license_policy(lic)
    components = _components_from_manifest(manifest, skill_md)

    permissions = set(_list_strings(manifest.get("permissions")))
    for scope in _list_strings(manifest.get("scopes")):
        permissions.add(scope)

    network_hosts: set[str] = set()
    serialized = repr(manifest)
    for host in re.findall(r"https?://([A-Za-z0-9._-]+)", serialized):
        network_hosts.add(host.lower())

    has_exec = any(c.executable for c in components)
    write_markers = ("write", "create", "update", "delete", "send", "publish", "execute", "admin")
    has_write = any(any(marker in p.lower() for marker in write_markers) for p in permissions)
    findings: list[str] = []
    if policy == "block":
        findings.append("Package license prohibits or appears to prohibit redistribution/use.")
    elif policy == "review":
        findings.append("Package license requires review before organization-wide installation.")
    if has_exec:
        findings.append("Package declares executable commands/hooks; execution must remain sandboxed and policy-gated.")
    if has_write:
        findings.append("Package requests write-capable permissions; Gravitre approval and verified-write policy must apply.")
    if network_hosts:
        findings.append("Package references external network destinations; allowlist review required.")

    if policy == "block":
        risk: RiskLevel = "blocked"
    elif has_exec and (has_write or network_hosts):
        risk = "high"
    elif has_exec or has_write or policy == "review":
        risk = "moderate"
    else:
        risk = "low"

    return PackageInspection(
        format=detect_format(manifest, skill_md),
        name=name,
        version=version,
        description=description,
        license=lic,
        license_policy=policy,
        components=tuple(components),
        permissions=tuple(sorted(permissions)),
        network_hosts=tuple(sorted(network_hosts)),
        has_executable_code=has_exec,
        has_write_tools=has_write,
        risk=risk,
        findings=tuple(findings),
    )


def installation_allowed(inspection: PackageInspection) -> bool:
    return inspection.license_policy != "block" and inspection.risk != "blocked"
