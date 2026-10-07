/**
 * The starter examples set. Shared by the training workbench and the
 * Intelligence › Data "Load starter examples" card so both create the same
 * dataset through the same training endpoints.
 */
export const STARTER_DATASET = {
  name: "Agent persona starter examples",
  type: "examples",
  description: "Seed examples for revenue ops and sync troubleshooting personas.",
} as const

export const STARTER_EXAMPLES = [
  {
    input:
      "Monitor overdue invoices and notify finance when totals exceed $10k",
    expected_output:
      "Set weekly AR review, alert finance when overdue total exceeds threshold, and log actions in CRM.",
  },
  {
    input: "Customer asks why sync-customers failed at step 3",
    expected_output:
      "Identify timeout at transformation step, recommend retry with 60s timeout and off-peak schedule.",
  },
] as const
