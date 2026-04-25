import { NextResponse } from "next/server"

const approvals = [
  {
    id: "apr-001",
    title: "Retry failed sync-customers workflow",
    description: "Request to retry the failed workflow run that encountered a connection timeout",
    type: "workflow",
    environment: "production",
    requestedBy: "AI Operator",
    requestedAt: "5 minutes ago",
    priority: "high",
    status: "pending",
    gate: "Approval gate",
    context: {
      entity: "sync-customers-1234",
      action: "Retry workflow execution",
    },
  },
  {
    id: "apr-002",
    title: "Update Salesforce connector credentials",
    description: "OAuth token refresh required due to security policy rotation",
    type: "connector",
    environment: "production",
    requestedBy: "System",
    requestedAt: "15 minutes ago",
    priority: "high",
    status: "pending",
    gate: "Approval gate",
    context: {
      entity: "salesforce-api",
      action: "Update OAuth credentials",
    },
  },
  {
    id: "apr-003",
    title: "Enable new workflow in production",
    description: "Promote invoice-processing workflow from staging to production",
    type: "workflow",
    environment: "production",
    requestedBy: "john.doe@company.com",
    requestedAt: "1 hour ago",
    priority: "medium",
    status: "pending",
    gate: "Approval gate",
    context: {
      entity: "invoice-processing",
      action: "Deploy to production",
    },
  },
  {
    id: "apr-004",
    title: "Grant admin access for new team member",
    description: "Request to add Sarah Chen as an admin user",
    type: "access",
    environment: "production",
    requestedBy: "mike.johnson@company.com",
    requestedAt: "2 hours ago",
    priority: "medium",
    status: "pending",
    gate: "Approval gate",
    context: {
      entity: "sarah.chen@company.com",
      action: "Grant admin role",
    },
  },
  {
    id: "apr-005",
    title: "Modify data retention policy",
    description: "Change retention period from 90 days to 180 days",
    type: "config",
    environment: "staging",
    requestedBy: "compliance@company.com",
    requestedAt: "3 hours ago",
    priority: "low",
    status: "pending",
    gate: "Approval gate",
    context: {
      entity: "data-retention-policy",
      action: "Update retention period",
    },
  },
]

export async function GET() {
  return NextResponse.json({ approvals })
}
