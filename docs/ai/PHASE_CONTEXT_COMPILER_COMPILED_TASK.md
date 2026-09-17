# ContextCompiler compiled_task slice (audit §34 item 5)

**Status:** structural (local). Does not expand the F1 ActionSpec slice. Does not change WRITE governance or G8.  
**Date:** 2026-09-17

E4 includes the §34.4 `compiled_task` projection as one context slice:

- Unified LIVE: `user_parts` label `compiled_task` + inclusion decision `INCLUDE`/`EXCLUDE`
- Classical: same fenced block merged into `entity_relationship_section`
- Trace: `compiled_task_included`

The block is business language (capability, calendar window, source display names, clarification/readiness). It does **not** add tool names, HMAC proof, or GA4 property ids as ask-the-user fields.

Empty/chitchat projections are excluded so the model is not told a fake resolved task.

**NOT PROVEN live:** a production unified-turn trace with `compiled_task` in `context_sources_included`.
