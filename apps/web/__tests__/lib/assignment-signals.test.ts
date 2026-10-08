import { describe, expect, it } from "vitest"
import {
  actionStats,
  assignmentFlag,
  classifyIssue,
  humanizeToolName,
  reportedConfidencePercent,
  upgradeLinkFrom,
} from "@/lib/assignment-signals"

const failedCall = (tool: string, error: string) => ({ tool, result: { success: false, error, action: tool } })
const okCall = (tool: string) => ({ tool, result: { success: true, action: tool } })

describe("assignment signals", () => {
  it("names tools in plain language", () => {
    expect(humanizeToolName("apollo.organizations.search")).toBe("Search organizations")
    expect(humanizeToolName("apollo.lists.list")).toBe("List Apollo lists")
    expect(humanizeToolName("hubspot")).toBe("Hubspot")
  })

  it("counts reported tool calls and returns null when none were reported", () => {
    expect(actionStats(undefined)).toBeNull()
    expect(actionStats([])).toBeNull()
    expect(actionStats([okCall("a.b.list"), failedCall("a.b.search", "x")])).toEqual({ total: 2, failed: 1, succeeded: 1 })
  })

  it("derives the flag from the real job error and tool results", () => {
    const error = "Company/contact discovery requires an Apollo plan with search API access. See app.apollo.io to upgrade."
    expect(classifyIssue(error)).toBe("Blocked by plan limit")
    expect(
      assignmentFlag({ status: "completed", error: null, result: { tool_calls: [okCall("apollo.lists.list"), failedCall("apollo.organizations.search", error)] } }),
    ).toEqual({ label: "Blocked by plan limit", tone: "amber", needsLook: true })
    expect(assignmentFlag({ status: "completed", error: null, result: { summary: "Done" } })).toBeNull()
    expect(assignmentFlag({ status: "failed", error: "401 Unauthorized", result: null })?.label).toBe("Needs access")
    expect(assignmentFlag({ status: "running", error: null, result: null })).toBeNull()
    expect(classifyIssue("The execution plan step crashed")).toBe("Failed")
  })

  it("offers an upgrade link only when the reported text names one", () => {
    expect(upgradeLinkFrom("See app.apollo.io to upgrade.")).toEqual({ href: "https://app.apollo.io", label: "Upgrade Apollo plan" })
    expect(upgradeLinkFrom("Upgrade your plan to continue.")).toBeNull()
    expect(upgradeLinkFrom("Visit app.apollo.io for docs")).toBeNull()
    expect(upgradeLinkFrom(null)).toBeNull()
  })

  it("keeps a reported zero confidence and rejects invalid values", () => {
    expect(reportedConfidencePercent(0)).toBe(0)
    expect(reportedConfidencePercent(0.35)).toBe(35)
    expect(reportedConfidencePercent(undefined)).toBeNull()
    expect(reportedConfidencePercent(140)).toBeNull()
  })
})
