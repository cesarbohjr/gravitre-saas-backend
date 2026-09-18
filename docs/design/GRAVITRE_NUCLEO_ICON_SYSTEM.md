# GRAVITRE NUCLEO ICON SYSTEM

**Program:** UX Reset 2.0 (planning). **Not production-implemented.**  
**Cesar amendment:** semantic migration, **not** file-count. Success = consistency on **visible authenticated product icons**.

**Provisional family:** Nucleo Sharp, 24px grid, outline (`semantic.tsx`). Validate at 14/16/18/20/24 in `/dev/ai-workspace-preview` before locking. Repo has **no** Mini/duotone set to compare — do not switch families without library evidence.

**Forbidden catch-alls:** sparkles, brain-for-everything, stars, magic wand, robot, generic bolt. `AiOutline24` contains a filled star — do not use it as Gravitre AI identity; use Chat / Command / Run / Connector by **function**.

**Brand mark:** service logos stay vendor marks.

**Evidence class:** repository read 2026-09-17. Counts are import-file counts, not a rewrite backlog.

---

## Current state

| Source | Files (approx.) | Role |
| --- | --- | --- |
| Lucide (`lucide-react`) | ~306 | Default shadcn / most product pages |
| Nucleo semantic (`SEMANTIC_NUCLEO`) | ~72 | AI chrome, some hubs |
| Phosphor | ~61 | Intelligence / admin |
| `@/lib/icons` facade | ~33 | Lucide map + ~15 Nucleo overrides |
| Public Nucleo sprites | 1 | Legacy `nucleo-icon.tsx` |
| Nodus nav outline | Activity glyph via `NavActivity` |

**Debt:** Lucide is still the majority **import** language. That is **not** a 306-file rewrite ticket. Classify before replacing:

| Class | Examples | 2.0 action |
| --- | --- | --- |
| Visible product | Sidebar, AI chrome, tables, agents, workflows | Semantic Nucleo first |
| Developer-only | `/dev/*`, e2e shots, stories | Ignore until last |
| Legacy | Unused `nucleo-icon.tsx` sprites | Delete when unused |
| Service logos | HubSpot/Slack/Google | Never Nucleo |
| Specialized | Charts, builder node type marks | Case-by-case |
| No user impact | Dead imports | Delete, don’t “migrate” |

---

## Family / style rule (2.0)

| Rule | Value |
| --- | --- |
| Family | Nucleo Sharp Essential, 24px |
| Default size | 16px in nav / tables; 20px in composers; 24px only as identity |
| Weight | Outline. Do not mix filled + outline in one toolbar |
| Color | Inherit `currentColor`. Semantic color only for status (success / warning / danger / intelligence) |
| Containers | Default **icon + label**. Circle/tile only for graph nodes, drag objects, selected identity |
| Exceptions | Service logos; Gravitre wordmark; voice waveform (existing `VoiceStateVisualizer`) |

Minimize / mic files that combine a Nucleo path with a small accent line stay disclosed as compound glyphs.

---

## Semantic map (shipped)

From `SEMANTIC_NUCLEO` in `apps/web/components/icons/nucleo/semantic.tsx`:

| Concept | Export | Source glyph | Where used | Where not |
| --- | --- | --- | --- | --- |
| Agent | `NucleoAgent` | AiOutline24 | Teammate identity | Not “all AI” |
| Connector | `NucleoConnector` | PlugOutline24 | Gravitre connect action | Not HubSpot/Slack marks |
| Intelligence | `NucleoIntelligence` | BrainNodesOutline24 | GIBE / hub | Not every sparkle |
| Voice | `NucleoVoice` | WaveformLinesOutline24 | Voice as concept | Not the live visualizer |
| Approval | `NucleoApproval` | ShieldCheckOutline24 | Governance | Not generic “secure” |
| Workflow | `NucleoWorkflow` | BranchMergeOutline24 | Orchestration | Not git |
| Activity | `NucleoActivity` | Nodus `NavActivity` | Execution log | — |
| Expand / collapse / minimize / fullscreen | matching exports | Sharp 24 | AI window controls | Not page headers |
| Mic / attach / send / run | matching | Sharp 24 | Composer | — |
| Success / error | matching | Sharp 24 | Status | Not decorative |
| Settings / history / new chat / chat / panel | matching | Sharp 24 | Workspace chrome | — |
| Search / command / bell / menu | matching | Sharp 24 | Global chrome | — |

---

## Taxonomy to complete in production (Reset 2.0)

Every row: **Nucleo Sharp 24 outline**, default **16px**, inherit color, **icon + label** unless noted.

| Concept | Proposed Nucleo role | Color rule | Usage |
| --- | --- | --- | --- |
| Dashboard | Layout / overview glyph (new map key) | inherit | Nav only |
| AI / Gravitre | Existing chat / command | inherit | Workspace, Ask |
| Agents / Team | Agent + group variant (need second glyph) | inherit | Team view |
| Run | Existing `run` | inherit | Lists |
| Connector | Existing plug | inherit | Gravitre action |
| Learning | Intelligence variant or book-nodes (new) | `--g-intelligence` only on active learning | Learning |
| Relationship | Node-edge (new) | `--g-signal` on selected edge | Graph |
| Knowledge / Memory / Evidence / Source | Distinct outline glyphs (new) | inherit | Inspector |
| Performance | Trace / stopwatch (new) | inherit | Performance |
| Model / Training | Cube / dataset (new) | inherit | Expert surfaces |
| Marketplace | Storefront (new) | inherit | Discovery |
| Enterprise / Organization | Building (new) | inherit | Settings |
| Customer / Person | Person outline (new) | inherit | CRM objects |
| Vendor | Use **service logo** | brand asset | Connectors |
| Product / Report | Document (new) | inherit | — |
| Tool | Wrench/terminal (new) | inherit | Tool calls |
| Filter / sort / add / edit / delete / archive / restore / refresh | Standard Sharp set | inherit; danger on delete | Tables |
| Execute / pause / resume / retry | Play/pause/rotate | inherit | Runs |
| Inspect / trace / history | Panel / path / history | inherit | Diagnostics |
| Security / governance / audit | Shield variants | inherit | Settings |
| Success / warning / failure / waiting | Existing + amber wait | semantic | Status |

**Replace:** Lucide on authenticated nav, tables, AI chrome, agents, workflows, intelligence. Keep Lucide only as a last fallback until the map has a glyph.

**Do not replace:** connector service logos (`simple-icons` / brand assets pipeline).

---

## Agent identity (2.0)

Current: `lib/agent-identity.ts` color IDs + avatars (`AgentAvatar`, pulse). Reset 2.0 target: Nucleo **role** icon + restrained identity color + name + role + department. Runtime status is separate (dot / line), not a glowing cartoon.

---

## Icon-only actions

Accessible name required. Hit target ≥ 32px (mobile 44px). No unlabeled sparkle.

---

## Delivery

Production replacement is **Foundation slice** of UX Reset 2.0, after approval. This file is the map; it does not swap Lucide in `apps/web` yet.
