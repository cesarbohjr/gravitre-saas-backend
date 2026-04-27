import { NextResponse } from "next/server"

const runs = [
  {
    id: "run-001",
    workflowId: "1",
    workflowName: "sync-customers",
    status: "running",
    approvalStatus: "not_required",
    environment: "production",
    startedAt: "2 minutes ago",
    duration: "1m 23s",
    triggeredBy: "schedule",
  },
  {
    id: "run-002",
    workflowId: "1",
    workflowName: "sync-customers",
    status: "failed",
    approvalStatus: "not_required",
    environment: "production",
    startedAt: "15 minutes ago",
    duration: "45s",
    triggeredBy: "manual",
  },
  {
    id: "run-003",
    workflowId: "2",
    workflowName: "etl-main-pipeline",
    status: "pending",
    approvalStatus: "pending",
    environment: "production",
    startedAt: "20 minutes ago",
    duration: "-",
    triggeredBy: "api",
  },
  {
    id: "run-004",
    workflowId: "3",
    workflowName: "invoice-processing",
    status: "completed",
    approvalStatus: "approved",
    environment: "staging",
    startedAt: "1 hour ago",
    duration: "3m 12s",
    triggeredBy: "schedule",
  },
  {
    id: "run-005",
    workflowId: "4",
    workflowName: "user-onboarding",
    status: "completed",
    approvalStatus: "not_required",
    environment: "production",
    startedAt: "2 hours ago",
    duration: "28s",
    triggeredBy: "webhook",
  },
  {
    id: "run-006",
    workflowId: "2",
    workflowName: "etl-main-pipeline",
    status: "completed",
    approvalStatus: "not_required",
    environment: "production",
    startedAt: "3 hours ago",
    duration: "5m 45s",
    triggeredBy: "schedule",
  },
]

export async function GET() {
  return NextResponse.json({ runs })
}
