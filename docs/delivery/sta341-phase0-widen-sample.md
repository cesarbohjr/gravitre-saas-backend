# STA-341 Phase 0 — Widened Serper vs Tavily sample

**Ran:** 2026-08-11T19:41:30.401607+00:00
**N:** 18
**Verdict:** GO — Serper quality holds on widened sample; proceed to Phase 1

## Summary

- Hold rate: 1.0 (18/18)
- Serper worse/empty/error: 0
- Avg latency Serper/Tavily: 1068ms / 2246ms

## Per-query

| Category | Hold | Domain overlap | Flags | Query |
| -- | -- | -- | -- | -- |
| factual | YES | 4 | — | What is the current US federal funds rate target range? |
| factual | YES | 2 | — | What is the capital of New Zealand? |
| factual | YES | 3 | — | How many bits are in an IPv6 address? |
| current_event | YES | 2 | — | Latest US CPI inflation reading year over year |
| current_event | YES | 3 | — | Who won the most recent Super Bowl? |
| current_event | YES | 3 | — | Current OpenAI CEO name |
| entity | YES | 4 | — | What does Stripe do as a company? |
| entity | YES | 2 | — | Headquarters city of Salesforce |
| entity | YES | 3 | — | Who founded Notion productivity software? |
| entity | YES | 3 | — | What is HubSpot known for? |
| comparison | YES | 3 | — | PostgreSQL vs MySQL primary differences for OLTP |
| comparison | YES | 0 | no_domain_overlap | React vs Vue which is more popular in 2026 enterprise apps |
| comparison | YES | 2 | — | AWS vs Azure market share cloud computing |
| lookup | YES | 4 | — | NIST Cybersecurity Framework 2.0 Govern function summary |
| lookup | YES | 4 | — | CAN-SPAM Act main requirements for commercial email |
| lookup | YES | 4 | — | SBA definition of a small business size standard overview |
| time_sensitive | YES | 4 | — | Today's date UTC and day of week |
| time_sensitive | YES | 0 | no_domain_overlap | Next US federal holiday after today |
