import type { SupabaseClient } from "@supabase/supabase-js"

const PRIMARY_DEMO_ORG_ID = "00000000-0000-0000-0000-000000000001"
const SECONDARY_DEMO_ORG_ID = "11111111-1111-4111-8111-111111111111"

const DEMO_ORGS: Record<string, { name: string; slug: string }> = {
  [PRIMARY_DEMO_ORG_ID]: { name: "Acme Corp", slug: "acme-corp" },
  [SECONDARY_DEMO_ORG_ID]: { name: "Gravitre Labs", slug: "gravitre-labs" },
}

function createDemoRows(orgId: string) {
  const suffix = orgId === SECONDARY_DEMO_ORG_ID ? "b" : "a"
  const orgSuffix = suffix === "a" ? "1" : "2"
  return {
    users: [
      {
        id: `20000000-0000-4000-8000-00000000000${orgSuffix}`,
        org_id: orgId,
        auth_user_id: null,
        email: suffix === "a" ? "jordan.ortiz@acmecorp.com" : "riley.chen@gravitrelabs.com",
        full_name: suffix === "a" ? "Jordan Ortiz" : "Riley Chen",
        role: "owner",
        status: "active",
      },
    ],
    agents: [
      {
        id: `30000000-0000-4000-8000-00000000000${suffix === "a" ? "1" : "7"}`,
        org_id: orgId,
        name: "Revenue Ops Agent",
        purpose: "Optimizes lead routing and opportunity progression.",
        role: "Revenue Operations",
        department: "Operations",
        model: "gpt-4.1",
        personality: {
          color: "blue",
          gradient: "from-blue-500 to-indigo-500",
          glow: "shadow-blue-500/30",
        },
        stats: {
          tasksToday: 37,
          successRate: 96,
          avgResponseTime: "1m 20s",
          workflowsUsing: 8,
        },
        capabilities: ["lead-scoring", "routing"],
        systems: ["hubspot", "salesforce", "slack"],
        guardrails: ["approval-for-high-value-actions"],
        config: { type: "ops" },
        status: "active",
        last_action: "Optimized lead assignment for enterprise pipeline",
        last_action_time: new Date(Date.now() - 1000 * 60 * 8).toISOString(),
      },
      {
        id: `30000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        org_id: orgId,
        name: "Customer Support Agent",
        purpose: "Triages escalations and drafts safe customer responses.",
        role: "Support Operations",
        department: "Support",
        model: "claude-3.5-sonnet",
        personality: {
          color: "violet",
          gradient: "from-violet-500 to-fuchsia-500",
          glow: "shadow-violet-500/30",
        },
        stats: {
          tasksToday: 52,
          successRate: 98,
          avgResponseTime: "45s",
          workflowsUsing: 5,
        },
        capabilities: ["ticket-triage", "response-drafting"],
        systems: ["zendesk", "slack", "gmail"],
        guardrails: ["require-human-approval-for-vip"],
        config: { type: "support" },
        status: "active",
        last_action: "Queued VIP escalation draft for human approval",
        last_action_time: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
      },
    ],
    workflows: [
      {
        id: `50000000-0000-4000-8000-00000000000${suffix === "a" ? "1" : "7"}`,
        org_id: orgId,
        name: "Lead Routing Automation",
        description: "Routes inbound leads to the best-fit owner in real time.",
        status: "active",
        environment: "production",
        nodes: [{ id: "source", type: "source", name: "Inbound Leads" }],
        edges: [],
        config: { version: 1 },
      },
      {
        id: `50000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        org_id: orgId,
        name: "Customer Escalation Triage",
        description: "Prioritizes and routes high-impact support cases.",
        status: "active",
        environment: "production",
        nodes: [{ id: "source", type: "source", name: "Support Queue" }],
        edges: [],
        config: { version: 1 },
      },
    ],
    runs: [
      {
        id: `60000000-0000-4000-8000-00000000000${suffix === "a" ? "1" : "7"}`,
        org_id: orgId,
        workflow_id: `50000000-0000-4000-8000-00000000000${suffix === "a" ? "1" : "7"}`,
        workflow_name: "Lead Routing Automation",
        status: "completed",
        trigger: "schedule",
        approval_status: "not_required",
        started_at: new Date(Date.now() - 1000 * 60 * 25).toISOString(),
        completed_at: new Date(Date.now() - 1000 * 60 * 22).toISOString(),
        duration_ms: 180000,
        metadata: { recordsProcessed: 1240 },
      },
      {
        id: `60000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        org_id: orgId,
        workflow_id: `50000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        workflow_name: "Customer Escalation Triage",
        status: "running",
        trigger: "manual",
        approval_status: "pending",
        started_at: new Date(Date.now() - 1000 * 60 * 7).toISOString(),
        completed_at: null,
        duration_ms: null,
        metadata: { recordsProcessed: 312 },
      },
      {
        id: `60000000-0000-4000-8000-00000000000${suffix === "a" ? "3" : "9"}`,
        org_id: orgId,
        workflow_id: `50000000-0000-4000-8000-00000000000${suffix === "a" ? "1" : "7"}`,
        workflow_name: "Lead Routing Automation",
        status: "failed",
        trigger: "schedule",
        approval_status: "pending",
        started_at: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
        completed_at: new Date(Date.now() - 1000 * 60 * 86).toISOString(),
        duration_ms: 240000,
        error_message: "Connector timeout while syncing CRM records.",
        metadata: { recordsProcessed: 480 },
      },
      {
        id: `60000000-0000-4000-8000-0000000000${suffix === "a" ? "10" : "11"}`,
        org_id: orgId,
        workflow_id: `50000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        workflow_name: "Customer Escalation Triage",
        status: "pending",
        trigger: "schedule",
        approval_status: "pending",
        started_at: null,
        completed_at: null,
        duration_ms: null,
        metadata: { recordsProcessed: 0 },
      },
    ],
    approvals: [
      {
        id: `70000000-0000-4000-8000-00000000000${suffix === "a" ? "1" : "7"}`,
        org_id: orgId,
        run_id: `60000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        title: "Approve escalation response draft",
        description: "Customer-facing response for a billing escalation needs review.",
        type: "message",
        priority: "high",
        status: "pending",
        requested_by: "Customer Support Agent",
        requested_at: new Date(Date.now() - 1000 * 60 * 6).toISOString(),
        context: { channel: "email", customerTier: "enterprise" },
      },
      {
        id: `70000000-0000-4000-8000-00000000000${suffix === "a" ? "2" : "8"}`,
        org_id: orgId,
        run_id: `60000000-0000-4000-8000-00000000000${suffix === "a" ? "3" : "9"}`,
        title: "Approve retry with expanded timeout",
        description: "Automation retry requires confirmation due to repeated connector failures.",
        type: "workflow",
        priority: "medium",
        status: "pending",
        requested_by: "Revenue Ops Agent",
        requested_at: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
        context: { guardrail: "high_impact_retry" },
      },
    ],
    connectedSystems: [
      {
        id: `40000000-0000-4000-8000-00000000000${orgSuffix}`,
        org_id: orgId,
        system_key: "hubspot",
        name: "HubSpot CRM",
        type: "crm",
        status: "connected",
        config: { vendor: "hubspot" },
      },
      {
        id: `40000000-0000-4000-8000-0000000000${suffix === "a" ? "12" : "13"}`,
        org_id: orgId,
        system_key: "slack",
        name: "Slack",
        type: "communication",
        status: "connected",
        config: { vendor: "slack" },
      },
    ],
    connectors: [
      {
        id: `a1000000-0000-4000-8000-00000000000${orgSuffix}`,
        org_id: orgId,
        name: "salesforce-api",
        type: "Salesforce",
        status: "connected",
        environment: "production",
        last_sync: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
        health: 98,
        description: "Salesforce REST API connector",
        data_flow_rate: "2.4 MB/s",
        requests_today: 12847,
        latency: 45,
        category: "CRM / Marketing",
        auth_type: "oauth",
        used_by_workflows: 8,
        triggered_by_agents: 3,
        config: { syncInterval: "5m" },
      },
      {
        id: `a1000000-0000-4000-8000-0000000000${suffix === "a" ? "12" : "13"}`,
        org_id: orgId,
        name: "slack-notifications",
        type: "Slack",
        status: "syncing",
        environment: "production",
        last_sync: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        health: 95,
        description: "Workspace notifications",
        data_flow_rate: "0.3 MB/s",
        requests_today: 3421,
        latency: 28,
        category: "Communication",
        auth_type: "oauth",
        used_by_workflows: 12,
        triggered_by_agents: 6,
        config: { syncInterval: "10m" },
      },
      {
        id: `a1000000-0000-4000-8000-0000000000${suffix === "a" ? "14" : "15"}`,
        org_id: orgId,
        name: "stripe-payments",
        type: "Stripe",
        status: "connected",
        environment: "production",
        last_sync: new Date(Date.now() - 1000 * 60 * 4).toISOString(),
        health: 100,
        description: "Payment processing",
        data_flow_rate: "1.1 MB/s",
        requests_today: 8234,
        latency: 32,
        category: "Payments / Finance",
        auth_type: "apiKey",
        used_by_workflows: 5,
        triggered_by_agents: 2,
        config: { syncInterval: "1m" },
      },
    ],
    apiKeys: [
      {
        id: `80000000-0000-4000-8000-00000000000${orgSuffix}`,
        org_id: orgId,
        name: "Production Integration Key",
        key_prefix: suffix === "a" ? "gva_live_" : "gvl_live_",
        key_hash: suffix === "a" ? "demo-hash-acme-live" : "demo-hash-labs-live",
        status: "active",
      },
    ],
    webhooks: [
      {
        id: `90000000-0000-4000-8000-00000000000${orgSuffix}`,
        org_id: orgId,
        url: suffix === "a" ? "https://hooks.acmecorp.com/gravitre/events" : "https://hooks.gravitrelabs.com/ops/events",
        events: ["run.completed", "approval.requested"],
        status: "active",
      },
    ],
  }
}

