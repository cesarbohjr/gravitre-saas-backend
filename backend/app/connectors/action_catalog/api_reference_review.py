"""Human verdict for every action whose code reaches more than one endpoint.

The extractor ranks multi-endpoint actions heuristically. A heuristic that is
right 32 times out of 33 still ships one wrong endpoint, and a wrong endpoint in
a drift scan is worse than a missing one: it makes a real vendor change look
like agreement. So every multi-hit action below was read in source and given an
explicit verdict.

``verdict`` values:
  extractor_correct  the ranked primary is the endpoint the action is *for*
  corrected          the ranking picked the wrong one; ``primary`` overrides it

``secondary_role`` says why the other endpoints exist, because "this action hits
three endpoints" is a fact the drift scan needs, not noise to discard — all of
them are recorded in the map's ``endpoints`` list.

The build fails if a multi-hit action has no entry here. That is deliberate: a
newly-ambiguous action must be looked at by a person, not silently ranked.
"""
from __future__ import annotations

from dataclasses import dataclass

REVIEWED = "2026-08-29"


@dataclass(frozen=True)
class AmbiguityVerdict:
    verdict: str
    secondary_role: str
    primary: str | None = None  # set only when verdict == "corrected"


AMBIGUOUS_REVIEW: dict[str, AmbiguityVerdict] = {
    # ---- Apollo: label lookup is a helper, not the action ---------------
    "apollo.contacts.search": AmbiguityVerdict(
        "extractor_correct",
        "GET /labels resolves a list name to an id before searching; the search "
        "itself is POST /contacts/search.",
    ),
    "apollo.lists.create": AmbiguityVerdict(
        "extractor_correct",
        "GET /labels is the pre-create duplicate check; the write is POST /labels.",
    ),
    "apollo.lists.list": AmbiguityVerdict(
        "extractor_correct",
        "POST /contacts/search appears in the shared module scope, not on this "
        "action's path; the action is GET /labels.",
    ),
    # ---- genuinely branches by destination vendor -----------------------
    "clay.crm.sync": AmbiguityVerdict(
        "extractor_correct",
        "Branches on the configured CRM: HubSpot POST /crm/v3/objects/contacts "
        "or Salesforce POST /sobjects/Lead. HubSpot is the default destination; "
        "both endpoints are real and both are recorded.",
    ),
    # ---- ClickUp: GET /team resolves the workspace id first -------------
    "clickup.members.list": AmbiguityVerdict(
        "extractor_correct", "GET /team resolves the default workspace id."
    ),
    "clickup.spaces.list": AmbiguityVerdict(
        "extractor_correct", "GET /team resolves the default workspace id."
    ),
    "clickup.tasks.list": AmbiguityVerdict(
        "extractor_correct",
        "GET /list/{list_id}/task when a list is given, GET /team/{tid}/task "
        "otherwise; GET /team resolves the workspace id. All three are real.",
    ),
    "clickup.time_entries.create": AmbiguityVerdict(
        "extractor_correct", "GET /team resolves the default workspace id."
    ),
    "clickup.webhooks.create": AmbiguityVerdict(
        "extractor_correct", "GET /team resolves the default workspace id."
    ),
    # ---- Confluence: client-side search over two real endpoints ---------
    "confluence.search_files": AmbiguityVerdict(
        "extractor_correct",
        "Not a server-side search. It lists GET /spaces then GET "
        "/spaces/{space_id}/pages per space and filters titles in process, so "
        "both endpoints are hit on every call.",
    ),
    "engagebay.contacts.get": AmbiguityVerdict(
        "extractor_correct",
        "GET /contacts is the email-lookup fallback when no contact id is given.",
    ),
    "finseo.metrics.overview": AmbiguityVerdict(
        "extractor_correct", "GET /projects resolves the project id by domain."
    ),
    # ---- Google Ads: mutate endpoints, search is the read-back ----------
    "google_ads.campaigns.update_budget": AmbiguityVerdict(
        "extractor_correct",
        "googleAds:search reads the current budget resource name before the "
        "campaignBudgets:mutate write.",
    ),
    "google_ads.structure.create": AmbiguityVerdict(
        "extractor_correct",
        "Genuinely creates a whole structure: budget, campaign, ad group, "
        "criteria and conversion actions, each its own :mutate endpoint. "
        "campaigns:mutate is the headline write; all six are recorded.",
    ),
    "google_drive.get_file_content": AmbiguityVerdict(
        "corrected",
        "Always fetches GET /drive/v3/files/{file_id} for metadata first, then "
        "either exports (Google-native docs) or downloads with alt=media. The "
        "metadata read is the one call made on every invocation.",
        primary="GET /drive/v3/files/{file_id}",
    ),
    "gusto.companies.get": AmbiguityVerdict(
        "extractor_correct",
        "GET /companies resolves the company id when none is supplied.",
    ),
    # ---- HubSpot ---------------------------------------------------------
    "hubspot.companies.get": AmbiguityVerdict(
        "extractor_correct",
        "The search endpoint is the by-domain fallback when no company id is given.",
    ),
    "hubspot.contacts.get": AmbiguityVerdict(
        "extractor_correct",
        "The search endpoint is the by-email fallback when no contact id is given.",
    ),
    "hubspot.contacts.search": AmbiguityVerdict(
        "extractor_correct",
        "GET /crm/v3/objects/contacts is the unfiltered list path used when the "
        "search body would be empty.",
    ),
    "hubspot.deals.create": AmbiguityVerdict(
        "extractor_correct",
        "The v4 associations PUT runs after the create to attach the deal to a "
        "contact or company. Both are real writes.",
    ),
    "hubspot.deals.update": AmbiguityVerdict(
        "extractor_correct",
        "The GET is the post-write read-back used by write verification.",
    ),
    "hubspot.deals.update_stage": AmbiguityVerdict(
        "extractor_correct",
        "The GET is the post-write read-back used by write verification.",
    ),
    "hubspot.lists.get": AmbiguityVerdict(
        "extractor_correct",
        "The memberships endpoint is fetched only when membership counts are "
        "requested.",
    ),
    "hubspot.notes.create": AmbiguityVerdict(
        "extractor_correct",
        "The v4 associations PUT attaches the note to its parent record.",
    ),
    "linkedin.prospect.enrich": AmbiguityVerdict(
        "extractor_correct",
        "GET /me is called unconditionally and gates the whole enrichment; "
        "GET /organizationSearch runs only when a company name is supplied.",
    ),
    # ---- Microsoft Graph: explicit drive vs signed-in user's drive ------
    "microsoft365.get_file_content": AmbiguityVerdict(
        "extractor_correct",
        "/drives/{drive_id}/... when a drive id is given, /me/drive/... otherwise.",
    ),
    "microsoft365.get_file_metadata": AmbiguityVerdict(
        "extractor_correct",
        "/drives/{drive_id}/... when a drive id is given, /me/drive/... otherwise.",
    ),
    "microsoft365.search_files": AmbiguityVerdict(
        "extractor_correct",
        "/drives/{drive_id}/root/search when a drive id is given, "
        "/me/drive/root/search otherwise.",
    ),
    "notion.get_file_content": AmbiguityVerdict(
        "corrected",
        "export_page_text calls GET /pages/{page_id} first for the title and "
        "last_edited_time, then walks GET /blocks/{block_id}/children for the "
        "body. The page read comes first and is the anchor for the file id.",
        primary="GET /pages/{page_id}",
    ),
    "pagerduty.incidents.escalate": AmbiguityVerdict(
        "extractor_correct",
        "PUT /incidents is PagerDuty's real bulk manage-incidents endpoint; the "
        "GET reads the incident back after escalation.",
    ),
    "semrush.exports.run": AmbiguityVerdict(
        "corrected",
        "report_type defaults to domain_organic and any unrecognised value also "
        "falls through to domain_organic; only an explicit domain_ranks/overview "
        "reaches the other branch. The extractor ranked the minority branch first.",
        primary="GET /?type=domain_organic",
    ),
    "workday.timeoff.balance.get": AmbiguityVerdict(
        "extractor_correct",
        "With a plan id it reads that plan's balances directly; without one it "
        "lists GET /workers/{wid}/timeOffPlans and fans out per plan.",
    ),
    "workday.workers.get": AmbiguityVerdict(
        "extractor_correct",
        "GET /workers is the search fallback when the worker id is not a direct id.",
    ),
}


def ambiguity_verdict(action: str) -> AmbiguityVerdict | None:
    return AMBIGUOUS_REVIEW.get(action)
