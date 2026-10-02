from app.plays.catalog import PLATFORM_PLAY_TEMPLATES, get_platform_play


def test_marketplace3_signature_play_catalog_expands_beyond_original_three() -> None:
    keys = {play.key for play in PLATFORM_PLAY_TEMPLATES}
    assert {
        "client-risk-radar",
        "revenue-leak-hunter",
        "process-drift-detector",
        "knowledge-gap-miner",
        "executive-morning-command-brief",
        "autonomous-exception-manager",
    } <= keys
    assert len(PLATFORM_PLAY_TEMPLATES) >= 9


def test_marketplace3_signature_plays_have_measurable_outcomes() -> None:
    for key in {
        "client-risk-radar",
        "revenue-leak-hunter",
        "process-drift-detector",
        "knowledge-gap-miner",
        "executive-morning-command-brief",
        "autonomous-exception-manager",
    }:
        play = get_platform_play(key)
        assert play is not None
        assert play.objective.strip()
        assert play.outcome_metrics
