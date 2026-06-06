"""Automated partner package security scan and permission scope review (STA-97)."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from app.connectors.sdk.manifest import ConnectorManifest

FindingSeverity = Literal["critical", "warning", "info"]
CertificationStatus = Literal["pending", "passed", "failed"]

ALLOWED_SOURCE_EXTENSIONS = frozenset({".py", ".md", ".txt", ".json"})
MAX_SOURCE_FILE_BYTES = 256 * 1024
MAX_SOURCE_FILES = 20

SECRET_PATTERNS: list[tuple[str, FindingSeverity, str]] = [
    (r"sk_(test|live)_[A-Za-z0-9]{10,}", "critical", "Possible Stripe secret key"),
    (r"whsec_[A-Za-z0-9]{10,}", "critical", "Possible webhook signing secret"),
    (r"(?i)(api[_-]?key|secret|password|token)\s*=\s*['\"][^'\"]{8,}['\"]", "critical", "Hardcoded credential assignment"),
    (r"(?i)Bearer\s+[A-Za-z0-9._\-]{20,}", "warning", "Possible hardcoded bearer token"),
]

DANGEROUS_PATTERNS: list[tuple[str, FindingSeverity, str]] = [
    (r"\beval\s*\(", "critical", "Use of eval() is not allowed in partner packages"),
    (r"\bexec\s*\(", "critical", "Use of exec() is not allowed in partner packages"),
    (r"__import__\s*\(", "critical", "Dynamic imports are not allowed"),
    (r"os\.system\s*\(", "critical", "os.system() is not allowed"),
    (r"subprocess\.(call|run|Popen|check_output)\s*\(", "warning", "Subprocess usage requires manual review"),
    (r"pickle\.loads?\s*\(", "warning", "pickle deserialization is risky in connector handlers"),
]

BROAD_OAUTH_SCOPE_TOKENS = frozenset(
    {"admin", "full", "full_access", "write", "delete", "manage", "all", "root", "superuser"}
)


@dataclass
class ReviewFinding:
    code: str
    severity: FindingSeverity
    message: str
    file: str | None = None
    line: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SecurityScanResult:
    findings: list[ReviewFinding] = field(default_factory=list)
    files_scanned: int = 0
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "filesScanned": self.files_scanned,
            "passed": self.passed,
            "criticalCount": sum(1 for f in self.findings if f.severity == "critical"),
            "warningCount": sum(1 for f in self.findings if f.severity == "warning"),
        }


@dataclass
class ScopeReviewEntry:
    action_key: str
    declared_scopes: list[str]
    recommended_scopes: list[str]
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "actionKey": self.action_key,
            "declaredScopes": self.declared_scopes,
            "recommendedScopes": self.recommended_scopes,
            "issues": self.issues,
        }


@dataclass
class ScopeReviewResult:
    entries: list[ScopeReviewEntry] = field(default_factory=list)
    oauth_scopes: list[str] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "oauthScopes": self.oauth_scopes,
            "passed": self.passed,
            "issueCount": sum(len(e.issues) for e in self.entries),
        }


@dataclass
class CertificationReviewResult:
    certification_status: CertificationStatus
    security_scan: SecurityScanResult
    scope_review: ScopeReviewResult
    badge_eligible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificationStatus": self.certification_status,
            "badgeEligible": self.badge_eligible,
            "securityScan": self.security_scan.to_dict(),
            "scopeReview": self.scope_review.to_dict(),
        }


def _normalize_sources(sources: dict[str, str] | None) -> dict[str, str]:
    if not sources:
        return {}
    normalized: dict[str, str] = {}
    for raw_name, content in sources.items():
        name = (raw_name or "").strip().replace("\\", "/").lstrip("/")
        if not name or ".." in name.split("/"):
            continue
        if len(normalized) >= MAX_SOURCE_FILES:
            break
        ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in ALLOWED_SOURCE_EXTENSIONS:
            continue
        text = content if isinstance(content, str) else str(content)
        if len(text.encode("utf-8")) > MAX_SOURCE_FILE_BYTES:
            text = text[:MAX_SOURCE_FILE_BYTES]
        normalized[name] = text
    return normalized


def _scan_line_patterns(
    *,
    filename: str,
    line_no: int,
    line: str,
    patterns: list[tuple[str, FindingSeverity, str]],
    code_prefix: str,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for pattern, severity, message in patterns:
        if re.search(pattern, line):
            findings.append(
                ReviewFinding(
                    code=f"{code_prefix}_{severity}",
                    severity=severity,
                    message=message,
                    file=filename,
                    line=line_no,
                )
            )
    return findings


def scan_package_sources(sources: dict[str, str] | None) -> SecurityScanResult:
    """Run static analysis on submitted package source files."""
    normalized = _normalize_sources(sources)
    findings: list[ReviewFinding] = []
    if not normalized:
        findings.append(
            ReviewFinding(
                code="no_sources_provided",
                severity="warning",
                message="No package source files submitted — static analysis limited to manifest scope review.",
            )
        )
        return SecurityScanResult(findings=findings, files_scanned=0, passed=True)

    for filename, content in normalized.items():
        for line_no, line in enumerate(content.splitlines(), start=1):
            findings.extend(
                _scan_line_patterns(
                    filename=filename,
                    line_no=line_no,
                    line=line,
                    patterns=SECRET_PATTERNS,
                    code_prefix="secret",
                )
            )
            if filename.endswith(".py"):
                findings.extend(
                    _scan_line_patterns(
                        filename=filename,
                        line_no=line_no,
                        line=line,
                        patterns=DANGEROUS_PATTERNS,
                        code_prefix="dangerous",
                    )
                )

    critical = any(f.severity == "critical" for f in findings)
    return SecurityScanResult(
        findings=findings,
        files_scanned=len(normalized),
        passed=not critical,
    )


def _is_broad_scope(scope: str) -> bool:
    lowered = scope.lower()
    if lowered.endswith(":*") or lowered == "*":
        return True
    parts = re.split(r"[:._\-/]", lowered)
    return any(part in BROAD_OAUTH_SCOPE_TOKENS for part in parts)


def _recommended_scopes(manifest: ConnectorManifest, action_key: str, destructive: bool) -> list[str]:
    prefix = f"{manifest.vendor}."
    action_id = action_key[len(prefix) :] if action_key.startswith(prefix) else action_key
    if destructive:
        return [f"{manifest.vendor}:{action_id}:write", action_key]
    return [f"{manifest.vendor}:{action_id}:read", action_key]


def review_permission_scopes(manifest: ConnectorManifest) -> ScopeReviewResult:
    """Review declared action/trigger scopes against least-privilege guidance."""
    oauth_scopes: list[str] = []
    if manifest.auth.type == "oauth2":
        oauth_scopes = list(manifest.auth.scopes)

    entries: list[ScopeReviewEntry] = []
    passed = True

    for action in manifest.actions:
        action_key = f"{manifest.vendor}.{action.id}"
        declared = list(action.scopes) if action.scopes else manifest.scopes_for_action(action_key)
        recommended = _recommended_scopes(manifest, action_key, action.destructive)
        issues: list[str] = []

        if not action.scopes:
            issues.append("No explicit scopes declared — defaults to vendor wildcard at runtime.")
        if any(scope.endswith(":*") for scope in declared):
            issues.append("Wildcard vendor scope declared; prefer action-specific scopes.")
        if action.destructive and any(scope.endswith(":*") for scope in declared):
            issues.append("Destructive action should not use vendor wildcard scope.")
            passed = False
        if len(declared) > 4:
            issues.append("Many scopes declared for a single action; verify least privilege.")

        entries.append(
            ScopeReviewEntry(
                action_key=action_key,
                declared_scopes=declared,
                recommended_scopes=recommended,
                issues=issues,
            )
        )

    for trigger in manifest.triggers:
        trigger_key = f"{manifest.vendor}.{trigger.id}"
        declared = list(trigger.scopes) if trigger.scopes else [f"{manifest.vendor}:*", trigger_key]
        recommended = [f"{manifest.vendor}:webhooks:read", trigger_key]
        issues: list[str] = []
        if any(scope.endswith(":*") for scope in declared):
            issues.append("Trigger uses wildcard scope; prefer webhook-specific scope.")
        entries.append(
            ScopeReviewEntry(
                action_key=trigger_key,
                declared_scopes=declared,
                recommended_scopes=recommended,
                issues=issues,
            )
        )

    for scope in oauth_scopes:
        if _is_broad_scope(scope):
            passed = False
            entries.append(
                ScopeReviewEntry(
                    action_key="oauth",
                    declared_scopes=oauth_scopes,
                    recommended_scopes=[f"{manifest.vendor}:read"],
                    issues=[f"OAuth scope {scope!r} is overly broad for marketplace certification."],
                )
            )
            break

    if manifest.auth.type == "oauth2" and not oauth_scopes:
        entries.append(
            ScopeReviewEntry(
                action_key="oauth",
                declared_scopes=[],
                recommended_scopes=[f"{manifest.vendor}:read"],
                issues=["OAuth connector declares no scopes — document required provider permissions."],
            )
        )

    return ScopeReviewResult(entries=entries, oauth_scopes=oauth_scopes, passed=passed)


def run_certification_review(
    manifest: ConnectorManifest,
    *,
    package_sources: dict[str, str] | None = None,
) -> CertificationReviewResult:
    """Run automated security scan + scope review for a partner submission."""
    security_scan = scan_package_sources(package_sources)
    scope_review = review_permission_scopes(manifest)

    if not security_scan.passed or not scope_review.passed:
        status: CertificationStatus = "failed"
    elif security_scan.files_scanned == 0:
        status = "pending"
    else:
        status = "passed"

    badge_eligible = status == "passed"
    return CertificationReviewResult(
        certification_status=status,
        security_scan=security_scan,
        scope_review=scope_review,
        badge_eligible=badge_eligible,
    )


def build_registry_scan_summary(certification: CertificationReviewResult) -> dict[str, Any]:
    """Compact scan summary stored on published registry rows."""
    return {
        "certificationStatus": certification.certification_status,
        "filesScanned": certification.security_scan.files_scanned,
        "criticalCount": sum(1 for f in certification.security_scan.findings if f.severity == "critical"),
        "warningCount": sum(1 for f in certification.security_scan.findings if f.severity == "warning"),
        "scopeIssueCount": sum(len(e.issues) for e in certification.scope_review.entries),
    }
