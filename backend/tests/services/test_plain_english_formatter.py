from app.services.plain_english_formatter import format_plain_english

SAMPLE_JSON = """
{
  "summary": "The organization currently has 2 active agents but cannot auto-create a new one yet.",
  "decision": {"action": "no_agent_created", "reason": "No creation template was found."},
  "recommended_actions": [
    "Confirm the agent name and role.",
    "Authenticate required integrations."
  ],
  "confidence": 90
}
"""


def test_format_plain_english_parses_json_blob():
    text = format_plain_english(SAMPLE_JSON)
    assert "2 active agents" in text
    assert "no agent created" in text.lower() or "No creation template" in text
    assert "Confirm the agent name" in text
    assert "{" not in text


def test_format_plain_english_strips_code_fence():
    fenced = f"```json\n{SAMPLE_JSON}\n```"
    text = format_plain_english(fenced)
    assert "{" not in text


def test_format_plain_english_extracts_truncated_json_summary():
    truncated = '{"summary": "The organization currently has 2 active agents", "decision": {"action": "review'
    text = format_plain_english(truncated)
    assert "2 active agents" in text
    assert "{" not in text


def test_format_plain_english_tool_envelope_lists():
    payload = {
        "success": True,
        "tool": "apollo_lists_list",
        "action": "apollo.lists.list",
        "result": [
            {"_id": "1", "name": "MSP Prospects"},
            {"_id": "2", "name": "Gravitre Smoke List"},
        ],
    }
    text = format_plain_english(payload)
    assert "MSP Prospects" in text
    assert "Gravitre Smoke List" in text
    assert "{" not in text


def test_format_plain_english_truncated_tool_json_uses_names():
    truncated = (
        '{"success": true, "tool": "apollo_lists_list", "action": "apollo.lists.list", '
        '"result": [{"_id": "abc", "name": "Gravitre Smoke MSP e020afe818e34c", "modality": "contacts"'
    )
    text = format_plain_english(truncated)
    assert "Gravitre Smoke MSP" in text
    assert "{" not in text
