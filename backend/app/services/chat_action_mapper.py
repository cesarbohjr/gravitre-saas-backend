"""Natural-language mapping from chat prompts to connector execution matrix actions."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.services.chat_connector_models import INTEGRATION_ALIASES, ConnectorActionPlan, LIST_CREATE_INTENT
from app.services.chat_tool_visibility import chat_visible_connector_tool_names
from app.services.connector_action_workflows import extract_asana_assignee_only
from app.services.connector_execution_matrix import (
    ConnectorActionMatrixEntry,
    chat_executable_entries,
    get_matrix_entry,
    skip_reason_for_entry,
)

READ_VERBS = re.compile(r"\b(search|find|list|get|lookup|query|show|fetch|read|summarize|pull)\b", re.I)
WRITE_VERBS = re.compile(
    r"\b(create|update|post|send|write|close|log|notify|message|assign|enroll|add|share|upload|delete|remove|draft|compose)\b",
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
FROM_ENTITY = re.compile(
    r"\bfrom\s+([A-Za-z0-9][\w\s.&'-]{1,80}?)(?:\s+in\b|[?.!,]|$)",
    re.I,
)
RELATIVE_DUE = re.compile(
    r"\bby\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today)\b",
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
        allowed_tools = chat_visible_connector_tool_names(
            connected_integrations=connected_integrations,
        )
        best: ActionMatch | None = None
        # STA-305 catalog-kind authority: clear write intent + write args fail must not
        # silently crown .list/.search or payload-fallthrough lookalikes (update/stories).
        best_write_without_args: ActionMatch | None = None
        write_intent = bool(WRITE_VERBS.search(text))
        for entry in entries:
            tool_name = entry.tool_registry_key
            if tool_name not in allowed_tools:
                continue
            score = self._score(text, entry)
            if score <= 0:
                continue
            # Fix 3 — schema-constrained extraction is primary; vendor regex is fallback.
            args: dict[str, Any] | None = None
            if write_intent and entry.kind != "read":
                try:
                    from app.services.schema_param_extractor import extract_action_args_heuristic

                    schema_args = extract_action_args_heuristic(
                        entry.registry_key,
                        text,
                        existing_args={},
                    )
                    if schema_args:
                        args = schema_args
                except Exception:  # noqa: BLE001
                    pass
            vendor_args = self._extract_args(text, entry)
            if vendor_args:
                # Vendor regex/heuristics win over schema fallthrough (full-message dumps).
                args = {**(args or {}), **vendor_args}
            elif args is None:
                args = vendor_args
            if args is None:
                if write_intent and entry.kind != "read":
                    candidate_wo = ActionMatch(
                        entry=entry, tool_name=tool_name, score=score, args={}
                    )
                    if (
                        best_write_without_args is None
                        or candidate_wo.score > best_write_without_args.score
                        or (
                            candidate_wo.score == best_write_without_args.score
                            and self._prefer_write_authority(
                                candidate_wo.entry, best_write_without_args.entry
                            )
                        )
                    ):
                        best_write_without_args = candidate_wo
                continue
            candidate = ActionMatch(entry=entry, tool_name=tool_name, score=score, args=args)
            if best is None or candidate.score > best.score or (
                candidate.score == best.score
                and self._prefer_entry(candidate.entry, best.entry, text)
            ):
                best = candidate
        if write_intent and best_write_without_args is not None:
            if best is None:
                return best_write_without_args
            if best.entry.kind == "read":
                return best_write_without_args
            # Override payload-fallthrough lookalikes only when the targeted write
            # was score-competitive (avoids demoting a real deals.update to contacts.create).
            if self._is_intent_text_fallthrough(best.args):
                if best_write_without_args.score >= best.score - 8:
                    return best_write_without_args
            elif self._prefer_write_authority(best_write_without_args.entry, best.entry):
                if best_write_without_args.score >= best.score - 8:
                    return best_write_without_args
        return best

    @staticmethod
    def _is_intent_text_fallthrough(args: dict[str, Any]) -> bool:
        payload = args.get("payload")
        return (
            isinstance(payload, dict)
            and "intent_text" in payload
            and set(args.keys()) <= {"payload"}
        )

    @staticmethod
    def _prefer_write_authority(
        candidate: ConnectorActionMatrixEntry,
        incumbent: ConnectorActionMatrixEntry,
    ) -> bool:
        """Prefer create/post/send over update/stories lookalikes under write intent."""
        create_markers = (".create", "post_message", "messages.send", "drafts.create")
        cand_create = any(m in candidate.action_key or m in candidate.registry_key for m in create_markers)
        inc_create = any(m in incumbent.action_key or m in incumbent.registry_key for m in create_markers)
        if cand_create and not inc_create:
            return True
        return False

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
        from app.services.gravitree_voice import format_operator_message

        for vendor in mentioned:
            if vendor not in connected:
                return format_operator_message(
                    "connector_connect_to_run",
                    integration=vendor,
                    confidence_register="blocked",
                    allow_humor=False,
                )
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
        if entry.connector_id == "slack" and "post_message" in entry.registry_key:
            if re.search(r"\b(post|send|notify|draft|compose)\b", text) and "slack" in text:
                score += 20.0
            if "approval" in text:
                score += 6.0
        if entry.connector_id == "slack" and "conversations.create" in entry.action_key:
            if re.search(r"\b(post|send|message|summary|draft|compose)\b", text) and not re.search(
                r"\b(create|new)\s+(?:a\s+)?channel\b",
                text,
                re.I,
            ):
                score -= 18.0
        if entry.connector_id in {"google_drive", "google_sheets"} and "files.list" in entry.action_key:
            if "sheet" in text and READ_VERBS.search(text):
                score += 28.0
            if re.search(r"\blist\s+files?\b", text, re.I):
                score += 32.0
        if entry.connector_id == "google_drive" and "search_files" in entry.action_key:
            if re.search(r"\blist\s+files?\b", text, re.I):
                score -= 28.0
            if re.search(r"\b(find|search|look\s+for)\b", text, re.I):
                score += 18.0
        if entry.connector_id == "google_sheets" and "values.get" in entry.action_key:
            if "find" in text or "search" in text or "summarize" in text:
                score -= 24.0
        if entry.connector_id == "google_sheets" and "values.batch_get" in entry.action_key:
            if "find" in text or "summarize" in text:
                score -= 24.0
        if entry.connector_id == "google_sheets" and "spreadsheets.get" in entry.action_key:
            if "find" in text or "search" in text:
                score -= 14.0
        if entry.connector_id == "asana" and "tasks.create" in entry.action_key:
            if re.search(r"\bcreate\s+(?:a\s+)?task\b", text, re.I):
                score += 16.0
            if re.search(r"\bcreate\s+an\s+asana\s+task\b", text, re.I):
                score += 20.0
            if re.search(r"\bcreate\s+(?:follow[- ]?up\s+)?tasks?\b", text, re.I):
                score += 14.0
        if entry.connector_id == "apollo" and LIST_CREATE_INTENT.search(text):
            # Prefer lists.create; demote list/search/contact creates that steal the match.
            if "lists.create" in entry.action_key:
                score += 40.0
            elif "contacts.create" in entry.action_key:
                score -= 40.0
            elif "lists.list" in entry.action_key or (
                "list" in entry.action_key and "create" not in entry.action_key
            ):
                score -= 40.0
            elif "search" in entry.action_key:
                score -= 28.0
            elif "list" in entry.action_key or "lists" in entry.registry_key:
                score += 8.0
            else:
                score -= 12.0
        if entry.connector_id == "apollo" and re.search(r"\b(search|find|check)\b", text, re.I):
            if "search" in entry.action_key:
                score += 14.0
        if entry.connector_id == "asana" and "tasks.update" in entry.action_key:
            if re.search(r"\bcreate\s+(?:an?\s+)?(?:asana\s+)?tasks?\b", text, re.I) and not re.search(
                r"\btask\s*#?\s*\w+",
                text,
                re.I,
            ):
                score -= 24.0
        if "hubspot" in entry.connector_id and "contacts.create" in entry.action_key:
            if re.search(r"\bcreate\s+(?:a\s+)?(?:hubspot\s+)?contacts?\b", text, re.I):
                score += 22.0
        if "github" in entry.connector_id and "issues.create" in entry.action_key:
            if re.search(r"\bcreate\s+(?:a\s+)?(?:github\s+)?issues?\b", text, re.I):
                score += 22.0
        if "github" in entry.connector_id and (
            "issues.comment" in entry.action_key or "issues.list" in entry.action_key
        ):
            if re.search(r"\bcreate\s+(?:a\s+)?(?:github\s+)?issues?\b", text, re.I):
                score -= 24.0
        if "jira" in entry.connector_id and "issues.create" in entry.action_key:
            if re.search(r"\bcreate\s+(?:a\s+)?(?:jira\s+)?issues?\b", text, re.I):
                score += 18.0
        if "hubspot" in entry.connector_id and "contacts.update" in entry.action_key:
            if re.search(r"\bcreate\s+(?:a\s+)?(?:hubspot\s+)?contacts?\b", text, re.I):
                score -= 24.0
        if "hubspot" in entry.connector_id and "deals.update" in entry.action_key:
            if re.search(r"\bupdate\b", text, re.I) and "deal" in text:
                score += 18.0
            if "stage" in text:
                score += 10.0
        if "hubspot" in entry.connector_id and "deals.update_stage" in entry.action_key:
            if re.search(r"\bupdate\b", text, re.I) and "deal" in text and "stage" in text:
                score += 24.0
        if "hubspot" in entry.connector_id and "deals.create" in entry.action_key:
            if re.search(r"\bupdate\b", text, re.I) and "deal" in text and "create" not in text:
                score -= 20.0
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
            if entry.connector_id == "google_drive" and "files.list" in entry.action_key:
                if "sheet" in text.lower():
                    args["query"] = "mimeType='application/vnd.google-apps.spreadsheet'"
                    return args
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
                    r"(?:post|send|notify|message|draft|compose)\s+(?:a\s+|this\s+)?(.+?)(?:\s+(?:to|in)\s+slack|\s+for\s+approval|$)",
                    text,
                    re.I,
                )
                if post_match:
                    message_text = post_match.group(1).strip(" .")
                    if message_text.lower() == "summary" and "this summary" in text.lower():
                        message_text = "this summary"
            if not message_text and "summary" in text.lower():
                message_text = "Summary pending approval."
            channel_token = channel.group(0) if channel else None
            if not channel_token and re.search(r"\b(?:to|in)\s+slack\b", text, re.I):
                channel_token = "general"
            if channel_token and message_text:
                clean = channel_token.lstrip("#").replace("<", "").replace(">", "")
                if clean.startswith("#"):
                    clean = clean[1:]
                return {"channel": clean, "message": message_text, "text": message_text}
            return None

        if entry.connector_id == "asana" and "tasks.create" in entry.action_key:
            payload = self._extract_asana_task_args(text, quoted)
            if payload:
                return payload
            return None

        if "hubspot" in entry.connector_id and "deals.create" in entry.action_key:
            deal_name = quoted[0] if quoted else None
            if not deal_name:
                named = re.search(r"\bdeal\s+(?:called|named)\s+[\"']?([^\"'.]+)", text, re.I)
                if named:
                    deal_name = named.group(1).strip()
            if not deal_name:
                deal_name = "New deal from chat"
            return {"properties": {"dealname": deal_name[:200]}}

        if entry.connector_id == "monday" and "items.create" in entry.action_key:
            board_match = re.search(r"\bboard\s+(\w[\w-]*)", text, re.I)
            name = quoted[0] if quoted else None
            if not name:
                create_match = re.search(
                    r"\b(?:create|add)\s+(?:a\s+)?(?:task|item)\s+(?:called\s+)?(.+)$",
                    text,
                    re.I,
                )
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
            if not summary:
                titled = re.search(
                    r"\btitled\s+[\"']?([^\"'.]+)[\"']?",
                    text,
                    re.I,
                )
                if titled:
                    summary = titled.group(1).strip()
            project_match = re.search(r"\bproject\s+([\w-]+)\b", text, re.I)
            if summary and project_match:
                return {"project_key": project_match.group(1), "summary": summary}
            if summary:
                return {"summary": summary, "project_key": "ENG"}
            return None

        if "github" in entry.connector_id and "issues.create" in entry.action_key:
            title = quoted[0] if quoted else None
            if not title:
                titled = re.search(
                    r"\btitled\s+[\"']?([^\"'.]+)[\"']?",
                    text,
                    re.I,
                )
                if titled:
                    title = titled.group(1).strip()
            repo_match = re.search(r"\brepo(?:sitory)?\s+([\w.-]+/[\w.-]+)\b", text, re.I)
            if title:
                payload: dict[str, Any] = {"title": title[:200]}
                if repo_match:
                    payload["repo"] = repo_match.group(1)
                return payload
            # Bare create — keep write candidate without inventing a title
            return None

        if "hubspot" in entry.connector_id and "contacts.create" in entry.action_key:
            email = EMAIL.search(text)
            if email:
                args["email"] = email.group(0)
            if quoted:
                args["firstname"] = quoted[0]
            if re.search(r"\bcreate\s+(?:a\s+)?(?:hubspot\s+)?contacts?\b", text, re.I):
                if not args:
                    args["properties"] = {"firstname": "Imported contact"}
                return args
            return args if args else None

        if entry.connector_id == "apollo" and "lists.create" in entry.action_key:
            name = quoted[0] if quoted else None
            # Treat Apollo "segment" like a contact list/label — Apollo's public
            # API exposes labels, not CRM segments, so we map both NL phrasings here.
            if not name:
                for_match = re.search(
                    r"\b(?:contact\s+)?(?:list|group|segment)\b.*?\bfor\s+(.+?)(?:[?.!]|$)",
                    text,
                    re.I,
                )
                if for_match:
                    name = for_match.group(1).strip()
            if not name:
                list_match = re.search(
                    r"\b(?:list|group|segment)\s+(?:named|called)\s*[\"']?([^\"'.]+)",
                    text,
                    re.I,
                )
                if list_match:
                    name = list_match.group(1).strip()
            if not name:
                # "create a segment in Apollo for MSPs" / "create an MSP segment"
                msp_match = re.search(
                    r"\b(?:an?\s+)?(msp)\s+(?:prospect\s+)?(?:list|group|segment|contacts?)\b",
                    text,
                    re.I,
                )
                if msp_match or re.search(r"\b(?:list|group|segment)\b.*\bmsp\b", text, re.I):
                    name = "MSP Prospects"
                elif "msp" in text.lower() and LIST_CREATE_INTENT.search(text):
                    name = "MSP Prospects"
            if name:
                cleaned = name.strip().strip("\"'")
                # Normalize plural shorthand like "MSPs" → "MSP Prospects"
                if re.fullmatch(r"msps?", cleaned, re.I):
                    cleaned = "MSP Prospects"
                return {"name": cleaned[:200], "modality": "contacts"}
            return None

        if quoted:
            if "body" in suffix or "comment" in suffix or "note" in suffix or "update" in suffix:
                return {"body": quoted[0]}
            if "message" in suffix or "send" in suffix:
                return {"message": quoted[0], "text": quoted[0]}

        if WRITE_VERBS.search(text):
            return {"payload": {"intent_text": text[:500]}}
        return None

    @staticmethod
    def _parse_relative_due(text: str) -> str | None:
        from datetime import date, timedelta

        match = RELATIVE_DUE.search(text)
        if not match:
            return None
        token = match.group(1).lower()
        if token == "today":
            return date.today().isoformat()
        if token == "tomorrow":
            return (date.today() + timedelta(days=1)).isoformat()
        weekdays = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        target = weekdays.get(token)
        if target is None:
            return None
        today = date.today()
        delta = (target - today.weekday()) % 7
        if delta == 0:
            delta = 7
        return (today + timedelta(days=delta)).isoformat()

    def _extract_asana_task_args(self, text: str, quoted: list[str]) -> dict[str, Any] | None:
        assignee_only = extract_asana_assignee_only(text)
        if assignee_only:
            return assignee_only

        name = quoted[0] if quoted else None
        payload: dict[str, Any] = {}

        for_person = re.search(
            r"\bcreate\s+(?:a\s+)?task\s+(?:in\s+asana\s+)?for\s+(\w+)\s+to\s+(.+?)(?:[?.!]|$)",
            text,
            re.I,
        )
        if for_person:
            payload["assignee_hint"] = for_person.group(1).strip()
            name = for_person.group(2).strip()
            due_fragment = RELATIVE_DUE.search(for_person.group(2) or "")
            if due_fragment:
                name = RELATIVE_DUE.sub("", name).strip(" .,")
                due_on = self._parse_relative_due(for_person.group(2))
                if due_on:
                    payload["due_on"] = due_on

        if not name:
            task_match = re.search(
                r"\bcreate\s+(?:a\s+)?task\s+(?:in\s+asana\s+)?(?:for\s+)?(.+?)(?:[?.!]|$)",
                text,
                re.I,
            )
            if task_match:
                name = task_match.group(1).strip()
        if not name:
            asana_task_match = re.search(
                r"\bcreate\s+an\s+asana\s+task\s+(?:for\s+)?(.+?)(?:[?.!]|$)",
                text,
                re.I,
            )
            if asana_task_match:
                name = asana_task_match.group(1).strip()
        if not name:
            follow_up_match = re.search(
                r"\bcreate\s+(?:follow[- ]?up\s+)?tasks?\s+(?:in\s+asana\s+)?(?:for\s+)?(.+?)(?:[?.!]|$)",
                text,
                re.I,
            )
            if follow_up_match:
                name = follow_up_match.group(1).strip()
        if not name and re.search(
            r"\bcreate\s+(?:follow[- ]?up\s+)?tasks?\s+in\s+asana\b",
            text,
            re.I,
        ):
            name = "Follow-up tasks"

        if not name:
            return None

        if RELATIVE_DUE.search(name):
            due_on = self._parse_relative_due(name)
            if due_on:
                payload["due_on"] = due_on
            name = RELATIVE_DUE.sub("", name).strip(" .,")

        payload["name"] = name[:200]
        return payload

    @staticmethod
    def _search_query(message: str) -> str | None:
        from_match = FROM_ENTITY.search(message.strip())
        if from_match:
            return from_match.group(1).strip(" .\"'")
        match = SEARCH_FOR.search(message.strip())
        if not match:
            return None
        raw = match.group(1).strip(" .\"'")
        cleaned = re.sub(
            r"\b(hubspot|salesforce|slack|asana|contacts?|companies|deals?|tickets?|for)\b",
            "",
            raw,
            flags=re.I,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .\"'-")
        return cleaned[:200] if cleaned else raw[:200]

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
