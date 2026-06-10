import type { LucideIcon } from "lucide-react"
import {
  Megaphone,
  TrendingUp,
  PieChart,
} from "lucide-react"
import { apiFetch } from "@/lib/fetcher"
import type { AgentJob, JobStatus } from "@/hooks/use-async-job"

export interface DemoAssignment {
  id: string
  title: string
  brief: string
  agent: { name: string; role: string; gradient: string; icon: LucideIcon }
  status: "running" | "completed" | "pending" | "failed" | "needs_approval"
  progress: number
  steps: { name: string; status: "done" | "running" | "pending" }[]
  createdAt: string
  completedAt?: string
  outputTypes: string[]
  destination: string
  confidence?: number
}

export const DEMO_ASSIGNMENTS: DemoAssignment[] = [
  {
    id: "assign-001",
    title: "Q3 Healthcare Campaign",
    brief: "Create multi-channel campaign targeting healthcare decision makers",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "running",
    progress: 67,
    steps: [
      { name: "Research", status: "done" },
      { name: "Strategy", status: "done" },
      { name: "Content", status: "running" },
      { name: "Review", status: "pending" },
    ],
    createdAt: "2 hours ago",
    outputTypes: ["Emails", "Social Posts", "Segments"],
    destination: "HubSpot + Outlook",
  },
  {
    id: "assign-002",
    title: "Weekly Performance Report",
    brief: "Generate comprehensive weekly marketing performance analysis",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "needs_approval",
    progress: 100,
    steps: [
      { name: "Data Pull", status: "done" },
      { name: "Analysis", status: "done" },
      { name: "Report", status: "done" },
      { name: "Approval", status: "running" },
    ],
    createdAt: "5 hours ago",
    completedAt: "4 hours ago",
    outputTypes: ["Report"],
    destination: "Slack",
    confidence: 94,
  },
  {
    id: "assign-003",
    title: "Lead Scoring Analysis",
    brief: "Analyze and score all leads from Q2 campaign activities",
    agent: { name: "Nexus", role: "Sales Assistant", gradient: "from-blue-500 to-indigo-500", icon: TrendingUp },
    status: "completed",
    progress: 100,
    steps: [
      { name: "Import", status: "done" },
      { name: "Score", status: "done" },
      { name: "Segment", status: "done" },
      { name: "Export", status: "done" },
    ],
    createdAt: "1 day ago",
    completedAt: "1 day ago",
    outputTypes: ["Report", "Segments"],
    destination: "Salesforce",
    confidence: 98,
  },
  {
    id: "assign-004",
    title: "Email Sequence - Re-engagement",
    brief: "Design 5-email re-engagement sequence for dormant leads",
    agent: { name: "Atlas", role: "Marketing Agent", gradient: "from-emerald-500 to-teal-500", icon: Megaphone },
    status: "pending",
    progress: 0,
    steps: [
      { name: "Research", status: "pending" },
      { name: "Draft", status: "pending" },
      { name: "Review", status: "pending" },
      { name: "Publish", status: "pending" },
    ],
    createdAt: "Just now",
    outputTypes: ["Emails"],
    destination: "HubSpot",
  },
  {
    id: "assign-005",
    title: "Competitor Analysis Report",
    brief: "Deep dive analysis of top 5 competitors market positioning",
    agent: { name: "Oracle", role: "Finance Reporter", gradient: "from-violet-500 to-purple-500", icon: PieChart },
    status: "failed",
    progress: 45,
    steps: [
      { name: "Research", status: "done" },
      { name: "Analysis", status: "done" },
      { name: "Report", status: "pending" },
      { name: "Export", status: "pending" },
    ],
    createdAt: "2 days ago",
    outputTypes: ["Report"],
    destination: "Export",
  },
]

export function getDemoAssignment(id: string): DemoAssignment | undefined {
  return DEMO_ASSIGNMENTS.find((item) => item.id === id)
}

function mapDemoStatus(status: DemoAssignment["status"]): JobStatus {
  if (status === "running") return "running"
  if (status === "completed") return "completed"
  if (status === "failed") return "failed"
  if (status === "needs_approval") return "completed"
  return "queued"
}

export function demoAssignmentToAgentJob(demo: DemoAssignment): AgentJob {
  const mappedStatus = mapDemoStatus(demo.status)
  return {
    jobId: demo.id,
    kind: "operator_task",
    status: mappedStatus,
    sessionId: null,
    result: {
      task: { description: demo.brief, status: demo.status },
      analysis_summary: demo.brief,
      finding_description: demo.brief,
      action_title: demo.title,
      action_description: `Deliverables: ${demo.outputTypes.join(", ")} → ${demo.destination}`,
      confidence: (demo.confidence ?? demo.progress) / 100,
      requires_approval: demo.status === "needs_approval",
      agent_name: demo.agent.name,
      summary: demo.brief,
      answer: demo.brief,
      recommended_actions: demo.steps.map((step) => step.name),
    },
    error: demo.status === "failed" ? "Task failed during report generation." : null,
    attempts: 1,
    createdAt: new Date().toISOString(),
    finishedAt: mappedStatus === "completed" || mappedStatus === "failed" ? new Date().toISOString() : null,
  }
}

export async function fetchAssignmentJob(id: string): Promise<AgentJob> {
  try {
    const response = await apiFetch(`/api/agent-jobs/${id}`)
    if (response.ok) {
      return response.json() as Promise<AgentJob>
    }
  } catch {
    // fall through to demo data
  }

  const demo = getDemoAssignment(id)
  if (demo) {
    return demoAssignmentToAgentJob(demo)
  }

  throw new Error("Assignment not found")
}
