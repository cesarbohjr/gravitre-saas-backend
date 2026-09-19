import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"

import { DEFAULT_AGENTS_FLEET_PREFS, normalizeAgentsFleetPrefs } from "@/lib/agents-fleet-prefs"

const webRoot = resolve(__dirname, "../..")

describe("UX Reset Phase 3 — product IA flatten", () => {
  it("agents roster defaults to the operating team view", () => {
    expect(DEFAULT_AGENTS_FLEET_PREFS.view).toBe("team")
    expect(normalizeAgentsFleetPrefs({ version: 1, view: "list" }).view).toBe("team")
    expect(normalizeAgentsFleetPrefs({ version: 2, view: "list" }).view).toBe("list")
    const src = readFileSync(resolve(webRoot, "app/agents/page.tsx"), "utf8")
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
    expect(src).not.toMatch(/NucleoAgent/)
    const identity = readFileSync(resolve(webRoot, "components/agents/fleet-v4/identity-tokens.ts"), "utf8")
    expect(identity).not.toMatch(/NucleoAgent/)
    expect(identity).not.toMatch(/NavSparkles/)
    expect(identity).not.toMatch(/NucleoIntelligence/)
    const team = readFileSync(resolve(webRoot, "components/agents/fleet-v4/team-view.tsx"), "utf8")
    expect(team).not.toMatch(/NodusGravitreHub/)
    expect(team).not.toMatch(/nodusGlow/)
    const inspector = readFileSync(
      resolve(webRoot, "components/agents/fleet-v4/agent-fleet-inspector.tsx"),
      "utf8",
    )
    expect(inspector).not.toMatch(/AgentIdentityAvatar/)
    const graph = readFileSync(resolve(webRoot, "components/agents/fleet-v4/graph-view.tsx"), "utf8")
    expect(graph).not.toMatch(/ConnectorsAtmosphere/)
    const tabs = readFileSync(resolve(webRoot, "components/agents/agents-hub-tabs.tsx"), "utf8")
    expect(tabs).not.toMatch(/from \"@\/components\/gravitre\/hub-tabs\"/)
    expect(tabs).toMatch(/aria-label="Agents hub"/)
  })

  it("connectors default to discovery then a compact management list", () => {
    const src = readFileSync(resolve(webRoot, "app/connectors/page.tsx"), "utf8")
    expect(src).toMatch(/useState<"topology" \| "grid">\("grid"\)/)
    expect(src).toMatch(/variant="list"/)
    expect(src).toMatch(/data-gravitre-connector-row/)
    expect(src).toMatch(/data-review-surface="connectors-management"/)
    expect(src).toMatch(/inspector stays closed until then/)
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
    const strip = readFileSync(
      resolve(webRoot, "components/connectors/available-connectors-strip.tsx"),
      "utf8",
    )
    expect(strip).toMatch(/data-review-surface="connectors-discovery"/)
    expect(strip).toMatch(/>Discovery</)
    expect(strip).not.toMatch(/Available\s*</)
  })

  it("relationships map is not wrapped in a permanent evidence dashboard", () => {
    const src = readFileSync(resolve(webRoot, "app/intelligence/page.tsx"), "utf8")
    expect(src).toMatch(/Attention, learnings, and impact/)
    expect(src).toMatch(/<details className="mx-auto max-w-\[1600px\]/)
    expect(src).toMatch(/aria-label=\{group\.heading\}/)
    expect(src).not.toMatch(/hover:border-\[color:var\(--g-brand-border\)\]/)
    const workspace = readFileSync(
      resolve(webRoot, "components/intelligence/relationships/relationships-workspace.tsx"),
      "utf8",
    )
    expect(workspace).toMatch(/viewMode === "graph"/)
    expect(workspace).toMatch(/\{selection \?/)
    expect(workspace).not.toMatch(/RelationshipMetrics/)
    const toolbar = readFileSync(
      resolve(webRoot, "components/intelligence/relationships/relationship-toolbar.tsx"),
      "utf8",
    )
    expect(toolbar).toMatch(/Neighborhood/)
    expect(toolbar).toMatch(/>\s*Focus\s*</)
  })

  it("performance leads with outcome then stages; inspector closed until selection", () => {
    const src = readFileSync(
      resolve(webRoot, "components/intelligence/pages/performance-stage.tsx"),
      "utf8",
    )
    const outcome = src.indexOf("{TYPE.eyebrow}>Outcome</p>")
    const flow = src.lastIndexOf("<OutcomeAttributionFlow")
    const metrics = src.indexOf("Totals for the selected view")
    expect(outcome).toBeGreaterThan(0)
    expect(flow).toBeGreaterThan(outcome)
    expect(metrics).toBeGreaterThan(flow)
    expect(src).toMatch(/AgentContributionRow/)
    expect(src).not.toMatch(/AgentContributionCard/)
    expect(src).toMatch(/bars are omitted rather than invented/)
    const flowSrc = readFileSync(
      resolve(webRoot, "components/intelligence/outcome-attribution-flow.tsx"),
      "utf8",
    )
    expect(flowSrc).toMatch(/Contributing stages/)
    expect(flowSrc).toMatch(/useState<string \| null>\(null\)/)
    expect(flowSrc).toMatch(/\{selected \?/)
  })

  it("settings preference chrome uses rows, not elevated cards", () => {
    const src = readFileSync(resolve(webRoot, "app/settings/page.tsx"), "utf8")
    expect(src).toMatch(/AI Operator/)
    const operatorIdx = src.indexOf("AI Operator")
    const operatorWindow = src.slice(Math.max(0, operatorIdx - 700), operatorIdx)
    expect(operatorWindow).toMatch(/border-b border-divide py-3/)
    expect(operatorWindow).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    expect(src).toMatch(/Enable/)
  })

  it("settings organizations are a list with inspector on selection", () => {
    const src = readFileSync(resolve(webRoot, "app/settings/organizations/page.tsx"), "utf8")
    expect(src).toMatch(/data-review-surface="settings-orgs-queue"/)
    expect(src).toMatch(/data-review-surface="settings-orgs-inspect"/)
    expect(src).toMatch(/inspector stays closed until then/)
    expect(src).toMatch(/data-review-cta="switch-org"/)
    expect(src).not.toMatch(/from \"@\/components\/ui\/card\"/)
    expect(src).not.toMatch(/org\.plan \?\? \"Free\"/)
    const prefs = readFileSync(resolve(webRoot, "app/settings/page.tsx"), "utf8")
    expect(prefs).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    const harness = readFileSync(
      resolve(webRoot, "app/dev/ai-workspace-preview/_components/design-exploration-shell.tsx"),
      "utf8",
    )
    expect(harness).toMatch(/\"settings\"/)
    expect(harness).toMatch(/SelectedSettings/)
    const enterprise = readFileSync(resolve(webRoot, "app/settings/enterprise/page.tsx"), "utf8")
    expect(enterprise).toMatch(/aria-label="Enterprise settings"/)
    expect(enterprise).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    const federation = readFileSync(resolve(webRoot, "app/settings/federation/page.tsx"), "utf8")
    expect(federation).not.toMatch(/TabsList/)
    expect(federation).toMatch(/aria-label="Federation activity"/)
  })

  it("workflow builder states intent then canvas and inspects config on the node", () => {
    const src = readFileSync(resolve(webRoot, "app/workflows/[id]/builder/page.tsx"), "utf8")
    expect(src).toMatch(/data-review-surface="workflow-intent"/)
    expect(src).toMatch(/traceOverlay/)
    expect(src).toMatch(/Inspect ·/)
    expect(src).toMatch(/not behind Ask/)
  })

  it("runs lead with outcome evidence and keep TRACE as a drill-down", () => {
    const run = readFileSync(resolve(webRoot, "app/runs/[id]/page.tsx"), "utf8")
    const outcome = run.indexOf('data-review-surface="run-outcome"')
    const trace = run.indexOf('data-review-surface="run-trace"')
    expect(outcome).toBeGreaterThan(0)
    expect(trace).toBeGreaterThan(outcome)
    expect(run).toMatch(/eyebrow="Outcome"/)
    expect(run).toMatch(/Drill-down into this run/)
    const activity = readFileSync(resolve(webRoot, "app/activity/page.tsx"), "utf8")
    expect(activity).not.toMatch(/selectedOutcomeExplicit \?\? outcomes\[0\]/)
    expect(activity).toMatch(/inspector stays closed until then/)
    expect(activity).toMatch(/\?trace=1/)
  })

  it("approvals queue is decision-first with one primary CTA after selection", () => {
    const src = readFileSync(resolve(webRoot, "app/approvals/page.tsx"), "utf8")
    expect(src).toMatch(/data-review-surface="approvals-queue"/)
    expect(src).toMatch(/data-review-surface="approvals-inspect"/)
    expect(src).toMatch(/data-review-cta="approve"/)
    expect(src).toMatch(/inspector stays closed until then/)
    expect(src).toMatch(/Select to decide/)
    expect(src).toMatch(/ESTIMATED_CONFIDENCE_LABEL/)
    expect(src).not.toMatch(/AI-approved/)
    expect(src).not.toMatch(/hidden lg:block/)
    expect(src).toMatch(/hideActions/)
    expect(src).toMatch(/selectedApproval \? \(/)
    const harness = readFileSync(
      resolve(webRoot, "app/dev/ai-workspace-preview/_components/design-exploration-shell.tsx"),
      "utf8",
    )
    expect(harness).toMatch(/"approvals"/)
    expect(harness).toMatch(/SelectedApprovals/)
  })

  it("learning insights are a list with inspector on selection; memory has no TabsList", () => {
    const stage = readFileSync(
      resolve(webRoot, "components/intelligence/pages/learning-stage.tsx"),
      "utf8",
    )
    expect(stage).toMatch(/LearningInsightsList/)
    expect(stage).not.toMatch(/md:grid-cols-2/)
    expect(stage).not.toMatch(/LearningInsightCard/)

    const list = readFileSync(
      resolve(webRoot, "components/intelligence/learning-insight-card.tsx"),
      "utf8",
    )
    expect(list).toMatch(/data-review-surface="learning-queue"/)
    expect(list).toMatch(/data-review-surface="learning-inspect"/)
    expect(list).toMatch(/inspector stays closed until then/)
    expect(list).toMatch(/data-review-cta="view-on-map"/)
    expect(list).not.toMatch(/from \"@\/components\/ui\/card\"/)

    const memory = readFileSync(resolve(webRoot, "app/intelligence/memory/page.tsx"), "utf8")
    expect(memory).not.toMatch(/TabsList/)
    expect(memory).not.toMatch(/from \"@\/components\/ui\/tabs\"/)
    expect(memory).toMatch(/data-review-surface="memory-queue"/)
    expect(memory).toMatch(/data-review-surface="memory-inspect"/)
    expect(memory).toMatch(/inspector stays closed until then/)
    expect(memory).toMatch(/selectedCandidate \?/)
  })

  it("models catalog and studio are list plus inspector, not card grids", () => {
    const stage = readFileSync(
      resolve(webRoot, "components/intelligence/pages/models-stage.tsx"),
      "utf8",
    )
    expect(stage).toMatch(/BusinessModelsList/)
    expect(stage).not.toMatch(/md:grid-cols-2/)

    const list = readFileSync(
      resolve(webRoot, "components/intelligence/business-model-card.tsx"),
      "utf8",
    )
    expect(list).toMatch(/data-review-surface="models-queue"/)
    expect(list).toMatch(/data-review-surface="models-inspect"/)
    expect(list).toMatch(/inspector stays closed until then/)
    expect(list).toMatch(/data-review-cta="open-model"/)
    expect(list).not.toMatch(/from \"@\/components\/ui\/card\"/)

    const brain = readFileSync(
      resolve(webRoot, "components/gravitre/built-in-models-brain.tsx"),
      "utf8",
    )
    expect(brain).toMatch(/data-review-surface="models-queue"/)
    expect(brain).toMatch(/inspector stays closed until then/)
    expect(brain).not.toMatch(/rounded-2xl/)
    expect(brain).not.toMatch(/LayoutGrid/)
    expect(brain).not.toMatch(/min-h-\[188px\]/)

    const studio = readFileSync(
      resolve(webRoot, "components/intelligence/pages/model-studio-stage.tsx"),
      "utf8",
    )
    expect(studio).toMatch(/data-review-surface="studio-queue"/)
    expect(studio).toMatch(/inspector stays closed until then/)
    expect(studio).not.toMatch(/sm:grid-cols-2 lg:grid-cols-3/)

    const training = readFileSync(resolve(webRoot, "app/training/page.tsx"), "utf8")
    expect(training).not.toMatch(/from-emerald-500 to-teal-500/)
  })

  it("marketplace keeps authorized discovery tiles and treats installed as ops", () => {
    const catalog = readFileSync(resolve(webRoot, "app/marketplace/assets/page.tsx"), "utf8")
    expect(catalog).toMatch(/data-review-surface="marketplace-discovery"/)
    expect(catalog).toMatch(/data-review-surface="marketplace-ops"/)
    expect(catalog).toMatch(/PriceBadge/)
    expect(catalog).toMatch(/discoveryAssets/)
    expect(catalog).not.toMatch(/FilterChip/)

    const installed = readFileSync(resolve(webRoot, "app/marketplace/installed/page.tsx"), "utf8")
    expect(installed).toMatch(/data-review-surface="marketplace-ops"/)
    expect(installed).toMatch(/data-review-surface="marketplace-ops-inspect"/)
    expect(installed).toMatch(/inspector stays closed until then/)
    expect(installed).toMatch(/data-review-cta="manage-install"/)
    expect(installed).not.toMatch(/sm:grid-cols-2/)

    const harness = readFileSync(
      resolve(webRoot, "app/dev/ai-workspace-preview/_components/design-exploration-shell.tsx"),
      "utf8",
    )
    expect(harness).toMatch(/"marketplace"/)
    expect(harness).toMatch(/SelectedMarketplace/)
  })
})
