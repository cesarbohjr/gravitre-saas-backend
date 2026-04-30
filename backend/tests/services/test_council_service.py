from app.services.council_service import AgentCouncilService, DecisionMethod


def test_resolve_vote_weighted():
    service = AgentCouncilService.__new__(AgentCouncilService)
    opinions = [
        {"position": "approve", "confidence": 0.9, "vote_weight": 1.0},
        {"position": "reject", "confidence": 0.4, "vote_weight": 1.0},
        {"position": "approve", "confidence": 0.7, "vote_weight": 1.0},
    ]
    winner, confidence = service._resolve_vote(opinions, DecisionMethod.WEIGHTED_VOTE, [])  # noqa: SLF001
    assert winner == "approve"
    assert confidence > 0.5
