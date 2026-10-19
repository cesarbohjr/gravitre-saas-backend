// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ children, href, ...rest }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}))

import { ExplainabilityPanel } from "@/components/gravitre/assistant/explainability-panel"
import { AssistantSourceLinks } from "@/components/gravitre/assistant/assistant-source-links"
import { RetrievalSummaryPanel } from "@/components/intelligence/retrieval-summary-panel"
import { DecisionTransparencyCard, answerMethodLabel } from "@/components/intelligence/decision-transparency-card"
import { parseContextSources } from "@/lib/context-sources"

;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
let host: HTMLDivElement
let root: Root

beforeEach(() => {
  host = document.createElement("div")
  document.body.append(host)
  root = createRoot(host)
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

async function render(node: React.ReactNode) {
  await act(async () => root.render(node))
}

/** Shape sent by the backend on the LIVE path (data-intelligence → contextSources). */
const streamed = {
  summary:
    "Used 2 documents from your knowledge and your conversation memory, and left out 1 out-of-date source.",
  used: [
    { name: "Pricing FAQ 2026", kind: "Your knowledge", freshness: "updated 2 hours ago" },
    { name: "Discount policy", kind: "Your knowledge", freshness: "updated 5 weeks ago" },
    { name: "Conversation and agent memory", kind: "Memory" },
  ],
  usedCount: 3,
  skipped: [{ reason: "out_of_date", label: "Out of date", count: 1 }],
  freshnessChecked: true,
}

describe("parseContextSources", () => {
  it("keeps a well-formed record and drops junk", () => {
    expect(parseContextSources(streamed)?.used).toHaveLength(3)
    expect(parseContextSources(null)).toBeNull()
    expect(parseContextSources({})).toBeNull()
    expect(parseContextSources({ used: [{ kind: "x" }], skipped: [{ label: "y", count: 0 }] })).toBeNull()
  })
})

describe("Why this answer?", () => {
  it("shows the plain summary, ranked sources with freshness, what was left out, and the help link", async () => {
    await render(
      <ExplainabilityPanel
        contextSources={parseContextSources(streamed)}
        contextExplanation={streamed.summary}
        toolInvocations={[]}
      />,
    )
    await act(async () => host.querySelector("button")!.click())
    const text = host.textContent ?? ""
    expect(text).toContain("Why this answer?")
    expect(text).toContain(streamed.summary)
    // The summary is not repeated when contextExplanation carries the same sentence.
    expect(text.split(streamed.summary).length - 1).toBe(1)
    expect(text).toContain("Sources")
    expect(text).toContain("Pricing FAQ 2026 · Your knowledge · updated 2 hours ago")
    expect(text).toContain("Left out")
    expect(text).toContain("Out of date (1)")
    expect(host.querySelector('a[href="/ai/help/context"]')?.textContent).toBe("How Gravitre uses your context")
  })

  it("renders nothing when there is nothing to explain", async () => {
    await render(<ExplainabilityPanel toolInvocations={[]} />)
    expect(host.textContent).toBe("")
  })
})

describe("Sources under a reply", () => {
  it("lists context sources even when no tool ran", async () => {
    await render(<AssistantSourceLinks invocations={[]} contextSources={parseContextSources(streamed)} />)
    const text = host.textContent ?? ""
    expect(text).toContain("Sources (3)")
    expect(text).toContain("Discount policy")
    expect(host.querySelector('a[href="/ai/help/context"]')).toBeTruthy()
  })

  it("stays hidden with no tools and no context", async () => {
    await render(<AssistantSourceLinks invocations={[]} contextSources={null} />)
    expect(host.textContent).toBe("")
  })
})

describe("plain language, no internal ids", () => {
  it("retrieval summary shows counts, never assignment or memory segment ids", async () => {
    await render(
      <RetrievalSummaryPanel
        summary={{
          domain: "sales_ops",
          sources_searched: 6,
          sources_used: 2,
          retrieval_score: 0.7,
          knowledge_graph_used: true,
          assignment_ids_used: ["9f2c1a7b-1111-2222-3333-444455556666"],
          memory_segments_used: ["seg_abc123", "seg_def456"],
        }}
      />,
    )
    const text = host.textContent ?? ""
    expect(text).not.toMatch(/9f2c1a7b|seg_abc123|Memory segments|Assignments:|Retrieval effectiveness|Knowledge graph/)
    expect(text).toContain("What was searched")
    expect(text).toContain("Used 1 assigned knowledge source.")
    expect(text).toContain("Used 2 saved memories.")
  })

  it("retrieval summary says nothing when nothing was recorded", async () => {
    await render(<RetrievalSummaryPanel summary={{}} />)
    expect(host.textContent).toBe("")
  })

  it("decision card has no runtime or learning jargon", async () => {
    expect(answerMethodLabel("heuristic")).toBe("Built-in rules")
    expect(answerMethodLabel("something_internal")).toBeNull()
    await render(
      <DecisionTransparencyCard
        envelope={{ runtime_status: "heuristic", decision_type: "knowledge_lookup", confidence: 0.6 }}
      />,
    )
    const text = host.textContent ?? ""
    expect(text).not.toMatch(/Heuristic runtime|Learning confidence|Decision transparency|knowledge_lookup/)
    expect(text).toContain("Built-in rules")
    expect(text).toContain("knowledge lookup")
  })
})
