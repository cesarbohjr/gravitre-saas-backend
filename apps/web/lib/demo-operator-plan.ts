type DemoPlanPayload = {
  plan: {
    reasoning: Array<{
      id: string
      type: string
      title: string
      content: string
    }>
    steps: Array<{
      step: number
      title: string
      description: string
      status: string
    }>
    proposals: Array<{
      id: string
      title: string
      description: string
      icon: string
      environment: string
      trustBadges: {
        confidenceScore: number
        guardrailStatus: string
        tokenCount: number
        approvalRequired: boolean
      }
    }>
  }
}

export function buildDemoOperatorPlan(task: string): DemoPlanPayload {
  return {
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
  }
}
