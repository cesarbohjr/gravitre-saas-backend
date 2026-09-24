# 16 — Phase 6 validation notes (harness only)

**Status:** Checklist slots for Phase 6 structural prototypes.  
**Venue:** `/dev/ai-workspace-preview` · branch `feat/gravitre-3.0-plus-frontend`  
**Authority:** Master §42 Phase 6 · §7 Phase 7 validation themes · `13-phase6-prototype-queue.md`  
**Hard rule:** Labels below are **Prototype** outcomes only. They are **not** production PASS, journey proof, or §46 completion evidence.

Selection areas **A–F** = shipped harness surfaces (`13`):

| ID | Area | Harness `?s=` | Maps to |
|----|------|---------------|---------|
| A | Shared window system | `window-manager` | WM docked + modes |
| B | AI conversation + widgets | `ai-workspace` | Conversation / work / show-the-work slot |
| C | React Flow Workflow Builder | `workflow-rf` | Design / live / explain / history |
| D | Intelligence | `intelligence` | Field-primary + prior scenes |
| E | Page intro / hierarchy | `page-intro` | Operating / expert / empty / immersive |
| F | Model Studio | `model-studio` | Standard / advanced |

**Checklist keys:** clarity · hierarchy · preservation · nav · a11y · responsive · state · empty/error · contract · perf

**Marks:** `Prototype PASS` = scene(s) exist and visibly exercise the concern in harness · `PARTIAL` = harness exists but concern only lightly / incompletely covered · `NOT RUN` = no deliberate harness check yet.

---

## A — Window manager (`?s=window-manager`)

| Check | Prototype status | Notes |
|-------|------------------|-------|
| clarity | PARTIAL | Modes visible; not journey-validated |
| hierarchy | PARTIAL | Docked/chrome hierarchy shown; G-STRUCT pending |
| preservation | PARTIAL | Mode scenes; cross-route state not proven |
| nav | PARTIAL | Preview nav only |
| a11y | NOT RUN | No dedicated keyboard/a11y pass recorded |
| responsive | NOT RUN | No viewport matrix recorded |
| state | PARTIAL | Mode switches in harness |
| empty/error | NOT RUN | Not a focus of WM scenes |
| contract | NOT RUN | No backend contract exercised |
| perf | NOT RUN | No harness perf measurement |

---

## B — AI workspace (`?s=ai-workspace`)

| Check | Prototype status | Notes |
|-------|------------------|-------|
| clarity | PARTIAL | Conversation/work composition scenes exist |
| hierarchy | PARTIAL | Slot composition shown; production dual-chrome unresolved |
| preservation | PARTIAL | Scene continuity only; runtime sync NOT RUN |
| nav | PARTIAL | Harness scene switcher |
| a11y | NOT RUN | — |
| responsive | NOT RUN | — |
| state | PARTIAL | Presentation/mode fixtures in preview |
| empty/error | PARTIAL | Some empty/immersive adjacent via page-intro, not full AI error recovery |
| contract | NOT RUN | No live Ask/tool invoke in harness claim |
| perf | NOT RUN | — |

---

## C — Workflow RF (`?s=workflow-rf`)

| Check | Prototype status | Notes |
|-------|------------------|-------|
| clarity | Prototype PASS | Design/live/explain/history scenes shipped |
| hierarchy | PARTIAL | Canvas primacy shown; production cutover gated |
| preservation | Prototype PASS | Option B evidence in `14-option-b-preservation-evidence.md` (schema/save shape) |
| nav | PARTIAL | Mode tabs in harness; product nav NOT RUN |
| a11y | NOT RUN | Keyboard on custom nodes called out as gap in `14` |
| responsive | NOT RUN | — |
| state | PARTIAL | Fixture NodeState coloring; no execute API |
| empty/error | NOT RUN | Failure recovery not harness-focused |
| contract | PARTIAL | Save payload shape demonstrated; HTTP get/save **not** called in harness |
| perf | NOT RUN | Dual-RF bundle noted as low–med concern only |

---

## D — Intelligence (`?s=intelligence`)

| Check | Prototype status | Notes |
|-------|------------------|-------|
| clarity | PARTIAL | Field-primary scene present |
| hierarchy | PARTIAL | Field vs Matrix primacy prototyped; product Matrix primacy still defect |
| preservation | NOT RUN | No production lens/deep-link preservation proof |
| nav | PARTIAL | Lens/scene switch in harness |
| a11y | NOT RUN | — |
| responsive | NOT RUN | — |
| state | PARTIAL | Selection/lens fixtures only |
| empty/error | PARTIAL | Empty density called out; not systematically exercised |
| contract | NOT RUN | No live KG/API proof in harness claim |
| perf | NOT RUN | — |

---

## E — Page intro / hierarchy (`?s=page-intro`)

| Check | Prototype status | Notes |
|-------|------------------|-------|
| clarity | PARTIAL | Operating/expert/empty/immersive variants exist |
| hierarchy | Prototype PASS | Explicit hierarchy variant scenes (G-STRUCT input) |
| preservation | NOT RUN | Concept only |
| nav | PARTIAL | Preview scene nav |
| a11y | NOT RUN | — |
| responsive | NOT RUN | — |
| state | NOT RUN | — |
| empty/error | PARTIAL | Empty variant scene present |
| contract | NOT RUN | — |
| perf | NOT RUN | — |

---

## F — Model Studio (`?s=model-studio`)

| Check | Prototype status | Notes |
|-------|------------------|-------|
| clarity | PARTIAL | Standard/advanced scenes shipped |
| hierarchy | PARTIAL | Progressive disclosure intent; product routes still underserved |
| preservation | NOT RUN | No production model-config preservation proof |
| nav | PARTIAL | Harness scene switch |
| a11y | NOT RUN | — |
| responsive | NOT RUN | — |
| state | PARTIAL | Standard vs advanced fixture states |
| empty/error | NOT RUN | — |
| contract | NOT RUN | No provider/API contract exercised in harness claim |
| perf | NOT RUN | — |

---

## Queued (not A–F yet)

From `13-phase6-prototype-queue.md` — still independent harness work:

1. AI-generated workflow → open/edit/run composition  
2. Dashboard structural concepts  
3. Agent workspace structural concepts  

Treat those as **NOT RUN** across all checklist keys until scenes ship.

## How to promote a cell

1. Harness scene must exist under `/dev/ai-workspace-preview`.  
2. Mark **Prototype PASS** only when the concern is deliberately demonstrated.  
3. Never copy Prototype PASS into `15-coverage-matrix.md` "Test / visual" as customer proof — keep **Harness only** / **NOT PROVEN** until authenticated journey evidence (§46).
