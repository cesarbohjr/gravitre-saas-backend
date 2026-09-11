"""Standing adversarial corpus: every shortcut-class failure this program already paid for.

Both modalities call evaluate_intent_gateway. Operator-task shaped turns must
fall through. Narrow social/FAQ phrasing may shortcut — identically for text and voice.
"""

from __future__ import annotations

import pytest

from app.services.intent_gateway import GatewayContext, evaluate_intent_gateway
from tests.services.task_execution_parity_fixtures import (
    AMBIGUOUS_CLARIFY,
    CONNECTOR_LOOKUP,
    GOOGLE_ADS_CAMPAIGN_BRIEF,
    GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE,
    MULTI_PARAM_WRITE,
    SEO_PLUS_GOOGLE_ADS,
    VENTING_PLUS_GOOGLE_ADS,
)

# Curly apostrophe — previously split "don't execute" into a campaign name.
CURLY_DONT_ADS = GOOGLE_ADS_CAMPAIGN_BRIEF.replace("don't", "don’t")

# Quoted vendor names inside a real Ads brief (Salesforce-as-copy, HubSpot-as-copy).
QUOTED_VENDORS_IN_ADS = (
    'Set it up in Google Ads. Ad groups include "AI agent for Salesforce" and '
    '"AI agent for HubSpot". Don\'t execute without my approval first.'
)

ENTERPRISE_WHERE_IN_ADS = (
    "Show me where I can verify the enterprise AI agent campaign in Google Ads."
)

SETTINGS_NAV_FAQ = (
    "In the Gravitre sidebar, which primary nav item holds Enterprise, Federation, and Environments?"
)

# Frustrated language that still contains a real ask.
FRUSTRATED_REAL_ASK = (
    "this is infuriating — check that my Google Ads account is actually connected"
)

FALLTHROUGH_CORPUS: tuple[tuple[str, str], ...] = (
    ("google_ads_campaign_brief", GOOGLE_ADS_CAMPAIGN_BRIEF),
    ("google_ads_campaign_brief_live", GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE),
    ("seo_plus_google_ads", SEO_PLUS_GOOGLE_ADS),
    ("venting_plus_google_ads", VENTING_PLUS_GOOGLE_ADS),
    ("connector_lookup", CONNECTOR_LOOKUP),
    ("multi_param_write", MULTI_PARAM_WRITE),
    ("curly_dont_ads", CURLY_DONT_ADS),
    ("quoted_vendors_in_ads", QUOTED_VENDORS_IN_ADS),
    ("enterprise_where_in_ads", ENTERPRISE_WHERE_IN_ADS),
    ("frustrated_real_ask", FRUSTRATED_REAL_ASK),
)

SHORTCUT_CORPUS: tuple[tuple[str, str, str], ...] = (
    ("settings_nav_faq", SETTINGS_NAV_FAQ, "ia_nav_faq"),
    ("ambiguous_seo_only", AMBIGUOUS_CLARIFY, "ambiguous_open_clarify"),
)


@pytest.mark.parametrize("label,message", FALLTHROUGH_CORPUS)
@pytest.mark.asyncio
async def test_adversarial_operator_tasks_fall_through_text_and_voice(label: str, message: str) -> None:
    typed = await evaluate_intent_gateway(GatewayContext(message=message, spoken_mode=False, org_id="org"))
    spoken = await evaluate_intent_gateway(GatewayContext(message=message, spoken_mode=True, org_id="org"))
    assert typed.action == "fallthrough", f"{label} typed served {typed.candidate_id}"
    assert spoken.action == "fallthrough", f"{label} spoken served {spoken.candidate_id}"
    assert typed.reason == spoken.reason == "operator_task_shaped"


@pytest.mark.parametrize("label,message,candidate_id", SHORTCUT_CORPUS)
@pytest.mark.asyncio
async def test_adversarial_narrow_phrases_shortcut_identically(
    label: str, message: str, candidate_id: str
) -> None:
    typed = await evaluate_intent_gateway(GatewayContext(message=message, spoken_mode=False, org_id="org"))
    spoken = await evaluate_intent_gateway(GatewayContext(message=message, spoken_mode=True, org_id="org"))
    assert typed.action == "shortcut", f"{label} typed fell through ({typed.reason})"
    assert spoken.action == "shortcut"
    assert typed.candidate_id == spoken.candidate_id == candidate_id
    assert typed.answer == spoken.answer
