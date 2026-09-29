# 03 — Technology adoption matrix (Phase 2)

**Authority:** Master §7 stack + §8 reference roles.  
**Rule:** Do not install because the master names it. Cesar **G-DEP** required for material new platform dependencies.

| Technology | Installed? | Current use | Class | Rationale |
|---|---|---|---|---|
| Medium + Codewave philosophy | N/A | Conceptual | **Retain** | Intent/adaptive/trust — not implementation |
| Mobbin / SaaSUI / SaaSFrame | N/A | Research | **Reference** | Flow + composition; SaaSFrame dashboard + AI states mandatory |
| Refero | N/A | Research | **Evaluate** | MCP pattern research if accessible |
| Beautiful UI | N/A | AI widget patterns | **Reference** | Normalize to Gravitre — do not adopt styling wholesale |
| 21st.dev | N/A | Component sourcing | **Reference** | Only after structure chosen |
| Nodus / Aceternity | Vendored | Product chrome | **Retain / Extend** | Visual foundation |
| Gravitre design tokens `--np-*` / `--g-*` | Yes | Authoritative | **Retain** | |
| shadcn + Radix + Tailwind 4 | Yes | `components/ui/**` | **Retain** | Prefer extend local primitives |
| Floating UI (direct) | Transitive via Radix | Anchored overlays | **Evaluate / Defer direct** | §14 selective — **not** Window Manager |
| Gravitre Window Manager | Partial first-party | Float/expand/fullscreen/helper | **Extend / Build** | Docked missing — harness `?s=window-manager` |
| React Grid Layout | No | — | **Evaluate** | Only if improves dashboard without parallel state |
| **@xyflow/react** | Yes | Relationships only | **Extend** | §17 preferred WF builder visual layer; **Option B harness authorized**; production cutover gated |
| ELK.js | No | — | **Evaluate** | Auto-layout for generated graphs; dagre retained until justified |
| @dagrejs/dagre | Yes | Graph layout | **Retain** | Until ELK proves better |
| tldraw | No | — | **Defer** | Must not replace Builder/RF/KG/Relationships |
| Existing charts + ECharts | Recharts yes / ECharts no | Dashboard | **Extend selectively / Defer ECharts** | No novelty migrations |
| Motion / Framer Motion | Yes | Product | **Retain** | |
| GSAP | Yes | Marketing | **Retain** (marketing) | Not simple product chrome |
| Three.js | Partial | Selective | **Retain** (high-value only) | |
| GravitreOrb / Wave / VoiceStateVisualizer | Yes | Voice | **Retain** | Canonical across window modes |
| Nucleo | Copied assets | Icons | **Retain / Extend** | Reduce Lucide drift |
| assistant-ui | No | — | **Evaluate** | Preferred chat primitive **if** no second runtime |
| AG-UI / CopilotKit | No | — | **Evaluate** | Adapter/protocol only — never replace cognitive runtime |
| Storybook | No/weak | — | **Evaluate / Add** | §41 canonical states |
| Chromatic | No | — | **Evaluate / Add** | Visual regression — paid gate |
| Playwright | Yes | e2e + visual | **Retain / Strengthen** | Journeys §41 |
| SWR | Yes | Fetch | **Retain** | |
| @ai-sdk/react / ai | Yes | Chat transport | **Retain** | Functional contract |
| Custom AI workspace | First-party | Core | **Retain / Extend** | Canonical runtime |
| Custom workflow builder | First-party | Builder page | **Extend (interim)** | RF Option B target; schema SoT `CanvasWorkflowNode` |

## Immediate Cesar dependency asks

None required to continue Phases 0–7 harness/docs. **Approval before:**

1. Production Workflow Builder cutover to React Flow  
2. Installing assistant-ui, CopilotKit/AG-UI, ELK, RGL, ECharts, Storybook platform, Chromatic  
3. Any second conversation runtime
