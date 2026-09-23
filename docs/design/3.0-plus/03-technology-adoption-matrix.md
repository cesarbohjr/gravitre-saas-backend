# 03 — Technology adoption matrix (Phase 2)

**Rule:** Do not install because the master spec names it. Cesar approval required for material new platform dependencies.

| Technology | Installed? | Current use | Class | Rationale |
|---|---|---|---|---|
| **Nodus** | Vendored (no npm) | Product chrome, marketing | **Retain / Extend** | Purchased visual foundation |
| **Nucleo** | Copied assets | Partial semantic icons | **Retain / Extend** | Finish optical pass; reduce Lucide |
| **Framer Motion** | Yes | Broad + MotionProvider | **Retain** | Existing motion + reduced-motion |
| **Radix / shadcn / Tailwind 4** | Yes | `components/ui/**` | **Retain** | Anchored overlays; a11y |
| **Direct Floating UI** | Transitive only | Via Radix | **Defer** | Spec: selective anchoring only — **not** Window Manager |
| **@xyflow/react** | Yes | Relationships graph only | **Extend** | Preferred for **workflow** canvas after migration plan |
| **@dagrejs/dagre** | Yes | Graph layout | **Retain** until ELK justified | |
| **ELK.js** | No | — | **Defer / Reject** | Overlaps dagre |
| **React Grid Layout** | No | — | **Evaluate** | Only if freeform dashboard tiles needed |
| **react-resizable-panels** | Yes | Splits | **Retain** | |
| **tldraw** | No | — | **Reject** (workflows) | Parallel canvas truth risk |
| **assistant-ui** | No | — | **Reject** | Conflicts with custom float/composition |
| **AG-UI / CopilotKit** | No | — | **Reject** (default) | Second agent-UI framework |
| **Chromatic** | No | — | **Defer** | Playwright visual already exists |
| **SWR** | Yes | Primary fetch | **Retain** | |
| **@ai-sdk/react / ai** | Yes | Chat transport | **Retain** | Functional contract surface |
| **Custom AI workspace** | First-party | Core product | **Retain / Extend** | Do not replace with chat kit |
| **Custom workflow builder** | First-party | `/workflows/[id]/builder` | **Extend → migrate** | Schema SoT stays `CanvasWorkflowNode` |
| **Playwright** | Repo root | e2e + visual | **Retain** | |
| **GSAP** | Yes | Marketing scroll only | **Retain** (marketing) | Do not expand into product chrome |
| **Recharts** | Yes | Dashboard charts | **Retain** | ECharts in spec → **Defer** |

## Immediate asks for Cesar (dependencies)

None required to continue Phases 0–7 docs/prototypes. **Approval needed before:**

1. Adding React Flow as the **workflow builder** renderer (migration project)  
2. Any paid service (Chromatic)  
3. assistant-ui / CopilotKit / tldraw / ELK installs
