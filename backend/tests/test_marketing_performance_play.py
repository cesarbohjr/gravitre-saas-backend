from app.plays.marketing_performance import project_marketing_signal


def test_marketing_signal_does_not_claim_pipeline_or_revenue_attribution():
    row = {
        "id": "m-1",
        "suggestion_type": "post_publish_marketing_underperformance",
        "target_entity_type": "campaign",
        "target_entity_id": "c-1",
        "evidence": {
            "source": "post_publish_marketing_metrics",
            "metric_name": "conversions",
            "avg_delta_ratio": -0.25,
            "sample_size": 4,
        },
        "suggested_action": "Review creative and targeting.",
    }
    projected = project_marketing_signal(row)
    assert projected["businessResult"]["verified"] is False
    assert projected["businessResult"]["pipelineInfluenced"] is None
    assert projected["businessResult"]["revenueInfluenced"] is None
    assert projected["actionTaken"] is False
