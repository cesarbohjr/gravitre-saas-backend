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
