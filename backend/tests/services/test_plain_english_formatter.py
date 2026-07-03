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
