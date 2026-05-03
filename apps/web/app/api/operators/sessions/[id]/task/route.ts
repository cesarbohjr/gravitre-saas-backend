import { NextRequest, NextResponse } from "next/server"
import { proxyToFastApi } from "@/lib/backend-proxy"
import { getDemoStore } from "@/lib/demo-runtime-store"

interface RouteParams {
  params: Promise<{ id: string }>
}

export async function POST(request: NextRequest, { params }: RouteParams) {
  const { id } = await params
  if (process.env.FASTAPI_BASE_URL?.trim()) {
    const upstream = await proxyToFastApi(request, `/api/sessions/${id}/task`)
    if (upstream.ok || upstream.status < 500) return upstream
  }

  const body = (await request.json().catch(() => ({}))) as { task?: string }
  const task = String(body.task ?? "Investigate issue").trim()
  const session = getDemoStore().sessions.find((item) => item.id === id)
  if (session) {
    session.status = "running"
  }

  return NextResponse.json({
    plan: {
      reasoning: [
        {
          id: "summary",
          type: "summary",
          title: "What Happened",
          content: `Processed request: "${task}". Generated a local fallback analysis because backend orchestration is unavailable.`,
        },
      ],
      steps: [
        {
          step: 1,
          title: "Analyze context",
          description: "Review recent failures and related connectors",
          status: "completed",
        },
        {
          step: 2,
          title: "Draft remediation",
          description: "Suggest low-risk corrective actions",
          status: "current",
        },
      ],
      proposals: [
        {
          id: `proposal-${Date.now()}`,
          title: "Retry workflow with extended timeout",
          description: "Increase timeout and retry the workflow execution once",
          icon: "RefreshCw",
          environment: "production",
          trustBadges: {
            confidenceScore: 78,
            guardrailStatus: "pass",
            tokenCount: 512,
            approvalRequired: true,
          },
        },
      ],
    },
  })
}
