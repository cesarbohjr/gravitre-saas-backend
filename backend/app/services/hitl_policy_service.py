"""Org human-in-the-loop policies — who needs approval for which action classes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.constants import SAFE_DEFAULT_APPROVER_ROLES

logger = get_logger(__name__)

ACTION_KINDS = frozenset({"read", "write", "delete"})
SCOPE_TYPES = frozenset({"org", "department", "user"})
DELETE_HINTS = re.compile(
    r"\b(delete|remove|archive|destroy|drop|purge|revoke)\b",
    re.I,
)


@dataclass(frozen=True)
class HitlDecision:
    requires_approval: bool
    matched_policy_id: str | None
    matched_policy_name: str | None
    action_kind: str
    required_approvals: int
    approver_roles: list[str]
    approver_user_ids: list[str]
    reason: str

    def can_approve(self, *, role: str | None, user_id: str | None) -> bool:
        if not self.requires_approval:
            return True
        uid = (user_id or "").strip()
        if uid and uid in set(self.approver_user_ids or []):
            return True
        role_l = (role or "").strip().lower()
        return bool(role_l and role_l in {(r or "").lower() for r in (self.approver_roles or [])})


def classify_action_kind(
    *,
    kind: str | None = None,
    destructive: bool = False,
    invoke_action: str | None = None,
    tool_name: str | None = None,
    label: str | None = None,
) -> str:
    """Map catalog/plan metadata to read | write | delete."""
    blob = " ".join(
        str(part or "") for part in (invoke_action, tool_name, label, kind)
    )
    if destructive or DELETE_HINTS.search(blob):
        return "delete"
    kind_l = (kind or "").strip().lower()
    if kind_l == "read":
        return "read"
    if kind_l in {"write", "advanced"}:
        return "write"
    # Default unknown connector actions to write (safer).
    return "write" if kind_l or invoke_action or tool_name else "read"


class HitlPolicyService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def list_policies(self, client: Any, org_id: str) -> list[dict[str, Any]]:
        try:
            rows = (
                client.table("hitl_policies")
                .select("*")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .execute()
                .data
                or []
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("hitl list failed org=%s error=%s", org_id, exc)
            return []
        return [self._serialize(row) for row in rows]

    def create_policy(
        self,
        client: Any,
        *,
        org_id: str,
        created_by: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        row = self._validate_payload(payload, org_id=org_id)
        row["org_id"] = org_id
        row["created_by"] = created_by
        row["created_at"] = datetime.now(timezone.utc).isoformat()
        row["updated_at"] = row["created_at"]
        inserted = client.table("hitl_policies").insert(row).execute()
        data = (inserted.data or [row])[0]
        return self._serialize(data)

    def update_policy(
        self,
        client: Any,
        *,
        org_id: str,
        policy_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        row = self._validate_payload(payload, org_id=org_id, partial=True)
        row["updated_at"] = datetime.now(timezone.utc).isoformat()
        updated = (
            client.table("hitl_policies")
            .update(row)
            .eq("id", policy_id)
            .eq("org_id", org_id)
            .execute()
        )
        data = (updated.data or [None])[0]
        if not data:
            raise LookupError("HITL policy not found")
        return self._serialize(data)

    def delete_policy(self, client: Any, *, org_id: str, policy_id: str) -> None:
        client.table("hitl_policies").delete().eq("id", policy_id).eq("org_id", org_id).execute()

    def resolve(
        self,
        client: Any,
        *,
        org_id: str,
        user_id: str,
        action_kind: str,
        department_ids: list[str] | None = None,
    ) -> HitlDecision:
        kind = (action_kind or "write").strip().lower()
        if kind not in ACTION_KINDS:
            kind = "write"

        policies = self._load_enabled(client, org_id)
        if not policies:
            # No HITL rules → keep legacy write/delete approval defaults for safety.
            if kind in {"write", "delete"}:
                return HitlDecision(
                    requires_approval=True,
                    matched_policy_id=None,
                    matched_policy_name=None,
                    action_kind=kind,
                    required_approvals=1,
                    approver_roles=list(SAFE_DEFAULT_APPROVER_ROLES),
                    approver_user_ids=[],
                    reason="Default write/delete approval (no HITL policies configured)",
                )
            return HitlDecision(
                requires_approval=False,
                matched_policy_id=None,
                matched_policy_name=None,
                action_kind=kind,
                required_approvals=0,
                approver_roles=[],
                approver_user_ids=[],
                reason="No HITL policy matches read action",
            )

        dept_ids = {str(d) for d in (department_ids or []) if d}
        if not dept_ids:
            dept_ids = set(self._user_department_ids(client, org_id, user_id))

        # Specificity: user > department > org
        candidates: list[tuple[int, dict[str, Any]]] = []
        for policy in policies:
            kinds = {(k or "").lower() for k in (policy.get("action_kinds") or [])}
            if kind not in kinds:
                continue
            scope = str(policy.get("scope_type") or "")
            if scope == "user" and str(policy.get("subject_user_id") or "") == user_id:
                candidates.append((0, policy))
            elif scope == "department" and str(policy.get("department_id") or "") in dept_ids:
                candidates.append((1, policy))
            elif scope == "org":
                candidates.append((2, policy))

        if not candidates:
            # Unmatched subjects keep the legacy write/delete safety net.
            if kind in {"write", "delete"}:
                return HitlDecision(
                    requires_approval=True,
                    matched_policy_id=None,
                    matched_policy_name=None,
                    action_kind=kind,
                    required_approvals=1,
                    approver_roles=list(SAFE_DEFAULT_APPROVER_ROLES),
                    approver_user_ids=[],
                    reason=f"Default {kind} approval (no matching HITL policy)",
                )
            return HitlDecision(
                requires_approval=False,
                matched_policy_id=None,
                matched_policy_name=None,
                action_kind=kind,
                required_approvals=0,
                approver_roles=[],
                approver_user_ids=[],
                reason=f"No HITL policy covers {kind} for this subject",
            )

        candidates.sort(key=lambda item: item[0])
        match = candidates[0][1]
        return HitlDecision(
            requires_approval=True,
            matched_policy_id=str(match.get("id") or "") or None,
            matched_policy_name=str(match.get("name") or "") or None,
            action_kind=kind,
            required_approvals=max(1, int(match.get("required_approvals") or 1)),
            approver_roles=[str(r) for r in (match.get("approver_roles") or []) if r],
            approver_user_ids=[str(u) for u in (match.get("approver_user_ids") or []) if u],
            reason=f"Matched HITL policy “{match.get('name')}” ({match.get('scope_type')})",
        )

    def _load_enabled(self, client: Any, org_id: str) -> list[dict[str, Any]]:
        try:
            return (
                client.table("hitl_policies")
                .select("*")
                .eq("org_id", org_id)
                .eq("enabled", True)
                .execute()
                .data
                or []
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("hitl load failed org=%s error=%s", org_id, exc)
            return []

    @staticmethod
    def _user_department_ids(client: Any, org_id: str, user_id: str) -> list[str]:
        try:
            rows = (
                client.table("department_members")
                .select("department_id, departments(id, org_id)")
                .eq("user_id", user_id)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            return []
        out: list[str] = []
        for row in rows:
            dept = row.get("departments") if isinstance(row.get("departments"), dict) else {}
            if str(dept.get("org_id") or "") != org_id:
                continue
            did = str(row.get("department_id") or "").strip()
            if did:
                out.append(did)
        return out

    def _validate_payload(
        self,
        payload: dict[str, Any],
        *,
        org_id: str,
        partial: bool = False,
    ) -> dict[str, Any]:
        _ = org_id
        out: dict[str, Any] = {}
        if not partial or "name" in payload:
            name = str(payload.get("name") or "").strip()
            if not name:
                raise ValueError("name is required")
            out["name"] = name[:120]
        if not partial or "enabled" in payload:
            out["enabled"] = bool(payload.get("enabled", True))
        if not partial or "scope_type" in payload:
            scope = str(payload.get("scope_type") or "").strip().lower()
            if scope not in SCOPE_TYPES:
                raise ValueError("scope_type must be org, department, or user")
            out["scope_type"] = scope
        scope = str(out.get("scope_type") or payload.get("scope_type") or "").lower()
        if not partial or "department_id" in payload or scope == "department":
            dept = payload.get("department_id")
            out["department_id"] = str(dept) if dept else None
        if not partial or "subject_user_id" in payload or scope == "user":
            subject = payload.get("subject_user_id")
            out["subject_user_id"] = str(subject) if subject else None
        if scope == "org":
            out["department_id"] = None
            out["subject_user_id"] = None
        elif scope == "department":
            if not out.get("department_id"):
                raise ValueError("department_id is required for department scope")
            out["subject_user_id"] = None
            self._assert_uuid(out["department_id"], "department_id")
        elif scope == "user":
            if not out.get("subject_user_id"):
                raise ValueError("subject_user_id is required for user scope")
            out["department_id"] = None
            self._assert_uuid(out["subject_user_id"], "subject_user_id")
        if not partial or "action_kinds" in payload:
            kinds = [
                str(k).strip().lower()
                for k in (payload.get("action_kinds") or [])
                if str(k).strip().lower() in ACTION_KINDS
            ]
            if not kinds:
                raise ValueError("action_kinds must include read, write, and/or delete")
            out["action_kinds"] = sorted(set(kinds))
        if not partial or "approver_roles" in payload:
            roles = [
                str(r).strip().lower()
                for r in (payload.get("approver_roles") or [])
                if str(r).strip()
            ]
            out["approver_roles"] = roles or list(SAFE_DEFAULT_APPROVER_ROLES)
        if not partial or "approver_user_ids" in payload:
            users = []
            for uid in payload.get("approver_user_ids") or []:
                text = str(uid).strip()
                if not text:
                    continue
                self._assert_uuid(text, "approver_user_ids")
                users.append(text)
            out["approver_user_ids"] = users
        if not partial or "required_approvals" in payload:
            try:
                required = int(payload.get("required_approvals") or 1)
            except (TypeError, ValueError) as exc:
                raise ValueError("required_approvals must be an integer") from exc
            if required < 1:
                raise ValueError("required_approvals must be >= 1")
            out["required_approvals"] = required
        return out

    @staticmethod
    def _assert_uuid(value: str, field: str) -> None:
        try:
            UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be a UUID") from exc

    @staticmethod
    def _serialize(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": str(row.get("id") or ""),
            "org_id": str(row.get("org_id") or ""),
            "name": row.get("name"),
            "enabled": bool(row.get("enabled", True)),
            "scope_type": row.get("scope_type"),
            "department_id": str(row["department_id"]) if row.get("department_id") else None,
            "subject_user_id": str(row["subject_user_id"]) if row.get("subject_user_id") else None,
            "action_kinds": list(row.get("action_kinds") or []),
            "approver_roles": list(row.get("approver_roles") or []),
            "approver_user_ids": [str(u) for u in (row.get("approver_user_ids") or [])],
            "required_approvals": int(row.get("required_approvals") or 1),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "created_by": str(row["created_by"]) if row.get("created_by") else None,
        }


_hitl_policy_service: HitlPolicyService | None = None


def get_hitl_policy_service(settings: Settings | None = None) -> HitlPolicyService:
    global _hitl_policy_service
    if _hitl_policy_service is None or settings is not None:
        _hitl_policy_service = HitlPolicyService(settings)
    return _hitl_policy_service
