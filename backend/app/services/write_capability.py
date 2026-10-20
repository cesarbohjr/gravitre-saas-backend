"""What a write does to the outside world, independent of which vendor does it.

Approval rules used to key on vendor action ids: gmail.messages.send and
slack.post_message always needed approval, but outlook.messages.send,
microsoft365.mail.send, sendgrid.mail.send, microsoft_teams.messages.send and
webhook.post did not, so an agent could send the same email through another
connector without the approval Gmail required. The capability is what governs.
"""
from __future__ import annotations

import re

EXTERNAL_SEND = "external_send"

# Known sends across connectors (catalog keys and registry spellings).
_EXTERNAL_SEND_ACTIONS: frozenset[str] = frozenset(
    {
        "email.send",
        "gmail.messages.send",
        "gmail.drafts.send",
        "outlook.messages.send",
        "outlook.mail.send",
        "microsoft365.mail.send",
        "microsoft365.batch.mail",
        "microsoft365.messages.send",
        "sendgrid.mail.send",
        "mailchimp.campaigns.send",
        "slack.post_message",
        "slack.chat.post_message",
        "microsoft_teams.messages.send",
        "teams.messages.send",
        "twilio.messages.send",
        "webhook.post",
    }
)

# Verbs that send something to a person or system outside Gravitre. Matched on
# the last segment of an action key or an MCP tool name.
_SEND_NAME = re.compile(
    r"(^|[._-])(send|send_email|send_mail|send_message|send_sms|post_message|"
    r"reply|reply_all|forward|post_webhook|webhook_post|publish_post|tweet)([._-]|$)",
    re.IGNORECASE,
)


def capability_of_action(action_key: str | None) -> str | None:
    """EXTERNAL_SEND for any action that sends outside Gravitre, else None."""
    key = str(action_key or "").strip().lower()
    if not key:
        return None
    if key in _EXTERNAL_SEND_ACTIONS:
        return EXTERNAL_SEND
    tail = key.split(".", 1)[1] if "." in key else key
    if _SEND_NAME.search(tail):
        return EXTERNAL_SEND
    return None


def capability_of_mcp_tool(tool_name: str | None) -> str | None:
    """Same classification for an MCP tool name (e.g. "send_email", "slack_post_message")."""
    name = str(tool_name or "").strip().lower()
    if not name:
        return None
    if _SEND_NAME.search(name):
        return EXTERNAL_SEND
    return None
