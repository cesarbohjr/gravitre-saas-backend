# 19 — SaaSFrame research → Gravitre design mapping

**Date:** 2026-09-24  
**Branch:** `feat/gravitre-3.0-plus-frontend`  
**Authority:** Master Spec §8.4 · §35 · §39  
**Visual system:** Nodus / Gravitre tokens (TYPE, `--g-*`) — not SaaSFrame branding.

## Access limitation (honest)

| Access | What was available |
|--------|--------------------|
| Free SaaSFrame | Category indexes; **full screen previews** on example pages for Wise Dashboard + Mintlify Dashboard; structure write-ups; pattern tags |
| Free SaaSFrame | Hugging Face Interactive AI Space + Dust Chat example pages load; pattern tags visible (AI Chat, Prompt Input, AI Generation State, Chat Feed, Sidebar) |
| **SaaSFrame Pro** | 173 additional dashboard screens; product-interface galleries for Wise/Dust/etc.; Figma downloads — **not accessible without Pro** |
| Not claimed inspected | Full Pro library screens (Cloudflare, Unkey, Prelude, Intercom Setup AI Chatbot product galleries behind Pro, etc.) |

Harness previews: `?s=saasframe` (research→design trace) + updated Phase 6 surfaces.

---

## Screens actually inspected

### 1. Wise Dashboard
- **URL:** https://www.saasframe.io/examples/wise-dashboard  
- **Collection:** https://www.saasframe.io/categories/dashboard  
- **Product / screen:** Wise · Home dashboard  
- **Patterns tagged:** Sidebar Navigation · Dashboard · Metrics · Filter · Card · Charts  
- **User problem:** Orient on money status + take primary actions without hunting.  
- **Structure worth adopting:** Narrow rail · hero status metric · one accent primary action + secondary actions · entity cards · activity list (“See all”).  
- **Interaction:** Primary CTA emphasis; list → detail via See all.  
- **Do NOT copy:** Wise green brand, finance metaphors, currency flags, promo banners.  
- **Gravitre interpretation:** Dashboard attention-first = “Needs you” hero + Resolve next + running/changed strips + activity table (fixture).  
- **Preserve:** Approvals / runs / connectors / Intelligence change signals — no invented KPIs.

### 2. Mintlify Dashboard
- **URL:** https://www.saasframe.io/examples/mintlify-dashboard  
- **Product / screen:** Mintlify · Documentation portal home  
- **Patterns:** Sidebar Navigation · Dashboard · Metrics · Filter · Card  
- **User problem:** Return to work; see live status + recent activity + incomplete setup.  
- **Structure:** Compact sidebar · greeting + secondary actions · progress stepper · hero status card · activity table (success/fail rows).  
- **Interaction:** Progressive setup disclosure; activity rows as operational truth.  
- **Do NOT copy:** Mintlify leaf brand, “Good afternoon” marketing tone, docs-site thumbnails as decoration.  
- **Gravitre interpretation:** Page-intro Operating = greeting strip + setup/attention stepper + primary work card + activity (not 3 equal KPI cards). Dashboard ops-board uses activity table language.  
- **Preserve:** Connectors / runs / approval statuses as real product entities.

### 3. June Report
- **URL:** https://www.saasframe.io/examples/june-report  
- **Also listed:** https://www.saasframe.io/categories/dashboard (June Dashboard free thumbnail)  
- **Product / screen:** June Analytics · Report  
- **Patterns (write-up):** Sticky sidebar · report header · filters/share · card segments · progressive summary→detail · Desktop + Mobile variants  
- **User problem:** Dense analytics without losing context.  
- **Structure:** Fixed zones (nav / header+filters / insight cards).  
- **Do NOT copy:** Blue marketing accents, vanity charts without business meaning.  
- **Gravitre interpretation:** Intelligence Field-primary = insight header + evidence cards + Field canvas (not empty graph). Model Studio Advanced = sticky list + filterable config groups.  
- **Preserve:** Intelligence journey Insight→Evidence→Relationship→Expert; Matrix/KG tools.

### 4. Hugging Face Interactive AI Space
- **URL:** https://www.saasframe.io/examples/hugging-face-interactive-ai-space  
- **Collection:** https://www.saasframe.io/patterns/ai-generation-state  
- **Patterns tagged:** Playground · AI Chat · Prompt Input · **AI Generation State**  
- **User problem:** Make generation progress, streaming, and regenerate legible.  
- **Structure / interaction:** Explicit generation states (loading / streaming / complete / regenerate) beside prompt + output.  
- **Do NOT copy:** HF community chrome, model zoo marketing.  
- **Gravitre interpretation:** AI workspace scenes for `generating` / `streaming` / `complete` / `needs-approval` — fixture task states, not a second chat runtime.  
- **Preserve:** Core chat API/SSE, artifacts, voice contracts.

### 5. Dust Chat Interface
- **URL:** https://www.saasframe.io/examples/dust-chat-interface  
- **Also catalogued:** Dust Dashboard (Pro-gated full gallery)  
- **Patterns tagged:** Chat · Chat Feed · AI Chat · Prompt Input · Sidebar Navigation  
- **User problem:** Agent conversation + context rail without losing the work object.  
- **Structure:** Sidebar + chat feed + prompt dock — split workspace.  
- **Do NOT copy:** Dust branding / agent marketplace look.  
- **Gravitre interpretation:** Window Manager docked + AI workspace conversation/work split; Agent roster→detail.  
- **Preserve:** Stable conversationId/taskId across WM modes; no remount of core agent.

### Catalogued but Pro-gated (named only — screens not claimed inspected)
Dust Dashboard, Cloudflare Dashboard×3, Unkey, Prelude, FullEnrich, Intercom Setup AI Chatbot, Profound Citations, etc. appear in category indexes / “Upgrade to Pro” walls.

---

## Experience map (Gravitre ← SaaSFrame)

| Gravitre experience | Primary refs | Pattern → interpretation |
|---------------------|--------------|---------------------------|
| Dashboard | Wise + Mintlify | Hero attention + action row + activity table |
| Page intro (Operating) | Mintlify | Greeting/lead + stepper + primary work card — replace equal 3-card KPI strip |
| Window Manager | Dust Chat tags + Wise rail | Persistent side workspace; page remains visible when docked |
| Intelligence | June Report zones | Insight header + evidence cards + Field — not blank canvas |
| AI workspace | HF AI Generation State + Dust Chat | Explicit gen states + feed + artifact pane |
| Agent workspace | Dust Chat / Dashboard catalog | Roster rail + detail + Create |
| Workflows / monitoring | Mintlify activity table | Success/fail rows with timestamps (fixture) |
| Model Studio | Mintlify progressive disclosure + June filters | Standard purpose/actions; Advanced config groups |
| Connectors / Knowledge / Approvals | Mintlify activity + Wise list | Status list + primary next action; empty explains why |

---

## Reference hierarchy reminder

| Source | Role |
|--------|------|
| Nodus / Aceternity | Visual foundation |
| **SaaSFrame** | Product screen architecture (this doc) |
| SaaSUI | Enterprise tables/settings/admin |
| Mobbin | Full journeys |
| Refero | Research assist |
| Beautiful UI | AI widgets |
| 21st.dev | Components **after** structure chosen |

---

## Cesar decisions still reserved

A–F + §40 unchanged; SaaSFrame refinements improve options — they do not auto-approve Phase 8.
