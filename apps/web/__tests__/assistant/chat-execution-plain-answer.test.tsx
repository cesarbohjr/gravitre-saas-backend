import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"
import {
  ChatExecutionPanel,
  repeatsAnswer,
  type ChatExecutionResult,
} from "@/components/gravitre/assistant/chat-execution-panel"

// The HubSpot contact count turn as the backend sends it after a bound read.
const contactCount: ChatExecutionResult = {
  success: true,
  entity_type: "report",
  entity_id: "2c81a222-959b-42a5-90bc-cf2d0d3d6570",
  title: "HubSpot contacts",
  task_label: "HubSpot contacts",
  body: "This HubSpot account has 57 contacts.",
  artifacts: [
    {
      artifact_id: "report:2c81a222-959b-42a5-90bc-cf2d0d3d6570",
      kind: "table",
      title: "HubSpot contacts",
      preview: "This HubSpot account has 57 contacts.",
      source: "e5_execution_plan",
      metadata: { code: "This HubSpot account has 57 contacts.", previewFormat: "markdown" },
    },
  ],
  structured: {
    format: "markdown",
    code: "This HubSpot account has 57 contacts.",
    previewFormat: "markdown",
    title: "HubSpot contacts",
    plan_id: "2c81a222-959b-42a5-90bc-cf2d0d3d6570",
    observation_ids: ["af5d9390-2011-4e23-b4be-808b314e3b00"],
    exportable: true,
    rows: [{ system: "HubSpot", object: "contacts", count: "57", source: "hubspot.contacts.search" }],
    outcome: "completed",
  } as ChatExecutionResult["structured"],
}

const answer =
  "This HubSpot account has 57 contacts.\n\nNothing else is needed from you. If it helps, I can list them, or break them down by owner or lifecycle stage."

function mainArea(html: string): string {
  const cut = html.indexOf('data-testid="execution-details"')
  return cut === -1 ? html : html.slice(0, cut)
}

describe("chat execution panel keeps the answer in plain language", () => {
  it("detects text the answer already says", () => {
    expect(repeatsAnswer("This HubSpot account has 57 contacts.", answer)).toBe(true)
    expect(repeatsAnswer("Two deals are overdue.", answer)).toBe(false)
    expect(repeatsAnswer("", answer)).toBe(true)
  })

  it("moves ids, action keys and the report preview behind Details", () => {
    const html = renderToStaticMarkup(
      <ChatExecutionPanel executionResult={contactCount} answerText={answer} />,
    )
    const main = mainArea(html)
    expect(html).toContain('data-testid="execution-details"')
    expect(html).toContain("<details")
    expect(main).not.toContain("2c81a222")
    expect(main).not.toContain("af5d9390")
    expect(main).not.toContain("hubspot.contacts.search")
    expect(main).not.toContain("preview-code-pane")
    expect(main).not.toContain("57 contacts")
    expect(html).not.toContain("inline summary only")
    // The detail is still there for anyone who opens it.
    expect(html).toContain("hubspot.contacts.search")
  })

  it("shows a recommendation as a plain next step", () => {
    const html = renderToStaticMarkup(
      <ChatExecutionPanel
        executionResult={{
          ...contactCount,
          recommendation: { title: "Review contacts with no owner", suggestedUtterance: "list unowned contacts" },
        }}
        answerText={answer}
      />,
    )
    expect(mainArea(html)).toContain("Next step:")
    expect(mainArea(html)).toContain("Review contacts with no owner")
  })

  it("keeps a generated document visible", () => {
    const html = renderToStaticMarkup(
      <ChatExecutionPanel
        executionResult={{
          success: true,
          title: "Launch brief",
          body: "I drafted the launch brief.",
          structured: { code: "# Launch brief\n\nGoals and timeline.", previewFormat: "markdown" },
        }}
        answerText="Here is the brief."
      />,
    )
    expect(mainArea(html)).toContain("preview-code-pane")
    expect(mainArea(html)).toContain("I drafted the launch brief.")
  })
})
