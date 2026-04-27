import { NextResponse } from "next/server"

export async function GET() {
  // Generate mock time series data for the last 24 hours
  const now = new Date()
  const runVolume = []
  const latencyDistribution = []

  for (let i = 23; i >= 0; i--) {
    const timestamp = new Date(now.getTime() - i * 60 * 60 * 1000)
    const hour = timestamp.getHours()
    
    // Simulate higher activity during business hours
    const baseRuns = hour >= 9 && hour <= 17 ? 80 : 30
    const runs = Math.floor(baseRuns + Math.random() * 80)
    
    runVolume.push({
      timestamp: timestamp.toISOString(),
      hour: `${hour}:00`,
      completed: Math.floor(runs * 0.85),
      failed: Math.floor(runs * 0.05),
      pending: Math.floor(runs * 0.10),
      total: runs,
    })

    // Latency data with multiple series
    latencyDistribution.push({
      timestamp: timestamp.toISOString(),
      hour: `${hour}:00`,
      p50: Math.floor(80 + Math.random() * 40),
      p90: Math.floor(200 + Math.random() * 100),
      p99: Math.floor(500 + Math.random() * 300),
    })
  }

  return NextResponse.json({
    runVolume,
    latencyDistribution,
  })
}
