// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import type { IntelligencePageContextResponse } from "@/lib/api"
import { IntelligenceBrain } from "@/components/intelligence/brain/intelligence-brain"

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() } }))
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

let root: Root
let container: HTMLDivElement
const now = new Date().toISOString()
const metrics = {
  knowledge: { knownEntities: 3 },
  learning: { relationshipsLearned: 2, modelsTracked: 0 },
  predictions: {},
  execution: {},
  outcomes: { outcomeEventsInWindow: 1 },
}
const pageContext: IntelligencePageContextResponse = {
  snapshot: {
    generatedAt: now,
    tenantId: "org",
    timeWindowHours: 24,
    coreState: "flow-inward",
    agents: [],
    predictions: [],
    learnings: [],
    models: [],
    knowledgeEntityTypes: ["deal"],
    metrics,
    qualityFlags: [],
    departments: [],
    outcomes: [{ id: "o1", event: "approval_granted", entityType: "deal", createdAt: now }],
  },
  graph: { nodes: [], edges: [] },
  activeLens: "knows",
  availableLenses: [],
  metrics,
  qualityFlags: [],
  suggestedQuestions: [],
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })))
  container = document.createElement("div")
  document.body.append(container)
  root = createRoot(container)
})
afterEach(() => {
  act(() => root.unmount())
  container.remove()
  vi.unstubAllGlobals()
})

const button = (name: string) =>
  [...container.querySelectorAll("button")].find((b) => b.textContent?.trim() === name) as HTMLButtonElement

it("renders the live overview from real records and drills into a node", () => {
  const onSelect = vi.fn()
  act(() => root.render(<IntelligenceBrain pageContext={pageContext} candidates={[]} connectors={[]} onSelectionChange={onSelect} />))
  const text = container.textContent ?? ""
  expect(text).toContain("Intelligence core")
  expect(text).toContain("Signals processed today")
  expect(text).toContain("How Gravitre is connecting the dots")
  expect(text).toContain("A teammate approved an agent's action")
  expect(text).toContain("Nothing is being reinforced yet")
  expect(container.querySelector('[data-example="false"]')).not.toBeNull()
  expect(button("Live data").getAttribute("aria-pressed")).toBe("true")

  const deal = container.querySelector('g[aria-label^="Deal"]') as SVGGElement
  act(() => deal.dispatchEvent(new MouseEvent("click", { bubbles: true })))
  expect(container.textContent).toContain("Open in Knowledge →")
  expect(onSelect).toHaveBeenLastCalledWith({ kind: "entity", id: "kn:deal", label: "Deal" })
})

it("switches to badged example data on request", () => {
  act(() => root.render(<IntelligenceBrain pageContext={pageContext} />))
  act(() => button("Example data").click())
  expect(container.querySelector('[data-example="true"]')).not.toBeNull()
  expect(container.textContent).toContain("Example")
  expect(container.textContent).toContain("Cold-chain routing")
  act(() => button("Pause").click())
  expect(button("Play").getAttribute("aria-pressed")).toBe("true")
})
