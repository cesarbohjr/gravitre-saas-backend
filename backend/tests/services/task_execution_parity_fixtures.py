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
