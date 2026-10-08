import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

const webRoot = resolve(__dirname, "../..")
const read = (path: string) => readFileSync(resolve(webRoot, path), "utf8")

describe("3.0 Plus final composition", () => {
  it("operating lanes size to content instead of the viewport", () => {
    const src = read("components/home/operating-flow.tsx")
    expect(src).toMatch(/data-flow-height="content"/)
    expect(src).not.toMatch(/100dvh-400px/)
    expect(src).not.toMatch(/h-\[420px\]/)
    expect(src).not.toMatch(/overflow-y-auto/)
  })

  it("system outcomes are a collapsible preview in the AI Native view, linked to Activity", () => {
    const src = read("components/home/home-dashboard.tsx")
    const ai = src.indexOf('data-dashboard-view="ai"')
    const reports = src.indexOf('data-dashboard-view="reports"')
    const outcomes = src.indexOf("<SystemOutcomes />")
    expect(outcomes).toBeGreaterThan(ai)
    expect(outcomes).toBeLessThan(reports)
    const outcomesSrc = read("components/home/system-outcomes.tsx")
    expect(outcomesSrc).toMatch(/aria-expanded=\{!collapsed\}/)
    expect(outcomesSrc).toMatch(/href=\{APP_ROUTES\.activity\}/)
  })

  it("system outcomes show counts and backend pass rate only", () => {
    const src = read("components/home/system-outcomes.tsx")
    expect(src).toMatch(/row\.pass_rate != null/)
    expect(src).not.toMatch(/style:\s*["']currency["']|\bUSD\b|\bROI\b|savings/)
  })

  it("public API surfaces advertise no unpublished SDKs and use accepted request bodies", () => {
    const page = read("app/(marketing)/api/page.tsx")
    expect(page).not.toMatch(/@gravitre\/sdk|pip install gravitre|go-sdk|Official SDKs/)
    expect(page).toMatch(/path: "\/api\/operator\/action-plan"/)
    expect(page).toMatch(/"workflow_id": "WORKFLOW_UUID"/)
    expect(read("app/(marketing)/changelog/page.tsx")).not.toMatch(/Official (Node\.js|Python) SDK/)
    const quickstart = read("content/docs/public/api/quickstart.mdx")
    expect(quickstart).toMatch(/"workflow_id": "WORKFLOW_UUID"/)
    expect(quickstart).toMatch(/"primary_context":/)
    expect(read("content/docs/public/guides/how-to/ai-operator.mdx")).not.toMatch(/"instruction":|"environmentId":/)
  })

  it("autonomy panel derives the three canonical labels and fails closed", () => {
    const src = read("components/agents/agent-autonomy-panel.tsx")
    expect(src).toMatch(/READ ONLY/)
    expect(src).toMatch(/ACT WITH APPROVAL/)
    expect(src).toMatch(/ACT WITHIN POLICY/)
    expect(src).toMatch(/deriveAutonomyLabel/)
    expect(src).toMatch(/high-risk actions still require approval/)
    expect(src).not.toMatch(/writes run automatically unless/)
    expect(src).not.toMatch(/<button|onClick=/)
  })

  it("agent overview is a main field plus a knowledge rail", () => {
    const src = read("app/(app)/agents/[id]/page.tsx")
    expect(src).toMatch(/data-agent-main-field=""/)
    expect(src).toMatch(/data-agent-rail=""/)
    expect(src).toMatch(/<AgentAutonomyPanel agentId=\{agent\.id\} \/>/)
    expect(src).toMatch(/<AgentStrengthProfile/)
    expect(src).toMatch(/layout="rail"/)
    expect(src).toMatch(/variant="ruled"/)
    expect(src).not.toMatch(/Radar/)
  })

  it("connectors inspector column shows the operating summary when nothing is selected", () => {
    const src = read("app/(app)/connectors/page.tsx")
    expect(src).toMatch(/\) : \(\s*<ConnectorOperatingSummary/)
    expect(src).toMatch(/className="hidden xl:flex"/)
  })

  it("onboarding does not auto-complete connect without an active connector", () => {
    const src = read("components/gravitre/onboarding-checklist.tsx")
    expect(src).toMatch(/routeMatch\.stepKey === "connect" && !hasActiveConnector/)
    expect(src).toMatch(/\.catch\(\(\) => undefined\)/)
  })

  it("settings preference routes are called with auth headers", () => {
    for (const path of ["lib/agents-fleet-prefs.ts", "lib/dashboard/layout-storage.ts"]) {
      const src = read(path)
      expect(src).not.toMatch(/\bfetch\("\/api\/settings\//)
      expect(src).toMatch(/apiFetch\("\/api\/settings\//)
    }
  })

  it("marketplace saves requests stay within the backend limit (le=100)", () => {
    const src = read("components/marketplace/asset-save-button.tsx")
    expect(src).toMatch(/listSaves\(\{ limit: 100 \}\)/)
  })

  it("builder never seeds a mock pipeline or mock connector statuses", () => {
    const src = read("app/(app)/workflows/[id]/builder/page.tsx")
    expect(src).not.toMatch(/Customer Data Pipeline/)
    expect(src).not.toMatch(/connectorLibrary/)
    expect(src).toMatch(/useState<WorkflowNode\[\]>\(\(\) => seedOverride \?\? \[\]\)/)
  })

  it("workflow cards do not invent connector dependencies", () => {
    const src = read("components/gravitre/workflow-card.tsx")
    expect(src).not.toMatch(/lastSync: "\d+ min ago"|lastSync: "Just now"/)
    expect(src).toMatch(/connectorDependencies \?\? \[\]/)
  })

  it("workflow list comes from the core route", () => {
    const src = read("app/api/workflows/route.ts")
    expect(src).toMatch(/proxyToFastApi\(request, "\/api\/workflows"\)/)
  })

  it("goal progress is not invented", () => {
    const src = read("app/api/goals/[id]/progress/route.ts")
    expect(src).not.toMatch(/Math\.min\(95/)
    expect(src).not.toMatch(/recentDeliverables/)
  })

  it("top bar org label is hydration-stable", () => {
    const src = read("components/gravitre/top-bar.tsx")
    expect(src).not.toMatch(/useState\(\(\) => getSelectedOrgFromStorage\(\)/)
    expect(src).toMatch(/useState\("Organization"\)/)
  })
})
