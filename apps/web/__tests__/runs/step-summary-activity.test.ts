import { describe, expect, it } from "vitest"
import { summarizeActivityLog, summarizeStepActivity, summarizeStepError } from "@/lib/runs/step-summary"

describe("summarizeActivityLog", () => {
  it("turns execution-engine JSON into readable facts", () => {
    const raw = JSON.stringify({
      node_id: "hubspot_crm_sync",
      step_type: "invoke_tool",
      duration_ms: 42,
      attempts: 1,
      input: {
        upstream_outputs: {},
        config: {
          action: "clay.crm.sync",
          instruction: "Call clay.crm.sync with records=$enriched_records",
          param_sources: {
            records: "$enriched_records",
            crm: "hubspot",
            crm_connector_id: "$hubspot_connector_id",
          },
        },
      },
      output: null,
      error_code: "step_failed",
      error_message: "clay.crm.sync requires records or record",
    })
    const summary = summarizeActivityLog(raw)
    expect(summary.isStructured).toBe(true)
    expect(summary.headline).toMatch(/no contact records/i)
    expect(summary.facts.some((f) => f.label === "Upstream inputs" && /none/i.test(f.value))).toBe(true)
    expect(summary.facts.some((f) => f.label === "Action")).toBe(true)
    expect(summary.facts.some((f) => f.label === "Bindings")).toBe(true)
  })

  it("summarizeStepActivity handles array logs", () => {
    const rows = summarizeStepActivity([
      JSON.stringify({
        step_type: "invoke_tool",
        input: { upstream_outputs: { clay_push: { records: [1] } }, config: { action: "clay.crm.sync" } },
        output: { synced: [] },
      }),
    ])
    expect(rows).toHaveLength(1)
    expect(rows[0].isStructured).toBe(true)
    expect(rows[0].facts.some((f) => f.label === "Upstream inputs" && f.value.includes("1"))).toBe(true)
  })

  it("translates clay.crm.sync missing records errors", () => {
    const err = summarizeStepError("clay.crm.sync requires records or record")
    expect(err?.title).toMatch(/no contact records/i)
    expect(err?.fix).toBeTruthy()
  })
})
