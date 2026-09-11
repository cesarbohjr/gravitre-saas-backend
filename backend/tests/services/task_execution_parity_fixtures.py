"""Shared operator-task prompts for shortcut + text/voice parity tests."""

# Exact class of request that first exposed the Settings FAQ hijack.
GOOGLE_ADS_CAMPAIGN_BRIEF = """
I have a Google Ads campaign strategy ready to go live. Set it up in
Google Ads exactly as specified below, and don't execute anything
without my approval first.

Create four campaigns:

1. RevOps / Sales Ops — 30% budget weight.
2. IT / Security Ops — 30% budget weight. Ad groups include
   "shadow AI in the enterprise" and "enterprise AI agent management platform".
3. DevOps / Engineering Leaders — 20% budget weight.
4. Customer Support Ops — 20% budget weight, including
   "enterprise support automation software".

Before you create anything: check that my Google Ads account is
actually connected and has the right access, confirm you can see my
current account structure so we're not creating duplicates, and show me
the complete plan for what you're about to create, campaign by campaign,
before asking me to approve it.

Once I approve, go ahead and create it, and once it's live, show me
where I can verify each campaign actually exists in my real Google Ads
account, not just that Gravitre says it worked.
"""

# Production brief used by live typed/spoken Ads verification (not a dollar amount).
GOOGLE_ADS_CAMPAIGN_BRIEF_LIVE = """
I have a Google Ads campaign strategy ready to go live. Set it up in Google Ads exactly as specified below, and don't execute anything without my approval first.

Create four campaigns:

1. RevOps / Sales Ops — 30% budget weight. Start on Maximize Conversions (no target) for the first 3 weeks to build conversion history. Ad groups: "Problem Aware" (broad+phrase: sales ops automation tools, manual CRM data entry problem, sales team AI agents, automate sales workflow), "Solution Aware" (phrase+exact: AI agent for Salesforce, AI agent for HubSpot, CRM workflow automation with approval, AI sales agent governance), "Ready to Buy" (exact: Gravitre, Gravitre pricing, AI ops platform for sales teams, best AI agent platform Salesforce).

2. IT / Security Ops — 30% budget weight. Start on Target CPA using the initial demo-request cost as a placeholder target. Ad groups: "Problem Aware" (broad+phrase: AI agent security risk, shadow AI in the enterprise, AI agent without oversight, AI agent compliance problem), "Solution Aware" (phrase+exact: AI agent governance platform, audit trail AI agents, AI agent approval workflow, MCP server security, role-based access AI agents), "Ready to Buy" (exact: Gravitre security, enterprise AI agent management platform, AES-256 AI agent platform, AI agent audit trail software).

3. DevOps / Engineering Leaders — 20% budget weight. Maximize Conversions from the start, optimizing for free trial signup. Ad groups: "Problem Aware" (broad+phrase: AI agents keep failing in production, AI agent orchestration problem, connecting AI agents to internal tools, agent sprawl), "Solution Aware" (phrase+exact: MCP server platform, AI agent orchestration platform, connect AI agents to Jira, connect AI agents to Slack, agent workflow simulation), "Ready to Buy" (exact: Gravitre MCP, Gravitre integrations, best MCP agent platform, AI agent platform 50 integrations).

4. Customer Support Ops — 20% budget weight. Run Target CPA from the outset, borrowing an initial CPA estimate from the RevOps campaign. Ad groups: "Problem Aware" (broad+phrase: support ticket volume too high, customer support automation ideas, AI for customer service team, reduce support response time), "Solution Aware" (phrase+exact: AI agent for customer support, support ops automation, AI workflow approval customer service, customer support agent health score), "Ready to Buy" (exact: Gravitre customer support, AI support agent platform pricing, enterprise support automation software, best AI agent for support ops).

Account-wide, apply these negative keywords to all four campaigns: gravitee, free, open source, jobs, careers, tutorial, course. The "gravitee" one matters — Gravitee.io is a similarly-named competitor and I don't want to pay for their traffic.

Set up "Free Trial Signup" and "Demo Request" as two separate, distinctly-valued conversion actions, don't combine them.

Start every campaign on phrase and exact match only for the first month, no broad match yet.

Before you create anything: check that my Google Ads account is actually connected and has the right access, confirm you can see my current account structure so we're not creating duplicates, and show me the complete plan for what you're about to create, campaign by campaign, before asking me to approve it. I want to see the real, exact structure you're about to build, not just a summary.

Once I approve, go ahead and create it, and once it's live, show me where I can verify each campaign actually exists in my real Google Ads account, not just that Gravitre says it worked.
"""

CONNECTOR_LOOKUP = "Is my Google Ads account connected, and what access does it currently have?"

MULTI_PARAM_WRITE = (
    "In Apollo, create a contact list named Text Voice Parity Battery "
    "and don't execute without my approval first."
)

AMBIGUOUS_CLARIFY = "help me improve our SEO"

# Same surface keywords as the SEO canned open, plus a real operator job.
SEO_PLUS_GOOGLE_ADS = (
    "help me improve our SEO for the Google Ads campaigns we're about to launch"
)

VENTING_PLUS_GOOGLE_ADS = (
    "ugh this is frustrating — create four Google Ads campaigns and "
    "don't execute without my approval"
)
