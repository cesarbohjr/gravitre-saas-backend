export type ApiAuthMe = {
  user_id: string
  org_id: string | null
  email: string | null
  role: string | null
}

export type ApiWorkflow = {
  id: string
  name: string
  status: string
}

export type ApiRun = {
  id: string
  workflowId?: string
  status: string
}

export type ApiConnector = {
  id: string
  name: string
  vendor?: string
  status: string
}

export type ApiSource = {
  id: string
  name: string
  type: string
  status: string
}

export type ApiOperator = {
  id: string
  name: string
  status: string
}

export type ApiMetricsOverview = {
  totalWorkflows?: number
  activeWorkflows?: number
  totalRuns?: number
  successRate?: number
  avgDuration?: number
  [key: string]: unknown
}
