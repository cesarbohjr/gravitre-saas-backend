import { describe, expect, it } from "vitest"
import {
  approvalGateCount,
  departmentLabel,
  isReportOutput,
  pipelineFitStages,
  requiredAppsLabel,
  templateCadence,
  templateOutput,
  templateSteps,
} from "@/lib/marketplace-template-detail"
import type { MarketplaceConnectorChecklistItem } from "@/types/api"

const workflowConfig = {
  name: "Weekly Team Status Report",
  steps: [
    {
      id: "collect",
      name: "Collect status themes",
      type: "agent",
      metadata: { task: "Draft weekly status bullets covering wins and blockers." },
    },
    { id: "approve", name: "Manager approval", type: "approval_gate" },
    {
      id: "publish",
      name: "Post to Slack",
      type: "invoke_tool",
      config: { action: "slack.post_message" },
    },
  ],
}

describe("template steps", () => {
  it("reads steps, task detail, tool and approval gates from the definition", () => {
    const steps = templateSteps({ config: workflowConfig })
    expect(steps.map((step) => step.title)).toEqual([
      "Collect status themes",
      "Manager approval",
      "Post to Slack",
    ])
    expect(steps[0].detail).toContain("wins and blockers")
    expect(steps[2].tool).toBe("slack.post_message")
    expect(steps.map((step) => step.approval)).toEqual([false, true, false])
    expect(approvalGateCount(steps)).toBe(1)
  })

  it("supports department pack workflow_steps and explicit approval flags", () => {
    const steps = templateSteps({
      config: { workflow_steps: [{ id: "send_email", type: "invoke_tool", requires_approval: true }] },
    })
    expect(steps).toHaveLength(1)
    expect(steps[0].title).toBe("Send email")
    expect(steps[0].approval).toBe(true)
  })

  it("returns nothing when the asset has no workflow definition", () => {
    expect(templateSteps({ config: { documents: [] } })).toEqual([])
    expect(templateSteps({})).toEqual([])
  })
})

describe("template output", () => {
  it("is null unless the definition declares an output", () => {
    expect(templateOutput({ title: "T", config: workflowConfig })).toBeNull()
  })

  it("normalises declared outputs and spots reports", () => {
    const output = templateOutput({
      title: "Weekly Team Status Report",
      config: {
        outputs: [
          {
            title: "Weekly status",
            type: "report",
            sections: ["Wins", "Blockers"],
            metrics: [{ name: "Runs" }, "Approved"],
            destination: "Reports",
          },
        ],
      },
    })
    expect(output).toMatchObject({
      title: "Weekly status",
      kind: "report",
      sections: ["Wins", "Blockers"],
      metrics: ["Runs", "Approved"],
      destination: "Reports",
    })
    expect(isReportOutput(output!)).toBe(true)
  })

  it("accepts a plain sample output description", () => {
    const output = templateOutput({ title: "Find Stale Deals", config: { sampleOutput: "Ranked stale deals." } })
    expect(output?.title).toBe("Find Stale Deals")
    expect(output?.description).toBe("Ranked stale deals.")
    expect(isReportOutput(output!)).toBe(false)
  })
})

describe("cadence, apps and labels", () => {
  it("only states a cadence the definition declares", () => {
    expect(templateCadence({ config: { cadence: "weekly" } })).toBe("Runs weekly")
    expect(templateCadence({ config: { schedule: { cron: "0 9 * * 1" } } })).toBe("Runs on a schedule")
    expect(templateCadence({ config: { trigger: { type: "manual" } } })).toBe("Runs on demand")
    expect(templateCadence({ config: workflowConfig })).toBeNull()
  })

  it("labels required apps from the checklist", () => {
    const item = (required: boolean) => ({ connectorType: "slack", label: "Slack", required }) as MarketplaceConnectorChecklistItem
    expect(requiredAppsLabel({ connectorChecklist: [] })).toBe("No required apps")
    expect(requiredAppsLabel({ connectorChecklist: [item(false)] })).toBe("No required apps")
    expect(requiredAppsLabel({ connectorChecklist: [item(true), item(true)] })).toBe("2 required apps")
  })

  it("formats department labels", () => {
    expect(departmentLabel("Revenue Operations")).toBe("Revenue Operations")
    expect(departmentLabel("customer_success")).toBe("Customer Success")
    expect(departmentLabel("hr")).toBe("HR")
    expect(departmentLabel(null)).toBeNull()
  })
})

describe("pipeline fit", () => {
  it("marks stages that list the asset or reference one of its tools", () => {
    const steps = templateSteps({ config: workflowConfig })
    const stages = pipelineFitStages(
      {
        stages: [
          { stageId: "discover", label: "Discover", references: ["apollo.search"] },
          { stageId: "notify", label: "Notify", references: ["slack.post_message"] },
          { stageId: "report", label: "Report", marketplacePackIds: ["weekly-team-status-report"] },
        ],
      },
      { slug: "weekly-team-status-report" },
      steps,
    )
    expect(stages.map((stage) => [stage.label, stage.matched])).toEqual([
      ["Discover", false],
      ["Notify", true],
      ["Report", true],
    ])
    expect(pipelineFitStages(undefined, { slug: "x" }, steps)).toEqual([])
  })
})
