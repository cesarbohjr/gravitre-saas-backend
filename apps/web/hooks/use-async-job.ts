import { useState, useRef, useCallback, useEffect } from "react"
import { apiFetch } from "@/lib/fetcher"

export type JobStatus = "queued" | "running" | "paused" | "completed" | "failed" | "cancelled"

export interface AgentJobResult {
  task?: {
    description?: string
    status?: string
  }
  aiStatus?: string
  analysis_summary?: string
  finding_description?: string
  action_title?: string
  action_description?: string
  progress_percent?: number
  confidence?: number
  requires_approval?: boolean
  provider?: string
  model?: string
  // AgentIntelligence handoff fields (agent_task jobs)
  summary?: string
  answer?: string
  status?: string
  react_status?: string
  recommended_actions?: string[]
  agent_id?: string
  agent_name?: string
  tool_calls?: unknown[]
  react_trace?: unknown[]
  rag_sources?: unknown[]
  needs_human_input?: boolean
  human_input_prompt?: string
  error?: string
  persona?: string
}

export interface AgentJob {
  jobId: string
  kind: string
  status: JobStatus
  sessionId: string | null
  result: AgentJobResult | null
  error: string | null
  attempts: number
  createdAt: string
  finishedAt: string | null
}

interface UseAsyncJobOptions {
  onCompleted?: (job: AgentJob) => void
  onFailed?: (job: AgentJob) => void
  onCancelled?: (job: AgentJob) => void
  onPaused?: (job: AgentJob) => void
}

export interface SubmitAgentJobOptions {
  sessionId?: string
  agentId?: string
  context?: Record<string, unknown>
}

const POLL_INTERVAL_BASE = 1500 // 1.5 seconds
const POLL_INTERVAL_MAX = 5000 // 5 seconds after backoff
const BACKOFF_THRESHOLD = 30000 // 30 seconds before backoff
const MAX_POLL_DURATION = 120000 // 2 minutes max

export function useAsyncJob(options: UseAsyncJobOptions = {}) {
  const [job, setJob] = useState<AgentJob | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pollStartTimeRef = useRef<number>(0)
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  // Holds the latest pollJob so the recursive setTimeout doesn't reference the
  // callback before it's declared (avoids react-hooks/immutability error).
  const pollJobRef = useRef<((jobId: string) => void) | null>(null)

  const stopPolling = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current)
      pollTimeoutRef.current = null
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsPolling(false)
  }, [])

  const pollJob = useCallback(async (jobId: string) => {
    const elapsed = Date.now() - pollStartTimeRef.current
    
    // Safety cap: stop polling after max duration
    if (elapsed > MAX_POLL_DURATION) {
      stopPolling()
      setError("Job timed out. Please try again.")
      return
    }

    try {
      abortControllerRef.current = new AbortController()
      const response = await apiFetch(`/api/agent-jobs/${jobId}`, {
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          stopPolling()
          setError("Not authorized. Please sign in again.")
          return
        }
        throw new Error(`Failed to fetch job status: ${response.status}`)
      }

      const data: AgentJob = await response.json()
      setJob(data)

      // Check terminal states
      if (data.status === "completed") {
        stopPolling()
        options.onCompleted?.(data)
        return
      }

      if (data.status === "failed") {
        stopPolling()
        options.onFailed?.(data)
        return
      }

      if (data.status === "paused") {
        stopPolling()
        options.onPaused?.(data)
        return
      }

      if (data.status === "cancelled") {
        stopPolling()
        options.onCancelled?.(data)
        return
      }

      // Continue polling with backoff
      const interval = elapsed > BACKOFF_THRESHOLD
        ? Math.min(POLL_INTERVAL_BASE * 2, POLL_INTERVAL_MAX)
        : POLL_INTERVAL_BASE

      pollTimeoutRef.current = setTimeout(() => pollJobRef.current?.(jobId), interval)
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return // Polling was cancelled
      }
      // On network error, retry after a delay
      pollTimeoutRef.current = setTimeout(() => pollJobRef.current?.(jobId), POLL_INTERVAL_MAX)
    }
  }, [stopPolling, options])

  // Keep the ref pointed at the latest pollJob for the recursive setTimeout.
  useEffect(() => {
    pollJobRef.current = pollJob
  }, [pollJob])

  const startPolling = useCallback((jobId: string) => {
    stopPolling()
    pollStartTimeRef.current = Date.now()
    setIsPolling(true)
    pollJob(jobId)
  }, [stopPolling, pollJob])

  const submitJob = useCallback(async (
    task: string,
    options?: SubmitAgentJobOptions | string,
    legacyContext?: object,
  ) => {
    setIsSubmitting(true)
    setError(null)
    setJob(null)

    let sessionId: string | undefined
    let agentId: string | undefined
    let context: Record<string, unknown> | undefined
    if (typeof options === "string") {
      sessionId = options
      context = legacyContext as Record<string, unknown> | undefined
    } else if (options) {
      sessionId = options.sessionId
      agentId = options.agentId
      context = options.context
    }

    try {
      const response = await apiFetch("/api/agent-jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task,
          session_id: sessionId,
          agent_id: agentId,
          context,
        }),
      })

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          throw new Error("Not authorized. Please sign in again.")
        }
        const data = await response.json().catch(() => ({}))
        throw new Error(data.detail || data.error || "Failed to submit job")
      }

      const data: AgentJob = await response.json()
      setJob(data)
      startPolling(data.jobId)
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit job"
      setError(message)
      throw err
    } finally {
      setIsSubmitting(false)
    }
  }, [startPolling])

  const pauseJob = useCallback(async () => {
    if (!job) return

    try {
      const response = await apiFetch(`/api/agent-jobs/${job.jobId}/pause`, {
        method: "POST",
      })

      if (!response.ok) {
        if (response.status === 409) {
          throw new Error("Job cannot be paused in its current state")
        }
        throw new Error("Failed to pause job")
      }

      const data: AgentJob = await response.json()
      stopPolling()
      setJob(data)
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to pause job"
      setError(message)
      throw err
    }
  }, [job, stopPolling])

  const cancelJob = useCallback(async () => {
    if (!job) return

    try {
      const response = await apiFetch(`/api/agent-jobs/${job.jobId}/cancel`, {
        method: "POST",
      })

      if (!response.ok) {
        if (response.status === 409) {
          throw new Error("Job cannot be cancelled in its current state")
        }
        throw new Error("Failed to cancel job")
      }

      const data: AgentJob = await response.json()
      stopPolling()
      setJob(data)
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to cancel job"
      setError(message)
      throw err
    }
  }, [job, stopPolling])

  const retryJob = useCallback(async () => {
    if (!job) return

    setError(null)

    try {
      const response = await apiFetch(`/api/agent-jobs/${job.jobId}/retry`, {
        method: "POST",
      })

      if (!response.ok) {
        if (response.status === 409) {
          throw new Error("Job cannot be retried in its current state")
        }
        throw new Error("Failed to retry job")
      }

      const data: AgentJob = await response.json()
      setJob(data)
      startPolling(data.jobId)
      return data
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to retry job"
      setError(message)
      throw err
    }
  }, [job, startPolling])

  const reset = useCallback(() => {
    stopPolling()
    setJob(null)
    setError(null)
    setIsSubmitting(false)
  }, [stopPolling])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopPolling()
    }
  }, [stopPolling])

  return {
    job,
    isSubmitting,
    isPolling,
    isWorking: isSubmitting || isPolling,
    error,
    submitJob,
    pauseJob,
    cancelJob,
    retryJob,
    reset,
    stopPolling,
  }
}
