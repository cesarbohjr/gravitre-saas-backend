"""Static security review for portable capability bundles.

This scanner never executes package content. Findings are evidence for admin and
publisher review, not a claim that code is safe merely because no pattern matched.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

SCRIPT_SUFFIXES = (".py", ".js", ".ts", ".sh", ".bash", ".ps1")
PROMPT_SUFFIXES = (".md", ".txt")
_HIGH_RISK_CODE = (
    (r"\b(?:eval|exec)\s*\(", "dynamic_code_execution"),
    (r"\b(?:os\.system|subprocess\.(?:run|popen|call|check_output))\b", "shell_process_execution"),
    (r"\b(?:child_process|spawn|execSync|execFile)\b", "shell_process_execution"),
    (r"\b(?:rm\s+-rf|shutil\.rmtree|unlink\s*\(|remove\s*\()","destructive_filesystem"),
)
_SECRET_ACCESS = (
    r"\b(?:os\.environ|getenv|process\.env|secret|api[_-]?key|access[_-]?token|password|private[_-]?key)\b"
)
_NETWORK_ACCESS = (
    r"\b(?:requests\.|httpx\.|fetch\s*\(|axios\.|urllib\.|curl\s+|wget\s+)\b"
)
_FILE_ACCESS = (
    r"\b(?:open\s*\(|write_text\s*\(|write_bytes\s*\(|read_text\s*\(|read_bytes\s*\()"
)
_PROMPT_OVERRIDE = (
    r"(?i)\b(?:ignore|override|disregard)\b.{0,45}\b(?:previous|system|developer|higher[- ]priority)\b.{0,35}\binstruction"
)
_EXFIL_HINT = (
    r"(?i)\b(?:send|upload|post|transmit|exfiltrat)\b.{0,45}\b(?:secret|credential|token|password|private key|environment variable)"
)
_DESTRUCTIVE_SCOPE = re.compile(
    r"(?i)(?:^|[._:/-])(?:delete|destroy|remove|purge|terminate|revoke|wipe)(?:$|[._:/-])"
)


@dataclass(frozen=True)
class SecurityFinding:
    severity: str
    code: str
    path: str | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _manifest_strings(value: Any, prefix: str = "") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_manifest_strings(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(_manifest_strings(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        rows.append((prefix, value))
    return rows


def scan_bundle_security(files: dict[str, str], manifest: dict[str, Any]) -> dict[str, Any]:
    findings: list[SecurityFinding] = []
    external_hosts: set[str] = set()
    oauth_scopes: set[str] = set()
    required_secrets: set[str] = set()

    for key_path, value in _manifest_strings(manifest):
        lower_key = key_path.lower()
        if "scope" in lower_key and value.strip():
            oauth_scopes.add(value.strip())
            if _DESTRUCTIVE_SCOPE.search(value):
                findings.append(SecurityFinding("high", "destructive_scope", key_path, "Manifest requests a destructive permission scope."))
        if any(token in lower_key for token in ("secret", "token", "api_key", "apikey", "password")) and value.strip():
            required_secrets.add(key_path)
        for host in re.findall(r"https?://([A-Za-z0-9._-]+)", value):
            external_hosts.add(host.lower())

    for path, raw in files.items():
        content = str(raw or "")
        lower = path.lower()
        if lower.endswith(SCRIPT_SUFFIXES):
            for pattern, code in _HIGH_RISK_CODE:
                if re.search(pattern, content, flags=re.I):
                    findings.append(SecurityFinding("high", code, path, "Executable source contains a high-risk runtime primitive."))
            has_secret = bool(re.search(_SECRET_ACCESS, content, flags=re.I))
            has_network = bool(re.search(_NETWORK_ACCESS, content, flags=re.I))
            if has_secret:
                findings.append(SecurityFinding("moderate", "secret_access", path, "Executable source appears to access credentials or environment secrets."))
            if has_network:
                findings.append(SecurityFinding("moderate", "network_access", path, "Executable source performs outbound network access."))
            if re.search(_FILE_ACCESS, content, flags=re.I):
                findings.append(SecurityFinding("moderate", "filesystem_access", path, "Executable source accesses the local filesystem."))
            if has_secret and has_network:
                findings.append(SecurityFinding("critical", "secret_network_combination", path, "Executable source combines credential access with outbound network access."))
        if lower.endswith(PROMPT_SUFFIXES):
            if re.search(_PROMPT_OVERRIDE, content):
                findings.append(SecurityFinding("high", "prompt_instruction_override", path, "Instruction text attempts to override higher-priority instructions."))
            if re.search(_EXFIL_HINT, content):
                findings.append(SecurityFinding("critical", "prompt_exfiltration_request", path, "Instruction text appears to request credential or secret exfiltration."))

    severity_rank = {"info": 0, "low": 1, "moderate": 2, "high": 3, "critical": 4}
    highest = max((severity_rank.get(f.severity, 0) for f in findings), default=0)
    risk = ("low", "low", "moderate", "high", "blocked")[highest]
    blocked = highest >= 4

    return {
        "risk": risk,
        "blocked": blocked,
        "findings": [finding.as_dict() for finding in findings],
        "externalHosts": sorted(external_hosts),
        "oauthScopes": sorted(oauth_scopes),
        "requiredSecrets": sorted(required_secrets),
        "scriptsScanned": sum(1 for path in files if path.lower().endswith(SCRIPT_SUFFIXES)),
        "promptFilesScanned": sum(1 for path in files if path.lower().endswith(PROMPT_SUFFIXES)),
        "executionPerformed": False,
        "limitations": "Static heuristic scan; absence of findings is not proof of safety.",
    }
