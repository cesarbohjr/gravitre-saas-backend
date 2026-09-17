# Capability recipe: traffic = GA4 + optional GSC (audit §34 item 6)

**Status:** structural (local). Does not expand the F1 ActionSpec slice. Does not change WRITE governance or G8.  
**Date:** 2026-09-17

`analytics.website-traffic-overview` recipe:

| Step | Capability | Required |
|---|---|---|
| Read website traffic | `analytics.traffic_overview` → `google_analytics.reports.run` | Yes |
| Read search performance | `search.performance` → `google_search_console.searchAnalytics.query` | **Optional** |
| Compose | agent | n/a |

Optional GSC does not mark the recipe `partial`. GA4 missing does.

`resolve_capability(analytics.traffic_overview)` stays **one** primary action (GA4). GSC is not a competing vendor on that capability — that would have made dual-connect **ambiguous**.

Cross-source ExecutionPlan is built from the recipe when **both** connectors are connected, including ordinary traffic language (not only “how is my website doing”).

**NOT PROVEN live:** production turn with both GA4 and GSC connected executing the two-read plan.
