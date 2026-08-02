import { describe, expect, it } from "vitest"

import {
  fromRun,
  kindChipInlineStyle,
  kindColorVar,
  KIND_STYLES,
} from "@/lib/schedules"

describe("schedule kind colors", () => {
  it("maps workflow / task / job to distinct CSS tokens", () => {
    expect(kindColorVar("workflow")).toBe("var(--schedule-workflow)")
    expect(kindColorVar("task")).toBe("var(--schedule-task)")
    expect(kindColorVar("job")).toBe("var(--schedule-job)")
    expect(KIND_STYLES.workflow.softBg).toContain("schedule-workflow")
    expect(KIND_STYLES.task.softBg).toContain("schedule-task")
    expect(KIND_STYLES.job.softBg).toContain("schedule-job")
  })

  it("builds inline chip styles from kind tokens", () => {
    const workflow = kindChipInlineStyle("workflow")
    expect(workflow.borderLeftColor).toBe("var(--schedule-workflow)")
    expect(workflow.backgroundColor).toContain("--schedule-workflow")
    expect(kindChipInlineStyle("task").borderLeftColor).toBe("var(--schedule-task)")
    expect(kindChipInlineStyle("job").borderLeftColor).toBe("var(--schedule-job)")
  })

  it("labels runs as tasks so they are not confused with workflow schedules", () => {
    const item = fromRun({
      id: "r1",
      workflow_id: "wf-1",
      workflow_name: "MSP Prospecting",
      status: "completed",
    } as never)
    expect(item.kind).toBe("task")
    expect(item.title).toBe("Run · MSP Prospecting")
  })
})
