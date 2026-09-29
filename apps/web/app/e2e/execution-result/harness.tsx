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
    canonical_table: {
    success: true,
    entity_type: "report",
    entity_id: "plan-table-1",
    title: "Submitted public form fields",
    body: "Submitted the public httpbin form.",
    task_label: "Submitted public form fields",
    artifacts: [
      {
        artifact_id: "report:plan-table-1",
        kind: "table",
        title: "Submitted public form fields",
        preview: "Submitted the public httpbin form.",
        metadata: {
          plan_id: "plan-table-1",
          observation_ids: ["obs-table-1"],
          exportable: true,
          rows: [
            { field: "custname", value: "Isolated Probe" },
            { field: "custemail", value: "isolated@gravitre.test" },
          ],
        },
      },
    ],
    structured: {
      kind: "table",
      plan_id: "plan-table-1",
      observation_ids: ["obs-table-1"],
      exportable: true,
      rows: [
        { field: "custname", value: "Isolated Probe" },
        { field: "custemail", value: "isolated@gravitre.test" },
      ],
    },
  },
  computer_browser_read: {
    success: true,
    entity_type: "report",
    entity_id: "plan-cu-read-1",
    title: "Public web research summary",
    body: "I opened a real browser (not an HTTP fetch) and recorded what loaded.",
    task_label: "Public web research summary",
    artifacts: [
      {
        artifact_id: "report:plan-cu-read-1",
        kind: "research_summary",
        title: "Public web research summary",
        preview: "I opened a real browser (not an HTTP fetch) and recorded what loaded.",
        metadata: {
          plan_id: "plan-cu-read-1",
          observation_ids: ["obs-cu-read-1"],
          exportable: true,
          execution_path: "computer_browser_read",
          rows: [
            { step: "1", title: "Example Domain", url: "https://example.com/", action: "goto" },
            {
              step: "2",
              title: "Example Domains",
              url: "https://www.iana.org/help/example-domains",
              action: "click_link",
            },
          ],
        },
      },
    ],
    structured: {
      kind: "research_summary",
      plan_id: "plan-cu-read-1",
      observation_ids: ["obs-cu-read-1"],
      exportable: true,
      execution_path: "computer_browser_read",
      screenshot_digest: "5f844380de58769434f35b130455e81af710e5a85aff1ada3a630ea4b77a088a",
      rows: [
        { step: "1", title: "Example Domain", url: "https://example.com/", action: "goto" },
        {
          step: "2",
          title: "Example Domains",
          url: "https://www.iana.org/help/example-domains",
          action: "click_link",
        },
      ],
      visits: [
        {
          url: "https://example.com/",
          title: "Example Domain",
          action: "goto",
          screenshot_digest: "6cc928b05a53a95e6adfc303397a58a426b32b638810d93edbf1fb9dc2a833c0",
        },
        {
          url: "https://www.iana.org/help/example-domains",
          title: "Example Domains",
          action: "click_link",
          screenshot_digest: "5f844380de58769434f35b130455e81af710e5a85aff1ada3a630ea4b77a088a",
        },
      ],
    },
  },
  catalog_search: {
    success: true,
    entity_type: "report",
    entity_id: "plan-catalog-1",
    title: "Eligible connected actions",
    body: "Here are connected READ actions that match that search. This is a catalog lookup, not a live provider run.",
    task_label: "Eligible connected actions",
    artifacts: [
      {
        artifact_id: "report:plan-catalog-1",
        kind: "table",
        title: "Eligible connected actions",
        preview: "Here are connected READ actions that match that search.",
        metadata: {
          plan_id: "plan-catalog-1",
          observation_ids: ["obs-catalog-1"],
          exportable: true,
          execution_path: "catalog_search_eligible",
          rows: [
            { action: "List HubSpot contacts", vendor: "hubspot", gate: "READ, connected" },
            { action: "List HubSpot deals", vendor: "hubspot", gate: "READ, connected" },
          ],
        },
      },
    ],
    structured: {
      kind: "table",
      plan_id: "plan-catalog-1",
      observation_ids: ["obs-catalog-1"],
      exportable: true,
      execution_path: "catalog_search_eligible",
      rows: [
        { action: "List HubSpot contacts", vendor: "hubspot", gate: "READ, connected" },
        { action: "List HubSpot deals", vendor: "hubspot", gate: "READ, connected" },
      ],
    },
  },
  /** Phase 2 — durable hosted file chips (md/docx/csv/pdf/html). */
  hosted_files: {
    success: true,
    entity_type: "document",
    entity_id: "doc-hosted-1",
    title: "Q3 ops brief",
    body: "Generated document with durable downloads.",
    task_label: "Generate document",
    artifacts: [
      {
        artifact_id: "hosted_file:brief.md",
        kind: "hosted_file",
        title: "q3-ops-brief.md",
        mime_type: "text/markdown",
        result_url: "https://example.com/files/q3-ops-brief.md",
        metadata: { role: "markdown", byteSize: 420, durable: true },
      },
      {
        artifact_id: "hosted_file:brief.docx",
        kind: "hosted_file",
        title: "q3-ops-brief.docx",
        mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        result_url: "https://example.com/files/q3-ops-brief.docx",
        metadata: { role: "docx", byteSize: 8900, durable: true },
      },
      {
        artifact_id: "hosted_file:brief.pdf",
        kind: "hosted_file",
        title: "q3-ops-brief.pdf",
        mime_type: "application/pdf",
        result_url: "https://example.com/files/q3-ops-brief.pdf",
        metadata: { role: "pdf", byteSize: 2100, durable: true },
      },
      {
        artifact_id: "hosted_file:brief.csv",
        kind: "hosted_file",
        title: "q3-ops-brief.csv",
        mime_type: "text/csv",
        result_url: "https://example.com/files/q3-ops-brief.csv",
        metadata: { role: "csv", byteSize: 180, durable: true },
      },
    ],
    structured: {
      title: "Q3 ops brief",
      format: "markdown",
      content: "# Q3 ops brief\n\n- Ship Phase 2 file chips\n- Ship Phase 3 Preview/Code\n",
      code: "# Q3 ops brief\n\n- Ship Phase 2 file chips\n- Ship Phase 3 Preview/Code\n",
      previewFormat: "markdown",
      previewHtml:
        "<!DOCTYPE html><html><body><h1>Q3 ops brief</h1><ul><li>Ship Phase 2 file chips</li><li>Ship Phase 3 Preview/Code</li></ul></body></html>",
    },
  },
  /** Phase 3 — Preview/Code pane with HTML chart (analytics-style). */
  preview_code: {
    success: true,
    entity_type: "report",
    entity_id: "analytics-1",
    title: "Workflow runs (7d)",
    body: "Status breakdown chart ready.",
    task_label: "Analytics",
    structured: {
      title: "Workflow runs (7d)",
      previewFormat: "html",
      code: "statusBreakdown = {'completed': 12, 'failed': 2}\n",
      previewHtml:
        "<!DOCTYPE html><html><body style='font-family:system-ui'><h2>Workflow runs (7d)</h2>" +
        "<svg width='240' height='160'><rect x='40' y='20' width='36' height='120' fill='#059669'/>" +
        "<rect x='100' y='100' width='36' height='40' fill='#059669'/></svg></body></html>",
      hostedFiles: [
        {
          id: "chart:html",
          filename: "workflow-runs-7d.html",
          mime_type: "text/html",
          byte_size: 320,
          role: "html",
          download_url: "https://example.com/files/workflow-runs-7d.html",
          durable: true,
        },
      ],
    },
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
