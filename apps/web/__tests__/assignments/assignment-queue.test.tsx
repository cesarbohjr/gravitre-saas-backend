import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"
import { Bot } from "lucide-react"
import { AssignmentQueue } from "@/components/assignments/assignment-queue"
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
  it("orders groups by attention, not pipeline position", () => {
    const html = render([make("c", "completed"), make("r", "running"), make("a", "needs_approval")])
    const decision = html.indexOf("Needs your decision")
    const executing = html.indexOf("Executing")
    const completed = html.indexOf(">Completed<")
    expect(decision).toBeGreaterThan(-1)
    expect(decision).toBeLessThan(executing)
    expect(executing).toBeLessThan(completed)
  })

  it("collapses empty groups into one summary line instead of empty lanes", () => {
    const html = render([make("r", "running")])
    expect(html).not.toContain('data-assignment-phase="failed"')
    expect(html).toContain("Nothing needs your decision, blocked, queued, completed.")
  })

  it("offers Decide only for paused work and links to the approval entry", () => {
    const html = render([make("a", "needs_approval", { approvalPrompt: "Send to client?" }), make("f", "failed")])
    expect(html).toContain('href="/assignments/a?approval=1"')
    expect(html).toContain("Send to client?")
    expect(html).toContain("See why")
    expect(html).toContain("Stopped without reporting a reason.")
  })
})
