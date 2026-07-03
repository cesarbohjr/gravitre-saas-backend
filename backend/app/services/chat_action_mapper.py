"""Natural-language mapping from chat prompts to connector execution matrix actions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.chat_connector_models import INTEGRATION_ALIASES, ConnectorActionPlan
from app.services.connector_execution_matrix import (
    ConnectorActionMatrixEntry,
    chat_executable_entries,
    get_matrix_entry,
    skip_reason_for_entry,
)
from app.services.chat_tool_bridge import build_dynamic_chat_tool_specs

READ_VERBS = re.compile(r"\b(search|find|list|get|lookup|query|show|fetch|read|summarize|pull)\b", re.I)
WRITE_VERBS = re.compile(
    r"\b(create|update|post|send|write|close|log|notify|message|assign|enroll|add|share|upload|delete|remove)\b",
    re.I,
)
QUOTED = re.compile(r'["\']([^"\']{1,500})["\']')
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
SLACK_CHANNEL = re.compile(r"(#[\w-]+|<#[^>]+>|@\w+)")
TICKET_ID = re.compile(r"\b(?:ticket\s*#?\s*|#)(\d{3,})\b", re.I)
SEARCH_FOR = re.compile(
    r"(?:search|find|lookup|list|query|show|pull)\s+(?:for\s+)?(.+?)(?:\s+in\s+\w+|\s*$)",
    re.I,
)
OBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "contacts": ("contact", "contacts", "person", "people", "prospect"),
    "deals": ("deal", "deals", "pipeline", "opportunity", "opportunities", "stale deal", "stale deals"),
    "tickets": ("ticket", "tickets", "case", "cases"),
    "issues": ("issue", "issues", "bug", "bugs", "story"),
    "items": ("item", "items", "task", "tasks", "follow-up", "follow up", "follow-up task"),
    "messages": ("message", "messages", "notify", "notification", "alert", "summary"),
    "files": ("file", "files", "folder", "folders", "document", "documents"),
    "events": ("event", "events", "meeting", "meetings", "appointment"),
    "boards": ("board", "boards"),
}


@dataclass(frozen=True)
class ActionMatch:
    entry: ConnectorActionMatrixEntry
    tool_name: str
    score: float
    args: dict[str, Any]


class ChatActionMapper:
    """Scores matrix entries against natural language and extracts invoke_tool params."""

    def match_segment(
        self,
        message: str,
        *,
        connected_integrations: list[str],
    ) -> ActionMatch | None:
        text = message.strip()
        if not text:
            return None
        entries = chat_executable_entries(connected_integrations=connected_integrations)
        if not entries:
            return None
        best: ActionMatch | None = None
        for entry in entries:
            tool_name = entry.tool_registry_key
            if tool_name not in build_dynamic_chat_tool_specs():
                continue
            score = self._score(text, entry)
            if score <= 0:
                continue
            args = self._extract_args(text, entry)
            if args is None:
                continue
            candidate = ActionMatch(entry=entry, tool_name=tool_name, score=score, args=args)
            if best is None or candidate.score > best.score or (
                candidate.score == best.score
                and self._prefer_entry(candidate.entry, best.entry, text)
            ):
                best = candidate
        return best

    @staticmethod
    def _prefer_entry(
        candidate: ConnectorActionMatrixEntry,
        incumbent: ConnectorActionMatrixEntry,
        text: str,
    ) -> bool:
        lowered = text.lower()
        if ".search" in candidate.action_key and ".get" in incumbent.action_key and "search" in lowered:
            return True
        if ".list" in candidate.action_key and ".get" in incumbent.action_key and READ_VERBS.search(text):
            return True
        if "post_message" in candidate.registry_key and "post_message" in incumbent.registry_key:
            return False
        return False

    def plan_from_match(
        self,
        match: ActionMatch,
        *,
        requires_approval: bool,
        approval_reason: str | None,
    ) -> ConnectorActionPlan:
        entry = match.entry
        return ConnectorActionPlan(
            tool_name=match.tool_name,
            invoke_action=entry.registry_key,
            integration=entry.connector_id,
            kind=entry.kind,
            label=entry.display_name,
            args=match.args,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            destructive=entry.destructive,
        )

    def skip_reason(
        self,
        message: str,
        *,
        connected_integrations: list[str],
    ) -> str | None:
        mentioned = self._mentioned_integrations(message, connected_integrations)
        if not mentioned:
            return None
        connected = {c.lower() for c in connected_integrations}
        for vendor in mentioned:
            if vendor not in connected:
                label = vendor.replace("_", " ").title()
                return f"Connect {label} in Gravitre to run this action."
        match = self.match_segment(message, connected_integrations=connected_integrations)
        if match:
            return None
        vendor = mentioned[0]
        return skip_reason_for_entry(get_matrix_entry(vendor, ""), connected=True)

    def _score(self, message: str, entry: ConnectorActionMatrixEntry) -> float:
        text = message.lower()
        aliases = INTEGRATION_ALIASES.get(entry.connector_id, (entry.connector_id.replace("_", " "),))
        if not any(alias in text for alias in aliases):
            return 0.0
        score = 12.0
        suffix = entry.action_key.split(".", 1)[-1]
        resource = suffix.split(".")[0] if "." in suffix else suffix.split("_")[0]
        for obj_key, obj_aliases in OBJECT_ALIASES.items():
            if obj_key in suffix or resource in obj_key:
                if any(alias in text for alias in obj_aliases):
                    score += 8.0
        for phrase in entry.chat_phrases[:6]:
            if phrase in text:
                score += 6.0
        if ".search" in entry.action_key and READ_VERBS.search(text):
            score += 18.0
        if ".list" in entry.action_key and READ_VERBS.search(text):
            score += 10.0
        if ".get" in entry.action_key and "search" in text and not re.search(
            r"\b(?:get|fetch)\b|\b(?:id|#)\s*\w+",
            text,
            re.I,
        ):
            score -= 16.0
        if entry.kind == "read" and READ_VERBS.search(text):
            score += 6.0
        if entry.kind != "read" and WRITE_VERBS.search(text):
            score += 10.0
        if entry.kind == "read" and WRITE_VERBS.search(text) and not READ_VERBS.search(text):
            score -= 4.0
        if entry.kind != "read" and READ_VERBS.search(text) and not WRITE_VERBS.search(text):
            score -= 4.0
        if "stale" in text and "deal" in suffix:
            score += 6.0
        if "notify" in text and "message" in suffix:
            score += 8.0
        if "task" in text and "item" in suffix:
            score += 8.0
        return score

    def _extract_args(self, message: str, entry: ConnectorActionMatrixEntry) -> dict[str, Any] | None:
        text = message.strip()
        suffix = entry.action_key.split(".", 1)[-1]
        quoted = [m.group(1).strip() for m in QUOTED.finditer(text)]
        args: dict[str, Any] = {}

        if entry.kind == "read":
            query = self._search_query(text) or (quoted[0] if quoted else None)
            if query:
                args["query"] = query[:200]
            if "limit" not in args:
                args["limit"] = 10
            if suffix.endswith(".search") or "search" in suffix or "list" in suffix:
                if not args.get("query") and len(text.split()) <= 12:
                    args["query"] = text[:200]
                return args if args.get("query") or "list" in suffix else None
            if "get" in suffix:
                ticket = TICKET_ID.search(text)
                if ticket:
                    args["ticket_id"] = ticket.group(1)
                    return args
                for key in ("file_id", "item_id", "deal_id", "issue_id", "record_id"):
                    match = re.search(rf"\b{key.replace('_', ' ')}\s*#?\s*(\w+)\b", text, re.I)
                    if match:
                        args[key] = match.group(1)
                        return args
                return args if args else {"query": text[:120]}

        if "slack" in entry.connector_id and "post_message" in entry.registry_key:
            channel = SLACK_CHANNEL.search(text)
            message_text = quoted[-1] if quoted else None
            if not message_text:
                post_match = re.search(
                    r"(?:post|send|notify|message)\s+(?:to\s+)?(?:#[\w-]+|<#[^>]+>|@\w+|\w[\w-]*)\s*[:\-]?\s*(.+)$",
                    text,
                    re.I,
                )
                if post_match:
                    message_text = post_match.group(1).strip()
            if channel and message_text:
                return {"channel": channel.group(0).lstrip("#").replace("<", "").replace(">", ""), "message": message_text}
            return None

        if entry.connector_id == "monday" and "items.create" in entry.action_key:
            board_match = re.search(r"\bboard\s+(\w[\w-]*)", text, re.I)
            name = quoted[0] if quoted else None
            if not name:
                create_match = re.search(r"\b(?:create|add)\s+(?:a\s+)?(?:task|item)\s+(?:called\s+)?(.+)$", text, re.I)
                if create_match:
                    name = create_match.group(1).strip().strip('"\'')
            if name:
                payload: dict[str, Any] = {"item_name": name[:200]}
                if board_match:
                    payload["board_id"] = board_match.group(1)
                return payload
            return None

        if entry.connector_id == "gmail" and "messages.send" in entry.registry_key:
            email = EMAIL.search(text)
            subject = quoted[0] if quoted else "Follow-up"
            body = quoted[1] if len(quoted) > 1 else (quoted[0] if quoted else text[:500])
            if email:
                return {"to": email.group(0), "subject": subject, "body": body}
            return None

        if "jira" in entry.connector_id and "issues.create" in entry.action_key:
            summary = quoted[0] if quoted else None
            project_match = re.search(r"\bproject\s+([\w-]+)\b", text, re.I)
            if summary and project_match:
                return {"project_key": project_match.group(1), "summary": summary}
            if summary:
                return {"summary": summary, "project_key": "ENG"}
            return None

        if "hubspot" in entry.connector_id and "contacts.create" in entry.action_key:
            email = EMAIL.search(text)
            if email:
                args["email"] = email.group(0)
            if quoted:
                args["firstname"] = quoted[0]
            return args if args else None

        if quoted:
            if "body" in suffix or "comment" in suffix or "note" in suffix or "update" in suffix:
                return {"body": quoted[0]}
            if "message" in suffix or "send" in suffix:
                return {"message": quoted[0], "text": quoted[0]}

        if WRITE_VERBS.search(text):
            return {"payload": {"intent_text": text[:500]}}
        return None

    @staticmethod
    def _search_query(message: str) -> str | None:
        match = SEARCH_FOR.search(message.strip())
        if match:
            return match.group(1).strip(" .\"'")
        return None

    @staticmethod
    def _mentioned_integrations(message: str, connected_integrations: list[str]) -> list[str]:
        lowered = message.lower()
        found: list[str] = []
        all_vendors = set(INTEGRATION_ALIASES.keys()) | set(connected_integrations)
        for integration in all_vendors:
            aliases = INTEGRATION_ALIASES.get(integration, (integration.replace("_", " "),))
            if any(alias in lowered for alias in aliases):
                found.append(integration)
        return found


_mapper: ChatActionMapper | None = None


def get_chat_action_mapper() -> ChatActionMapper:
    global _mapper
    if _mapper is None:
        _mapper = ChatActionMapper()
    return _mapper
