import { NextResponse } from "next/server"

export async function GET() {
  // Mock metrics overview data
  const overview = {
    totalRuns: 1247,
    totalRunsChange: 12,
    successRate: 98.7,
    successRateChange: 0.5,
    recordsProcessed: "1.8M",
    recordsProcessedChange: 24,
    avgLatency: 142,
    avgLatencyChange: -8,
    activeConnectors: 9,
    totalConnectors: 12,
  }

  return NextResponse.json(overview)
}
