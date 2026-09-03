# Agent Security Gateway — Phase 0 audit + ship

**Date:** 2026-09-03  
**Principle:** Knowledge is data. System policy is authority. Keep those worlds separated.  
**Critical gap:** Retrieved/external content could enter LLM context without a structural data/authority boundary.

## Pre-flight (memory contamination)

| Item | Status |
|------|--------|
| `memory_contamination_guard` | **Shipped** — live PASS in `memory-hardening-live.json` (`contamination.ok=true`) |
| Write-time `looks_like_injection` | Shipped on extract path only |
| Gateway approach | **Extend** `ai_guardrails` + `memory_contamination_guard` — do not fork regexes or invent parallel risk enums |

## Phase 0 — where external content entered reasoning (pre-gateway)

| Ingress | Pre-gateway | Gap |
|---------|-------------|-----|
| RAG / Knowledge Fabric | Soft `<knowledge_base>` / `<knowledge_fabric>` in **system** | Soft tags ≠ enforcement |
| Tool / connector observations | Raw JSON in `role:tool` (`react_engine`) | **Highest risk** — no fence/scan |
| Web research | Soft `<internet_research>` | Snippets unscanned |
| Extension page context | Soft `<page_context>` in system | DOM fields as system weight |
| Memory recall | Soft memory tags; write-time contamination only | Recall not re-scanned |
| User task | `<untrusted_input>` via ModelRouter/ReAct | Already hard-fenced |

`detect_prompt_injection` ran on assistant **user** turns only (`assistant.py`) — not on documents/tools/web.

## Phase 1–3 — what shipped

Module: `backend/app/services/agent_security_gateway.py`

1. **Structural fence** — all external kinds wrapped in `<external_data kind=… trust="untrusted_external">` with tag-escape  
2. **Injection scanner** — reuses `detect_prompt_injection` + `looks_like_injection` before include; flagged content gets `review_required` + visible SECURITY REVIEW banner  
3. **Authority preamble** — SAFETY_PREAMBLE extended; `harden_authority_system_prompt` on ModelRouter + ReAct  
4. **Tool trust** — five-class `integration_taxonomy` + `catalog_write_authority` (no parallel risk system); unregistered consequential tools → `untrusted_new` / review  
5. **Full sequence** — `run_gateway_sequence`: scan → tool trust → permission → risk → policy → approval → execute gate → audit  

### Wired call sites

- `react_engine._truncate_observation` → `fence_tool_observation`  
- `unified_retrieval_service` knowledge section → `fence_external_content`  
- `adaptive_research_cascade.format_internet_research_section` → `fence_web_research_section`  
- `extension_bridge.build_extension_chat_system_prompt` → `fence_page_context_block`  
- `agent_intelligence._format_rag_context` → `fence_knowledge_section`  
- `agent_memory_service.format_retrieval_prompt_section` / `cognitive_turn_kernel._memory_prompt_section` → `fence_memory_recall_section`  
- `model_router` + ReAct system harden → `harden_authority_system_prompt`  

## Live proof

Artifact: `docs/delivery/agent-security-gateway-live.json`

| Check | Result |
|-------|--------|
| Injection doc flagged | PASS |
| Soft-tag mutation bypass blocked | PASS |
| Full sequence blocks injection without approval | PASS |
| Write requires catalog approval | PASS |
| Untrusted new tool review | PASS |
| Audit emit | PASS — `agent_security_gateway.sequence` |

Pytest: `tests/services/test_agent_security_gateway.py` (12 passed)

## Re-open / regression

Zero parallel gate. Memory contamination write path unchanged; gateway adds **ingress** fencing on recall/RAG/tools/web/page.
