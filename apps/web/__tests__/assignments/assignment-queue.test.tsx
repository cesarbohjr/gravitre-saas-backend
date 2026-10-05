import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { Bot } from "lucide-react"
import { AssignmentQueue, queueBriefing } from "@/components/assignments/assignment-queue"
import type { DemoAssignment } from "@/lib/demo-assignments"

function make(id: string, status: DemoAssignment["status"], extra: Partial<DemoAssignment> = {}): DemoAssignment {
  return {
    id,
    title: `Task ${id}`,
    brief: "",
    agent: { name: "Ledger", role: "", gradient: "", icon: Bot },
    status,
    progress: 0,
    steps: [],
    createdAt: "",
    outputTypes: [],
    destination: "",
    ...extra,
  }
}

const render = (items: DemoAssignment[]) =>
  renderToStaticMarkup(<AssignmentQueue assignments={items} selectedId={null} onActivate={() => {}} />)

describe("AssignmentQueue", () => {
  it("orders sections by attention, not pipeline position", () => {
    const html = render([make("c", "completed"), make("r", "running"), make("a", "needs_approval")])
    const decision = html.indexOf('data-assignment-phase="needs_approval"')
    const working = html.indexOf('data-assignment-phase="running"')
    const delivered = html.indexOf('data-assignment-phase="completed"')
    expect(decision).toBeGreaterThan(-1)
    expect(decision).toBeLessThan(working)
    expect(working).toBeLessThan(delivered)
  })

  it("collapses empty sections into one line instead of empty lanes", () => {
    const html = render([make("r", "running")])
    expect(html).not.toContain('data-assignment-phase="failed"')
    expect(html).toContain("Also: nothing waiting on you, nothing blocked, nothing queued.")
  })

  it("puts the agent's question and the decision entry on the queue itself", () => {
    const html = render([make("a", "needs_approval", { approvalPrompt: "Send to client?" }), make("f", "failed")])
    expect(html).toContain('href="/assignments/a?approval=1"')
    expect(html).toContain("Review and decide")
    expect(html).toContain("Send to client?")
    expect(html).toContain("See why")
    expect(html).toContain("Stopped without reporting a reason.")
  })

  it("never invents progress: unreported progress scans, reported progress fills", () => {
    const unknown = render([make("r", "running", { progress: Number.NaN })])
    expect(unknown).toContain("Progress not reported")
    expect(unknown).not.toContain("aria-valuenow")
    const known = render([make("r", "running", { progress: 62 })])
    expect(known).toContain('aria-valuenow="62"')
  })

  it("leads with a one-sentence briefing built from real counts", () => {
    expect(queueBriefing([make("a", "needs_approval"), make("r", "running"), make("r2", "running")])).toEqual({
      lead: "1 decision is waiting on you.",
      rest: "2 agents at work.",
    })
    expect(queueBriefing([make("c", "completed")]).lead).toBe("All quiet.")
  })
})
