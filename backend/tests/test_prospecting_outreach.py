import pytest
from app.plays.prospecting_outreach import OutreachDraft,prepare_outreach_draft
from app.plays.prospecting_policy import ProspectDecision

def sample():
    return OutreachDraft("ceo@example.ca","A relevant conversation","Business message",
      "Example Company","123 Main Street","hello@example.com",
      "https://example.com/unsubscribe","evidence-1")

def test_no_draft_for_unreviewed_contact():
    with pytest.raises(PermissionError):
        prepare_outreach_draft(sample(),decision=ProspectDecision.REVIEW,suppressed=False,source_prohibition=False)

def test_casl_sender_fields_required_and_draft_never_sends():
    result=prepare_outreach_draft(sample(),decision=ProspectDecision.CRM_READY,
                                  suppressed=False,source_prohibition=False)
    assert result["pending_action_required"] is True
    assert result["sent"] is False