export function getDemoRowsForOrg(orgId: string) {
  const orgTemplate = DEMO_ORGS[orgId]
  if (!orgTemplate) return null
  return {
    organization: {
      id: orgId,
      name: orgTemplate.name,
      slug: orgTemplate.slug,
      status: "active",
      settings: { environment: "production" },
    },
    ...createDemoRows(orgId),
  }
}

export async function ensureDemoDataForOrg(supabase: SupabaseClient, orgId: string) {
  const orgTemplate = DEMO_ORGS[orgId]
  if (!orgTemplate) return

  try {
    const nowIso = new Date().toISOString()
    await supabase.from("organizations").upsert(
      {
        id: orgId,
        name: orgTemplate.name,
        slug: orgTemplate.slug,
        status: "active",
        settings: { environment: "production" },
        created_at: nowIso,
        updated_at: nowIso,
      },
      { onConflict: "id" }
    )

    const rows = createDemoRows(orgId)
    await supabase.from("users").upsert(rows.users, { onConflict: "id" })
    await supabase.from("agents").upsert(rows.agents, { onConflict: "id" })
    await supabase.from("workflows").upsert(rows.workflows, { onConflict: "id" })
    await supabase.from("runs").upsert(rows.runs, { onConflict: "id" })
    await supabase.from("approvals").upsert(rows.approvals, { onConflict: "id" })
    await supabase.from("connected_systems").upsert(rows.connectedSystems, { onConflict: "id" })
    const { error: connectorsError } = await supabase.from("connectors").upsert(rows.connectors, { onConflict: "id" })
    if (connectorsError) {
      // Connectors table may not exist yet in older environments.
      console.warn("Skipping connectors demo bootstrap", { orgId, message: connectorsError.message })
    }
    await supabase.from("api_keys").upsert(rows.apiKeys, { onConflict: "id" })
    await supabase.from("webhooks").upsert(rows.webhooks, { onConflict: "id" })
    await supabase.from("model_settings").upsert(
      {
        org_id: orgId,
        workspace_model: "auto",
        operator_model: "auto",
        agent_default_model: "balanced",
        fallback_model: "fast",
        allow_overrides: true,
        show_model_in_logs: true,
      },
      { onConflict: "org_id" }
    )
  } catch (error) {
    console.error("Failed to auto-bootstrap demo data", { orgId, error })
  }
}
