"use client"

import { ChatExecutionPanel, type ChatExecutionResult } from "@/components/gravitre/assistant/chat-execution-panel"

const SCENARIOS: Record<string, ChatExecutionResult> = {
  apollo_external: {
    success: true,
    entity_type: "connector",
    entity_id: "conn-apollo-1",
    connector_management_url: "/connectors/conn-apollo-1",
    result_url: "https://app.apollo.io/#/lists/abc123",
    integration: "apollo",
    title: "Create contact list",
    body: 'Created contact list "MSP Prospects" (id: abc123).',
    task_label: "Create contact list",
  },
  /** Canonical matched preview for connector writes — BusinessOutcome evidence card. */
  business_outcome: {
    success: true,
    entity_type: "connector",
    entity_id: "conn-apollo-bo",
    integration: "apollo",
    title: "Create contact list",
    body: 'Created contact list "MSP Prospects".',
    task_label: "Create contact list",
    result_url: "/runs/run-bo-fixture",
    business_outcome: {
      id: "run-bo-fixture",
      orgId: "org-fixture",
      kind: "created_record",
      title: "Create contact list",
      status: "completed",
      lifecycleState: "presented",
      source: "assistant_chat",
      projection: "business_outcome",
      runId: "run-bo-fixture",
      sections: {
        summary: 'Created contact list "MSP Prospects" in Apollo.',
        evidence: {
          integration: "apollo",
          entityType: "list",
          entityId: "abc123",
          links: [
            {
              label: "View in Apollo",
              href: "https://app.apollo.io/#/lists/abc123",
              kind: "vendor",
            },
            { label: "View run", href: "/runs/run-bo-fixture", kind: "gravitre" },
          ],
        },
        verification: {
          verified: true,
          method: "module_a_verified_output",
          detail: "Vendor URL present on Module A verified_output.",
        },
        explanation: "This list was created through a governed catalog write.",
      },
    },
  },
  internal_doc: {
    success: true,
    entity_type: "connector",
    entity_id: "conn-doc-1",
    result_url: "/docs/guides/how-to/agents",
    title: "Task completed",
    body: "Created contact list with inline summary.",
    task_label: "Create contact list",
  },
  inline_only: {
    success: true,
    entity_type: "connector",
    entity_id: "conn-apollo-2",
    connector_management_url: "/connectors/conn-apollo-2",
    integration: "apollo",
    title: "Create contact list",
    body: 'Created contact list "Inline summary only".',
    task_label: "Create contact list",
  },
}

export function ExecutionResultHarness({ scenario }: { scenario: string }) {
  const payload = SCENARIOS[scenario]
  if (!payload) {
    return (
      <main className="p-8">
        <h1>Unknown scenario</h1>
        <p>Valid scenarios: {Object.keys(SCENARIOS).join(", ")}</p>
      </main>
    )
  }

  return (
    <main className="mx-auto max-w-xl p-8" data-testid="execution-result-harness">
      <h1 className="mb-4 text-lg font-semibold">ExecutionResult harness ({scenario})</h1>
      <ChatExecutionPanel executionResult={payload} />
    </main>
  )
}
