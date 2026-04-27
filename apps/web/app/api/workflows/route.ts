import { NextResponse } from "next/server"

const workflows = [
  {
    id: "1",
    name: "sync-customers",
    description: "Synchronize customer data from Salesforce",
    status: "active",
    environment: "production",
    lastRun: "2 minutes ago",
    successRate: "98.5%",
    runCount: 1247,
  },
  {
    id: "2",
    name: "etl-main-pipeline",
    description: "Main ETL pipeline for data warehouse",
    status: "active",
    environment: "production",
    lastRun: "5 minutes ago",
    successRate: "99.2%",
    runCount: 856,
  },
  {
    id: "3",
    name: "invoice-processing",
    description: "Process and validate incoming invoices",
    status: "paused",
    environment: "staging",
    lastRun: "1 hour ago",
    successRate: "94.1%",
    runCount: 432,
  },
  {
    id: "4",
    name: "user-onboarding",
    description: "Handle new user registration workflow",
    status: "active",
    environment: "production",
    lastRun: "15 minutes ago",
    successRate: "99.8%",
    runCount: 2103,
  },
  {
    id: "5",
    name: "data-cleanup",
    description: "Scheduled data cleanup and archival",
    status: "draft",
    environment: "staging",
    lastRun: "Never",
    successRate: "-",
    runCount: 0,
  },
  {
    id: "6",
    name: "report-generation",
    description: "Generate and distribute weekly reports",
    status: "active",
    environment: "production",
    lastRun: "3 hours ago",
    successRate: "100%",
    runCount: 52,
  },
]

export async function GET() {
  return NextResponse.json({ workflows })
}
