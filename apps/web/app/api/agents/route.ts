import { NextResponse } from "next/server"

const agents = [
  {
    id: "agent-001",
    name: "Marketing Operator",
    description: "Manages marketing campaigns, analyzes performance, and suggests optimizations",
    status: "active",
    activeVersion: "v3",
    environment: "production",
    workflowCount: 4,
    capabilities: ["Analyze campaign data", "Generate reports", "Suggest improvements"],
    connectedSystems: ["HubSpot", "Google Analytics"],
    avatarColor: "bg-emerald-500",
  },
  {
    id: "agent-002",
    name: "Sales Assistant",
    description: "Syncs customer data, tracks deals, and provides sales insights",
    status: "active",
    activeVersion: "v2",
    environment: "production",
    workflowCount: 6,
    capabilities: ["Sync contacts", "Update deal stages", "Generate forecasts"],
    connectedSystems: ["Salesforce", "Slack"],
    avatarColor: "bg-blue-500",
  },
  {
    id: "agent-003",
    name: "Data Quality Agent",
    description: "Monitors data integrity, detects anomalies, and alerts on issues",
    status: "draft",
    activeVersion: null,
    environment: "staging",
    workflowCount: 0,
    capabilities: ["Validate records", "Detect duplicates", "Alert on anomalies"],
    connectedSystems: ["PostgreSQL", "Snowflake"],
    avatarColor: "bg-amber-500",
  },
  {
    id: "agent-004",
    name: "Finance Reporter",
    description: "Generates weekly financial reports and budget summaries",
    status: "active",
    activeVersion: "v1",
    environment: "production",
    workflowCount: 2,
    capabilities: ["Generate reports", "Calculate metrics", "Export to Excel"],
    connectedSystems: ["QuickBooks", "Microsoft 365"],
    avatarColor: "bg-violet-500",
  },
  {
    id: "agent-005",
    name: "Support Coordinator",
    description: "Routes tickets, escalates issues, and tracks resolution times",
    status: "error",
    activeVersion: "v4",
    environment: "staging",
    workflowCount: 3,
    capabilities: ["Route tickets", "Escalate issues", "Track SLAs"],
    connectedSystems: ["Zendesk", "Slack"],
    avatarColor: "bg-rose-500",
  },
]

export async function GET() {
  return NextResponse.json({ agents })
}
