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
    const src = readFileSync(resolve(webRoot, "app/(app)/agents/page.tsx"), "utf8")
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
    expect(graph).toMatch(/sweep=\{active\}/)
    const tabs = readFileSync(resolve(webRoot, "components/agents/agents-hub-tabs.tsx"), "utf8")
    expect(tabs).not.toMatch(/from \"@\/components\/gravitre\/hub-tabs\"/)
    expect(tabs).toMatch(/aria-label="Agents hub"/)
  })

  it("connectors default to discovery then a compact management list", () => {
    const src = readFileSync(resolve(webRoot, "app/(app)/connectors/page.tsx"), "utf8")
    expect(src).toMatch(/useState<"topology" \| "grid">\("grid"\)/)
    expect(src).toMatch(/<ConnectorOperatingRow/)
    expect(src).toMatch(/\{selectedConnector \? \(\s*<ResponsiveConnectorInspector/)
    expect(src).toMatch(/data-review-surface="connectors-management"/)
    expect(src).not.toMatch(/requestsToday|dataFlowRate|usedByWorkflows|triggeredByAgents/)
    expect(src).not.toMatch(/ConnectorsAtmosphere/)
    const strip = readFileSync(
      resolve(webRoot, "components/connectors/available-connectors-strip.tsx"),
      "utf8",
    )
    expect(strip).toMatch(/data-review-surface="connectors-discovery"/)
    expect(strip).toMatch(/Discover systems/)
    expect(strip).not.toMatch(/Available\s*</)
  })

  it("sources retain the desktop table with compact disclosure below tablet cutover", () => {
    const src = readFileSync(resolve(webRoot, "app/(app)/sources/page.tsx"), "utf8")
    expect(src).toMatch(/<table/)
    expect(src).not.toMatch(/xl:grid-cols-4/)
    expect(src).toMatch(/Last sync/)
    expect(src).toMatch(/data-testid="sources-compact-view"/)
    expect(src).toMatch(/useIsMobile\(1024\)/)
    expect(src).toMatch(/data-source-ingest="syncing"/)
    expect(src).toMatch(/source\.status === "syncing"/)
  })

  it("relationships map is not wrapped in a permanent evidence dashboard", () => {
    const src = readFileSync(resolve(webRoot, "app/(app)/intelligence/page.tsx"), "utf8")
    // The overview is the v2 design: one core view (stats, flow map, activity, learnings), no evidence dashboard below it.
    expect(src).toMatch(/<IntelligenceBrain/)
    expect(src).not.toMatch(/Attention, learnings, and impact/)
    expect(src).not.toMatch(/<details/)
    // Hub tabs carry navigation; the overview no longer repeats them as link groups.
    expect(src).not.toMatch(/ADVANCED_LINK_GROUPS/)
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

  it("impact reads spend to value, then by agent, then first result and latest outcome; period toggle lives in the header", () => {
    const src = readFileSync(
      resolve(webRoot, "components/intelligence/pages/performance-stage.tsx"),
      "utf8",
    )
    const legend = src.indexOf("<CertaintyLegend")
    const flow = src.indexOf("<SpendToValueFlow")
    const agents = src.indexOf("<ByAgentTable")
    const checklist = src.indexOf("<FirstResultChecklist")
    const outcome = src.indexOf("<LatestOutcomeCard")
    expect(legend).toBeGreaterThan(0)
    expect(flow).toBeGreaterThan(legend)
    expect(agents).toBeGreaterThan(flow)
    expect(checklist).toBeGreaterThan(agents)
    expect(outcome).toBeGreaterThan(checklist)
    // No in-stage view switcher: the only segmented control is the 7/30/90 day period in the header.
    expect(src).not.toMatch(/SegmentedControl/)
    expect(src).not.toMatch(/AgentContributionCard/)
    const page = readFileSync(resolve(webRoot, "app/(app)/intelligence/performance/page.tsx"), "utf8")
    expect(page).toMatch(/ariaLabel="Period"/)
    expect(page).toMatch(/getAgentRoi\(\{ periodDays: period \}\)/)
    const flowSrc = readFileSync(
      resolve(webRoot, "components/intelligence/outcome-attribution-flow.tsx"),
      "utf8",
    )
    expect(flowSrc).toMatch(/Contributing stages/)
    expect(flowSrc).toMatch(/useState<string \| null>\(null\)/)
    expect(flowSrc).toMatch(/\{selected \?/)
  })

  it("settings preference chrome uses rows, not elevated cards", () => {
    const page = readFileSync(resolve(webRoot, "app/(app)/settings/page.tsx"), "utf8")
    expect(page).toMatch(/from \"@\/components\/settings\/organization-settings\"/)
    expect(page).toMatch(/from \"@\/components\/settings\/notification-settings\"/)
    expect(page).toMatch(/from \"@\/components\/settings\/security-settings\"/)
    expect(page).toMatch(/from \"@\/components\/settings\/team-settings\"/)
    expect(page).toMatch(/from \"@\/components\/settings\/api-keys-settings\"/)
    expect(page).toMatch(/from \"@\/components\/settings\/webhooks-settings\"/)
    expect(page).toMatch(/from \"@\/components\/settings\/ai-models-settings\"/)
    expect(page).toMatch(/<OrganizationSettings/)
    expect(page).toMatch(/<NotificationSettings/)
    expect(page).toMatch(/<SecuritySettings/)
    expect(page).toMatch(/<TeamSettings/)
    expect(page).toMatch(/<ApiKeysSettings/)
    expect(page).toMatch(/<WebhooksSettings/)
    expect(page).toMatch(/<AIModelsSettings/)
    expect(page).toMatch(/border-b border-divide py-3/)
    expect(page).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    expect(page).not.toMatch(/AI Operator/)
    expect(page).not.toMatch(/ModelSelector/)

    const notifications = readFileSync(
      resolve(webRoot, "components/settings/notification-settings.tsx"),
      "utf8",
    )
    expect(notifications).toMatch(/aria-label="Email notifications"/)
    expect(notifications).toMatch(/aria-label="Slack notifications"/)
    expect(notifications).toMatch(/border-b border-divide py-3/)
    expect(notifications).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)

    const security = readFileSync(
      resolve(webRoot, "components/settings/security-settings.tsx"),
      "utf8",
    )
    const ssoIdx = security.indexOf("Single sign-on")
    expect(ssoIdx).toBeGreaterThan(0)
    const ssoWindow = security.slice(Math.max(0, ssoIdx - 450), ssoIdx + 1800)
    expect(ssoWindow).toMatch(/border-b border-divide py-3/)
    expect(ssoWindow).toMatch(/ssoConfig\?\.is_enabled \? "Disable" : "Enable"/)
    expect(ssoWindow).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    expect(security).toMatch(/Organization-wide 2FA enforcement is not available/)
    expect(security).toMatch(/IP restriction is not available/)

    const models = readFileSync(
      resolve(webRoot, "components/settings/ai-models-settings.tsx"),
      "utf8",
    )
    expect(models).toMatch(/<MemoryEntityEmbeddingsSettings/)
    expect(models).toMatch(/no organization API for workspace default models/)
    expect(models).not.toMatch(/AI Operator/)
    expect(models).not.toMatch(/ModelSelector/)
    expect(models).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
  })

  it("settings organizations are a list with inspector on selection", () => {
    const src = readFileSync(resolve(webRoot, "app/(app)/settings/organizations/page.tsx"), "utf8")
    expect(src).toMatch(/data-review-surface="settings-orgs-queue"/)
    expect(src).toMatch(/data-review-surface="settings-orgs-inspect"/)
    expect(src).not.toMatch(/requestsToday|dataFlowRate|usedByWorkflows|triggeredByAgents/)
    expect(src).toMatch(/data-review-cta="switch-org"/)
    expect(src).not.toMatch(/from \"@\/components\/ui\/card\"/)
    expect(src).not.toMatch(/org\.plan \?\? \"Free\"/)
    const prefs = readFileSync(resolve(webRoot, "app/(app)/settings/page.tsx"), "utf8")
    expect(prefs).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    const harness = readFileSync(
      resolve(webRoot, "app/dev/ai-workspace-preview/_components/design-exploration-shell.tsx"),
      "utf8",
    )
    expect(harness).toMatch(/\"settings\"/)
    expect(harness).toMatch(/SelectedSettings/)
    const enterprise = readFileSync(resolve(webRoot, "app/(app)/settings/enterprise/page.tsx"), "utf8")
    expect(enterprise).toMatch(/aria-label="Enterprise settings"/)
    expect(enterprise).not.toMatch(/shadow-\[var\(--np-shadow\)\]/)
    const federation = readFileSync(resolve(webRoot, "app/(app)/settings/federation/page.tsx"), "utf8")
    expect(federation).not.toMatch(/TabsList/)
    expect(federation).toMatch(/aria-label="Federation activity"/)
  })

  it("workflow builder states intent then canvas and inspects config on the node", () => {
    const src = readFileSync(resolve(webRoot, "app/(app)/workflows/[id]/builder/page.tsx"), "utf8")
    expect(src).toMatch(/data-review-surface="workflow-intent"/)
    expect(src).toMatch(/traceOverlay/)
    expect(src).toMatch(/Inspect ·/)
    expect(src).toMatch(/not behind Ask/)
    expect(src).toMatch(/isActive && !isDimmedPath/)
  })

  it("runs lead with outcome evidence and keep TRACE as a drill-down", () => {
    const run = readFileSync(resolve(webRoot, "app/(app)/runs/[id]/page.tsx"), "utf8")
    const outcome = run.indexOf('data-review-surface="run-outcome"')
    const trace = run.indexOf('data-review-surface="run-trace"')
    expect(outcome).toBeGreaterThan(0)
    expect(trace).toBeGreaterThan(outcome)
    expect(run).toMatch(/eyebrow="Outcome"/)
    expect(run).toMatch(/Drill-down into this run/)
    const activity = readFileSync(resolve(webRoot, "app/(app)/activity/page.tsx"), "utf8")
    expect(activity).not.toMatch(/selectedOutcomeExplicit \?\? outcomes\[0\]/)
    // v4 design: desktop opens on the top exception; phones keep the inspector closed until a tap.
    expect(activity).toMatch(/inspector stays closed until then/)
    expect(activity).toMatch(/\?trace=1/)
  })

  it("approvals queue is decision-first with one primary CTA after selection", () => {
    const src = readFileSync(resolve(webRoot, "app/(app)/approvals/page.tsx"), "utf8")
    expect(src).toMatch(/data-review-surface="approvals-queue"/)
    expect(src).toMatch(/data-review-surface="approvals-inspect"/)
    expect(src).toMatch(/data-review-cta="approve"/)
    expect(src).not.toMatch(/requestsToday|dataFlowRate|usedByWorkflows|triggeredByAgents/)
    // Workspace redesign v1: stat tabs (Waiting on you / Past SLA / Approved / Rejected)
    // replace the PhaseBand, and the detail pane leads with Approve / Reject plus a
    // reason-required reject dialog. The heuristic suggestion card is gone because
    // /api/approvals never sends one.
    expect(src).toMatch(/Waiting on you/)
    expect(src).toMatch(/Past SLA/)
    expect(src).toMatch(/Reject with a reason/)
    expect(src).toMatch(/approvalsApi\.reject\(a\.id, \{ comment: reason \}\)/)
    expect(src).not.toMatch(/AI-approved/)
    expect(src).not.toMatch(/hidden lg:block/)
    expect(src).toMatch(/data-testid="approval-mobile-actions"/)
    expect(src).toMatch(/selected \? \(/)
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

    const memory = readFileSync(resolve(webRoot, "components/intelligence/org-memory-section.tsx"), "utf8")
    expect(memory).not.toMatch(/TabsList/)
    expect(memory).not.toMatch(/from \"@\/components\/ui\/tabs\"/)
    expect(memory).toMatch(/data-review-surface="memory-queue"/)
    expect(memory).toMatch(/data-review-surface="memory-inspect"/)
    expect(memory).toMatch(/inspector stays closed until then/)
    expect(memory).toMatch(/selectedCandidate \?/)
  })

  it("models v2 renders real registry cards with lineage, and studio stays list plus inspector", () => {
    const stage = readFileSync(
      resolve(webRoot, "components/intelligence/pages/models-stage.tsx"),
      "utf8",
    )
    // Models v2 design: stat strip, filter chips, "Where models are used" and model cards.
    expect(stage).toMatch(/BusinessModelCard/)
    expect(stage).toMatch(/ModelUsageTopology/)
    expect(stage).toMatch(/data-review-surface="models-cards"/)
    expect(stage).toMatch(/aria-pressed=\{active\}/)
    expect(stage).toMatch(/Show technical details/)

    const list = readFileSync(
      resolve(webRoot, "components/intelligence/business-model-card.tsx"),
      "utf8",
    )
    expect(list).toMatch(/data-review-surface="models-card"/)
    expect(list).toMatch(/data-review-cta="open-model"/)
    expect(list).toMatch(/Path to production/)
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

    const training = readFileSync(resolve(webRoot, "app/(app)/training/page.tsx"), "utf8")
    expect(training).not.toMatch(/from-emerald-500 to-teal-500/)
  })

  it("marketplace keeps authorized discovery tiles and treats installed as ops", () => {
    const catalog = readFileSync(resolve(webRoot, "app/(app)/marketplace/assets/page.tsx"), "utf8")
    expect(catalog).toMatch(/data-review-surface="marketplace-discovery"/)
    expect(catalog).toMatch(/data-review-surface="marketplace-ops"/)
    expect(catalog).toMatch(/PriceBadge/)
    expect(catalog).toMatch(/discoveryAssets/)
    expect(catalog).toMatch(/More about this pack/)
    expect(catalog).not.toMatch(/2xl:grid-cols-4/)
    expect(catalog).not.toMatch(/FilterChip/)

    const installed = readFileSync(resolve(webRoot, "app/(app)/marketplace/installed/page.tsx"), "utf8")
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
