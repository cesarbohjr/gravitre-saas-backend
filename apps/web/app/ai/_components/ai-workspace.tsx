"use client"

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import useSWR from "swr"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { motion } from "framer-motion"
import {
  ArrowUp,
  Loader2,
  PanelLeft,
  PanelLeftClose,
  Sparkles,
  Square,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import { parseChatError } from "@/lib/chat-errors"
import { polishAssistantText } from "@/lib/plain-english"
import { conversationMessageToUI } from "@/lib/chat-messages"
import { conversationsApi, searchApi, assistantApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import type { SearchResult } from "@/types/api"
import { ConversationSidebar } from "@/components/gravitre/assistant/conversation-sidebar"
import { PersonaSelector } from "@/components/gravitre/assistant/persona-selector"
import { Button } from "@/components/ui/button"
import { usePreferredPersona } from "@/hooks/use-preferred-persona"
import { useAsyncJob, type AgentJob } from "@/hooks/use-async-job"
import {
  buildOperatorJobPayload,
  createOperatorSession,
  planFromJobResult,
  runSyncOperatorTask,
  type InlineExecutePlan,
} from "@/lib/ai-inline-execute"
import { isConversationalOperatorPrompt } from "@/lib/ai-route-intent"
import {
  describeOperatorJobError,
  isBackendUnavailableError,
} from "@/lib/operator-plan"
import { AiExecuteResults } from "./ai-execute-results"
import { AiFindResults } from "./ai-find-results"
import { AiLanding } from "./ai-landing"
import { AiLayoutPanelPicker } from "./ai-layout-panel-picker"
import { AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"
import {
  ChatExecutionPanel,
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import { useNotifications } from "@/components/gravitre/notification-center"
import {
  DEFAULT_RESULT_BLOCK_ORDER,
  type LayoutColumn,
  type ResultBlockId,
} from "./draggable-result-stack"
import {
  loadLayoutColumns,
  loadLayoutEnabled,
  loadLayoutOrder,
  persistLayoutColumns,
  persistLayoutEnabled,
  persistLayoutOrder,
} from "./ai-layout-storage"
import { LiveActivityRail } from "./live-activity-rail"
import {
  BusinessSignalsBanner,
  type BusinessSignal,
} from "@/components/gravitre/assistant/business-signals-banner"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"
import { ExplainabilityPanel } from "@/components/gravitre/assistant/explainability-panel"
import { PlanProgressIndicator } from "@/components/gravitre/assistant/plan-progress-indicator"
import {
  clearCachedConversationMessages,
  readCachedConversationMessages,
  readCachedInlineTurns,
  readStoredConversationId,
  writeCachedConversationMessages,
  writeCachedInlineTurns,
  writeStoredConversationId,
} from "@/lib/ai-conversation-storage"

type InlineTurn = {
  id: string
  prompt: string
  engine: AiEngine
  status: "running" | "completed" | "failed"
  executePlan?: InlineExecutePlan | null
  executeJob?: AgentJob | null
  executeError?: string | null
  findResults?: SearchResult[]
  findSuggestions?: string[]
  findError?: string | null
}

type AiWorkspaceProps = {
  initialMode?: ModeId
  initialPrompt?: string
  initialConversationId?: string | null
}

function normalizeChatText(message: UIMessage): string {
  const parts = (message.parts ?? []) as Array<{ type?: string; text?: string }>
  return parts
    .filter((part) => part.type === "text" && typeof part.text === "string")
    .map((part) => part.text as string)
    .join("")
}

export function AiWorkspace({
  initialMode = "auto",
  initialPrompt = "",
  initialConversationId = null,
}: AiWorkspaceProps) {
  const { user } = useAuth()
  const { preferredPersona, preferredPersonaRef, handlePersonaChange } = usePreferredPersona({
    enabled: Boolean(user),
  })
  const [mode, setMode] = useState<ModeId>(initialMode)
  const [input, setInput] = useState("")
  const [routing, setRouting] = useState(false)
  const [routedTo, setRoutedTo] = useState<AiEngine | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [inlineTurns, setInlineTurns] = useState<InlineTurn[]>([])
  const [layoutBlockOrder, setLayoutBlockOrder] = useState<ResultBlockId[]>(DEFAULT_RESULT_BLOCK_ORDER)
  const [layoutEnabledBlocks, setLayoutEnabledBlocks] = useState<ResultBlockId[]>([])
  const [layoutBlockColumns, setLayoutBlockColumns] = useState<Partial<Record<ResultBlockId, LayoutColumn>>>({})
  const [conversationLoading, setConversationLoading] = useState(false)
  const [sessionBusy, setSessionBusy] = useState(false)
  const [orgReady, setOrgReady] = useState(false)
  const [threadRestoreStale, setThreadRestoreStale] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return initialConversationId || readStoredConversationId()
  })
  const [conversationTitle, setConversationTitle] = useState("Gravitre AI")
  const [chatMode] = useState<"standard" | "deep">("standard")
  const [dialogueMode, setDialogueMode] = useState<string | null>(null)
  const [pendingTask, setPendingTask] = useState<ChatPendingTask | null>(null)
  const [executionResult, setExecutionResult] = useState<ChatExecutionResult | null>(null)
  const [confirmExecuting, setConfirmExecuting] = useState(false)
  const [activeBusinessSignals, setActiveBusinessSignals] = useState<BusinessSignal[]>([])
  const [advisorBrief, setAdvisorBrief] = useState<AdvisorBrief | null>(null)
  const [strategicPlan, setStrategicPlan] = useState<{
    goal?: string
    confidence?: number
    risks?: Array<{ title?: string; summary?: string; severity?: string }>
  } | null>(null)
  const [taskState, setTaskState] = useState<{
    current_plan?: { steps?: Array<{ step_id?: string; description?: string }> }
    completed_steps?: Array<{ step_id?: string; description?: string }>
    pending_steps?: Array<{ step_id?: string; description?: string }>
  } | null>(null)
  const [explainability, setExplainability] = useState<{
    summary?: string
    evidence?: Array<{ label?: string; kind?: string; relevance?: number }>
    confidence_note?: string
    missing_context?: string[]
  } | null>(null)
  const [contextExplanation, setContextExplanation] = useState<string | null>(null)
  const [executionGate, setExecutionGate] = useState<{
    confidence?: number
    can_proceed?: boolean
    requires_approval?: boolean
    reason?: string
  } | null>(null)
  const notifications = useNotifications()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeConversationIdRef = useRef<string | null>(activeConversationId)
  const submitLockRef = useRef(false)
  const pendingConversationRef = useRef<Promise<string | null> | null>(null)
  const operatorSessionRef = useRef<string | null>(null)
  const activeExecuteTurnRef = useRef<string | null>(null)
  const initialPromptSentRef = useRef(false)
  const initialConversationHandledRef = useRef(false)

  const activeMode = useMemo(() => getModeMeta(mode), [mode])

  const {
    data: conversationsData,
    error: conversationsError,
    isLoading: conversationsLoading,
    mutate: mutateConversations,
  } = useSWR(
    user && orgReady ? "ai-conversations" : null,
    () => conversationsApi.list({ limit: 100, includeArchived: true }),
    { revalidateOnFocus: false },
  )
  const conversations = conversationsData?.conversations ?? []

  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        headers: async () => {
          const token = await getAccessToken()
          const orgId = await ensureSelectedOrg()
          return {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(orgId ? { "x-org-id": orgId } : {}),
            "x-environment": getEnvironmentHeader(),
          }
        },
        body: () => ({
          ...buildChatOrgPayload(),
          mode: chatMode,
          conversation_id: activeConversationIdRef.current,
          preferred_persona: preferredPersonaRef.current,
        }),
      }),
    [chatMode, preferredPersonaRef],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    onError: (error) => {
      submitLockRef.current = false
      setSessionBusy(false)
      toast.error(parseChatError(error instanceof Error ? error : new Error(String(error))))
    },
    onFinish: () => {
      submitLockRef.current = false
      setSessionBusy(false)
      void mutateConversations()
    },
    onData: (dataPart) => {
      if (dataPart.type !== "data-intelligence" || !dataPart.data || typeof dataPart.data !== "object") {
        return
      }
      const payload = dataPart.data as {
        dialogueMode?: string
        executionResult?: ChatExecutionResult
        pendingTask?: ChatPendingTask
        businessSignals?: BusinessSignal[]
        strategicPlan?: typeof strategicPlan
        advisorBrief?: AdvisorBrief
        explainability?: typeof explainability
        executionGate?: typeof executionGate
        contextExplanation?: string
        taskState?: typeof taskState
      }
      if (payload.dialogueMode) setDialogueMode(payload.dialogueMode)
      if (payload.pendingTask) setPendingTask(payload.pendingTask)
      if (payload.taskState) setTaskState(payload.taskState)
      if (payload.strategicPlan) setStrategicPlan(payload.strategicPlan)
      if (payload.advisorBrief) setAdvisorBrief(payload.advisorBrief)
      if (payload.explainability) setExplainability(payload.explainability)
      if (payload.contextExplanation) setContextExplanation(payload.contextExplanation)
      if (payload.executionGate) setExecutionGate(payload.executionGate)
      if (Array.isArray(payload.businessSignals) && payload.businessSignals.length > 0) {
        setActiveBusinessSignals(payload.businessSignals)
      }
      if (payload.executionResult) {
        setExecutionResult(payload.executionResult)
        if (payload.executionResult.success && notifications) {
          notifications.addNotification({
            type: "task_complete",
            title: payload.executionResult.task_label || payload.executionResult.title || "Task completed",
            message:
              polishAssistantText(payload.executionResult.body || "") ||
              "Your request was executed in Gravitre.",
            link: payload.executionResult.url,
          })
        }
      }
    },
  })

  const { data: businessSignalsPayload } = useSWR(
    user ? "ai-business-signals" : null,
    () => assistantApi.businessSignals(),
    { revalidateOnFocus: false },
  )

  const { data: advisorBriefPayload } = useSWR(
    user ? "ai-advisor-brief" : null,
    () => assistantApi.advisorBrief(),
    { revalidateOnFocus: false },
  )

  useEffect(() => {
    const fetched = businessSignalsPayload?.signals
    if (Array.isArray(fetched) && fetched.length > 0 && activeBusinessSignals.length === 0) {
      setActiveBusinessSignals(fetched as BusinessSignal[])
    }
  }, [businessSignalsPayload, activeBusinessSignals.length])

  useEffect(() => {
    if (advisorBriefPayload && !advisorBrief) {
      setAdvisorBrief(advisorBriefPayload as AdvisorBrief)
    }
  }, [advisorBriefPayload, advisorBrief])

  useSWR(
    user && activeConversationId ? `ai-conversation-state-${activeConversationId}` : null,
    () => assistantApi.getConversationState(activeConversationId!),
    {
      revalidateOnFocus: false,
      onSuccess: (data) => {
        if (data?.task_state) {
          setTaskState(data.task_state as typeof taskState)
        }
      },
    },
  )

  const handleConfirmExecution = useCallback(async () => {
    const conversationId = activeConversationIdRef.current
    if (!conversationId || confirmExecuting) return
    setConfirmExecuting(true)
    try {
      const result = await assistantApi.executeConversationTask(conversationId)
      if (result.execution_result) {
        setExecutionResult(result.execution_result)
        setDialogueMode("answer")
        setPendingTask(null)
        if (result.execution_result.success && notifications) {
          notifications.addNotification({
            type: "task_complete",
            title: result.execution_result.task_label || result.execution_result.title || "Task completed",
            message: result.execution_result.body || result.message,
            link: result.execution_result.url,
          })
        }
      }
      if (result.success) {
        toast.success(result.message)
      } else {
        toast.error(result.message)
      }
    } catch (error) {
      toast.error(parseChatError(error instanceof Error ? error : new Error(String(error))))
    } finally {
      setConfirmExecuting(false)
    }
  }, [confirmExecuting, notifications])

  const notifyInlineTaskComplete = useCallback(
    (title: string, message: string) => {
      if (!notifications) return
      notifications.addNotification({
        type: "task_complete",
        title,
        message: polishAssistantText(message) || message,
      })
    },
    [notifications],
  )

  const {
    isWorking: executeWorking,
    error: executeHookError,
    submitJob,
    reset: resetExecuteJob,
  } = useAsyncJob({
    onCompleted: useCallback(
      (job: AgentJob) => {
        const turnId = activeExecuteTurnRef.current
        if (!turnId) return
        setInlineTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? {
                  ...turn,
                  status: "completed",
                  executeJob: job,
                  executePlan: planFromJobResult(job),
                  executeError: null,
                }
              : turn,
          ),
        )
        activeExecuteTurnRef.current = null
        setSessionBusy(false)
        const summary =
          (job.result?.analysis_summary as string | undefined) ||
          (job.result?.summary as string | undefined) ||
          "Analysis finished — review the results below."
        notifyInlineTaskComplete(
          (job.result?.action_title as string | undefined) || "Task complete",
          summary,
        )
      },
      [notifyInlineTaskComplete],
    ),
    onFailed: useCallback((job: AgentJob) => {
      const turnId = activeExecuteTurnRef.current
      if (!turnId) return
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "failed",
                executeError: job.error || "Analysis failed",
              }
            : turn,
        ),
      )
      activeExecuteTurnRef.current = null
      setSessionBusy(false)
    }, []),
  })

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId
  }, [activeConversationId])

  useEffect(() => {
    if (!user) {
      setOrgReady(false)
      return
    }
    void ensureSelectedOrg(true).then((orgId) => setOrgReady(Boolean(orgId)))
  }, [user])

  useEffect(() => {
    if (!orgReady || !activeConversationId || conversationsLoading) return
    if (conversations.some((conversation) => conversation.id === activeConversationId)) return
    writeStoredConversationId(null)
    setActiveConversationId(null)
    activeConversationIdRef.current = null
    setMessages([])
    setConversationTitle("Gravitre AI")
    setThreadRestoreStale(false)
  }, [orgReady, activeConversationId, conversations, conversationsLoading, setMessages])

  useEffect(() => {
    setLayoutBlockOrder(loadLayoutOrder())
    setLayoutEnabledBlocks(loadLayoutEnabled())
    setLayoutBlockColumns(loadLayoutColumns())
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, inlineTurns, status, conversationLoading])

  const classifyIntent = useCallback(async (prompt: string): Promise<AiEngine> => {
    const res = await fetch("/api/ai/route-intent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    })
    if (!res.ok) throw new Error(`route-intent ${res.status}`)
    const data = (await res.json()) as { mode: AiEngine }
    return data.mode
  }, [])

  const resolveEngine = useCallback(
    async (prompt: string, selectedMode: ModeId): Promise<AiEngine> => {
      if (isConversationalOperatorPrompt(prompt)) {
        return "chat"
      }
      if (selectedMode !== "auto") return selectedMode
      setRouting(true)
      setRoutedTo(null)
      try {
        const engine = await classifyIntent(prompt)
        setRoutedTo(engine)
        return engine
      } catch {
        return "chat"
      } finally {
        setRouting(false)
        setRoutedTo(null)
      }
    },
    [classifyIntent],
  )

  const ensureConversation = useCallback(
    async (title: string) => {
      if (activeConversationIdRef.current) return activeConversationIdRef.current
      if (!pendingConversationRef.current) {
        pendingConversationRef.current = conversationsApi
          .create({ title: title.slice(0, 80) })
          .then((created) => {
            activeConversationIdRef.current = created.id
            setActiveConversationId(created.id)
            setConversationTitle(created.title || title.slice(0, 80))
            writeStoredConversationId(created.id)
            void mutateConversations()
            return created.id
          })
          .catch(() => null)
          .finally(() => {
            pendingConversationRef.current = null
          })
      }
      return pendingConversationRef.current
    },
    [mutateConversations],
  )

  const loadConversationMessages = useCallback(
    async (id: string, options?: { preferApi?: boolean; silent?: boolean }) => {
      const orgId = await ensureSelectedOrg(true)
      if (!orgId) {
        if (!options?.silent) {
          toast.error("Organization context required", {
            description: "Select a workspace before loading conversations.",
          })
        }
        return
      }

      const cached = readCachedConversationMessages(id)
      const showBlockingLoader = !options?.silent && !cached?.length
      let fetchedCount = cached?.length ?? 0

      if (showBlockingLoader) {
        setConversationLoading(true)
        setThreadRestoreStale(false)
      }
      if (!options?.silent && !cached?.length) {
        setInlineTurns([])
      }
      if (cached?.length && !options?.silent) {
        setMessages(cached)
      }

      try {
        const { messages: stored } = await conversationsApi.getMessages(id)
        fetchedCount = stored.length
        if (stored.length > 0) {
          const uiMessages = stored.map(conversationMessageToUI)
          setMessages(uiMessages)
          writeCachedConversationMessages(id, uiMessages)
          setThreadRestoreStale(false)
        } else if (!options?.preferApi) {
          if (cached?.length) {
            setMessages(cached)
            setThreadRestoreStale(false)
          } else {
            setMessages([])
          }
        } else if (!cached?.length) {
          setMessages([])
        }

        const selected = conversations.find((conversation) => conversation.id === id)
        if (selected?.title) setConversationTitle(selected.title)

        const cachedTurns = readCachedInlineTurns<InlineTurn>(id)
        if (cachedTurns?.length) setInlineTurns(cachedTurns)
      } catch (error) {
        if (cached?.length) {
          setMessages(cached)
          setThreadRestoreStale(false)
        } else if (error instanceof ApiError && error.status === 404) {
          writeStoredConversationId(null)
          setActiveConversationId(null)
          activeConversationIdRef.current = null
          setMessages([])
          setConversationTitle("Gravitre AI")
          setThreadRestoreStale(false)
        } else if (!cached?.length) {
          if (error instanceof ApiError && (error.status === 502 || error.status === 503)) {
            toast.error("Gravitre AI is reconnecting", {
              description: "The backend is unavailable. Try again in a moment or start a new conversation.",
            })
          } else if (error instanceof ApiError && error.status === 403) {
            toast.error("Could not load conversation", {
              description: "Organization context is missing or invalid for this thread.",
            })
          } else {
            toast.error("Could not load conversation")
          }
        }
      } finally {
        if (showBlockingLoader) {
          setConversationLoading(false)
        }
        if (fetchedCount === 0 && !cached?.length) {
          const selected = conversations.find((conversation) => conversation.id === id)
          setThreadRestoreStale((selected?.message_count ?? 0) > 0)
        }
      }
    },
    [conversations, setMessages],
  )

  const runChat = useCallback(
    async (prompt: string) => {
      submitLockRef.current = true
      setSessionBusy(true)
      await ensureConversation(prompt)
      sendMessage({ text: prompt })
    },
    [ensureConversation, sendMessage],
  )

  const runExecute = useCallback(
    async (prompt: string, turnId: string) => {
      activeExecuteTurnRef.current = turnId
      if (!operatorSessionRef.current) {
        operatorSessionRef.current = await createOperatorSession(prompt)
      }

      try {
        resetExecuteJob()
        await submitJob(prompt, buildOperatorJobPayload(operatorSessionRef.current, prompt))
      } catch (err) {
        if (isBackendUnavailableError(err)) {
          try {
            const sessionId = operatorSessionRef.current ?? (await createOperatorSession(prompt))
            if (sessionId) operatorSessionRef.current = sessionId
            if (!sessionId) throw new Error("Could not create operator session")
            const plan = await runSyncOperatorTask(sessionId, prompt)
            setInlineTurns((prev) =>
              prev.map((turn) =>
                turn.id === turnId
                  ? { ...turn, status: "completed", executePlan: plan, executeError: null }
                  : turn,
              ),
            )
            activeExecuteTurnRef.current = null
            setSessionBusy(false)
            notifyInlineTaskComplete(
              "Task complete",
              plan.findings?.[0]?.content || "Analysis finished — review the results below.",
            )
            return
          } catch (fallbackErr) {
            setInlineTurns((prev) =>
              prev.map((turn) =>
                turn.id === turnId
                  ? {
                      ...turn,
                      status: "failed",
                      executePlan: null,
                      executeError: describeOperatorJobError(fallbackErr),
                    }
                  : turn,
              ),
            )
            activeExecuteTurnRef.current = null
            setSessionBusy(false)
            return
          }
        }
        setInlineTurns((prev) =>
          prev.map((turn) =>
            turn.id === turnId
              ? { ...turn, status: "failed", executeError: describeOperatorJobError(err) }
              : turn,
          ),
        )
        activeExecuteTurnRef.current = null
        setSessionBusy(false)
      }
    },
    [notifyInlineTaskComplete, resetExecuteJob, submitJob],
  )

  const runFind = useCallback(async (prompt: string, turnId: string) => {
    try {
      const response = await searchApi.search(prompt)
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? {
                ...turn,
                status: "completed",
                findResults: response.results,
                findSuggestions: response.suggestions,
                findError: null,
              }
            : turn,
        ),
      )
      setSessionBusy(false)
      notifyInlineTaskComplete(
        "Search complete",
        response.results?.length
          ? `Found ${response.results.length} result${response.results.length === 1 ? "" : "s"} for your query.`
          : "Search finished — review the results below.",
      )
    } catch {
      setInlineTurns((prev) =>
        prev.map((turn) =>
          turn.id === turnId
            ? { ...turn, status: "failed", findError: "Search failed. Try again." }
            : turn,
        ),
      )
      setSessionBusy(false)
    }
  }, [notifyInlineTaskComplete])

  const submitPrompt = useCallback(
    async (rawPrompt: string) => {
      const prompt = rawPrompt.trim()
      if (!prompt || routing || submitLockRef.current) return
      if (!user) {
        toast.error("Sign in to use Gravitre AI")
        return
      }

      setSessionBusy(true)
      await ensureSelectedOrg()
      await ensureConversation(prompt)
      const engine = await resolveEngine(prompt, mode)
      setInput("")

      if (engine === "chat") {
        await runChat(prompt)
        return
      }

      const turnId = `turn-${Date.now()}`
      setInlineTurns((prev) => [
        ...prev,
        {
          id: turnId,
          prompt,
          engine,
          status: "running",
        },
      ])

      if (engine === "execute") {
        await runExecute(prompt, turnId)
      } else {
        await runFind(prompt, turnId)
      }
    },
    [mode, resolveEngine, routing, runChat, runExecute, runFind, user, ensureConversation],
  )

  useEffect(() => {
    if (initialPromptSentRef.current || !initialPrompt.trim()) return
    initialPromptSentRef.current = true
    void submitPrompt(initialPrompt)
  }, [initialPrompt, submitPrompt])

  const handleSelectConversation = useCallback(
    async (id: string) => {
      if (id === activeConversationIdRef.current && messages.length > 0) {
        setSidebarOpen(false)
        return
      }

      const orgId = await ensureSelectedOrg(true)
      if (!orgId) {
        toast.error("Organization context required", {
          description: "Select a workspace before opening conversations.",
        })
        return
      }
      setOrgReady(true)

      setSessionBusy(false)
      submitLockRef.current = false
      setSidebarOpen(false)
      stop()
      setThreadRestoreStale(false)

      setActiveConversationId(id)
      activeConversationIdRef.current = id
      writeStoredConversationId(id)
      operatorSessionRef.current = null
      resetExecuteJob()

      const cached = readCachedConversationMessages(id)
      if (cached?.length) {
        setMessages(cached)
      } else {
        setMessages([])
      }
      setInlineTurns(readCachedInlineTurns<InlineTurn>(id) ?? [])

      const selected = conversations.find((conversation) => conversation.id === id)
      if (selected?.title) setConversationTitle(selected.title)

      await loadConversationMessages(id)
    },
    [conversations, loadConversationMessages, messages.length, resetExecuteJob, setMessages, stop],
  )

  const handleNewConversation = useCallback(() => {
    if (activeConversationId) clearCachedConversationMessages(activeConversationId)
    setMessages([])
    setInlineTurns([])
    setActiveConversationId(null)
    activeConversationIdRef.current = null
    pendingConversationRef.current = null
    operatorSessionRef.current = null
    writeStoredConversationId(null)
    resetExecuteJob()
    setConversationTitle("Gravitre AI")
    setConversationLoading(false)
    setThreadRestoreStale(false)
    setSessionBusy(false)
    submitLockRef.current = false
    inputRef.current?.focus()
    void mutateConversations()
  }, [activeConversationId, mutateConversations, resetExecuteJob, setMessages])

  const handleDeleteConversation = useCallback(
    async (id: string) => {
      clearCachedConversationMessages(id)
      await conversationsApi.delete(id)
      if (activeConversationId === id) handleNewConversation()
      void mutateConversations()
    },
    [activeConversationId, handleNewConversation, mutateConversations],
  )

  const handleArchiveConversation = useCallback(
    async (id: string) => {
      await conversationsApi.archive(id)
      if (activeConversationId === id) handleNewConversation()
      void mutateConversations()
    },
    [activeConversationId, handleNewConversation, mutateConversations],
  )

  const handleRenameConversation = useCallback(
    async (id: string, title: string) => {
      await conversationsApi.update(id, { title })
      if (activeConversationId === id) setConversationTitle(title)
      void mutateConversations()
    },
    [activeConversationId, mutateConversations],
  )

  const handleBulkDeleteConversations = useCallback(
    async (ids: string[]) => {
      await conversationsApi.bulkDelete(ids)
      if (activeConversationId && ids.includes(activeConversationId)) handleNewConversation()
      void mutateConversations()
    },
    [activeConversationId, handleNewConversation, mutateConversations],
  )

  const isChatBusy = status === "submitted" || status === "streaming"
  const showConversationsSkeleton = Boolean(user) && conversationsLoading && !conversationsData
  const showConversationsError = Boolean(user) && Boolean(conversationsError) && !conversationsLoading
  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? null,
    [conversations, activeConversationId],
  )
  const activeConversationHasStoredMessages = (activeConversation?.message_count ?? 0) > 0

  useEffect(() => {
    if (!initialConversationId || initialConversationHandledRef.current || !user || !orgReady) return
    if (
      conversations.length > 0 &&
      !conversations.some((conversation) => conversation.id === initialConversationId)
    ) {
      return
    }
    initialConversationHandledRef.current = true
    void handleSelectConversation(initialConversationId)
  }, [initialConversationId, user, orgReady, conversations, handleSelectConversation])

  useEffect(() => {
    if (!orgReady || !user || !activeConversationId || messages.length > 0 || sessionBusy || isChatBusy || conversationLoading) {
      return
    }
    void loadConversationMessages(activeConversationId)
  }, [
    orgReady,
    user,
    activeConversationId,
    messages.length,
    sessionBusy,
    isChatBusy,
    conversationLoading,
    loadConversationMessages,
  ])

  useEffect(() => {
    if (!activeConversationId || messages.length === 0) return
    writeCachedConversationMessages(activeConversationId, messages)
  }, [activeConversationId, messages])

  useEffect(() => {
    if (!activeConversationId) return
    writeCachedInlineTurns(activeConversationId, inlineTurns)
  }, [activeConversationId, inlineTurns])

  const handleToggleLayoutBlock = useCallback((blockId: ResultBlockId, enabled: boolean) => {
    setLayoutEnabledBlocks((current) => {
      const next = enabled
        ? current.includes(blockId)
          ? current
          : [...current, blockId]
        : current.filter((id) => id !== blockId)
      persistLayoutEnabled(next)
      return next
    })
    if (enabled) {
      setLayoutBlockOrder((current) => {
        const next = current.includes(blockId) ? current : [...current, blockId]
        persistLayoutOrder(next)
        return next
      })
    }
  }, [])

  const handleReorderLayoutBlocks = useCallback((next: ResultBlockId[]) => {
    setLayoutBlockOrder(next)
    persistLayoutOrder(next)
  }, [])

  const handleMoveLayoutBlockToColumn = useCallback((blockId: ResultBlockId, target: LayoutColumn) => {
    setLayoutBlockColumns((current) => {
      const next = { ...current, [blockId]: target }
      persistLayoutColumns(next)
      return next
    })
    setLayoutEnabledBlocks((current) => {
      if (current.includes(blockId)) return current
      const next = [...current, blockId]
      persistLayoutEnabled(next)
      return next
    })
    setLayoutBlockOrder((current) => {
      const next = current.includes(blockId) ? current : [...current, blockId]
      persistLayoutOrder(next)
      return next
    })
  }, [])

  const latestExecuteTurn = useMemo(
    () => [...inlineTurns].reverse().find((turn) => turn.engine === "execute") ?? null,
    [inlineTurns],
  )

  const showLanding =
    !activeConversationId &&
    messages.length === 0 &&
    inlineTurns.length === 0 &&
    !isChatBusy &&
    !routing &&
    !initialPrompt.trim() &&
    !conversationLoading

  const showPinnedLayout =
    layoutEnabledBlocks.length > 0 && latestExecuteTurn == null && inlineTurns.length === 0

  const showEmptyThreadHint =
    !showLanding &&
    !conversationLoading &&
    activeConversationId &&
    messages.length === 0 &&
    inlineTurns.length === 0 &&
    !isChatBusy &&
    !sessionBusy &&
    !routing &&
    !threadRestoreStale &&
    !activeConversationHasStoredMessages

  const showWaitingForReply =
    !showLanding &&
    !conversationLoading &&
    (sessionBusy || isChatBusy) &&
    messages.length === 0 &&
    inlineTurns.length === 0

  const showComposer = !showLanding || Boolean(activeConversationId)

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    void submitPrompt(input)
  }

  return (
    <div className="flex h-full min-h-0">
      <ConversationSidebar
        conversations={conversations}
        activeConversationId={activeConversationId}
        onSelect={(id) => void handleSelectConversation(id)}
        onNew={handleNewConversation}
        onDelete={(id) => void handleDeleteConversation(id)}
        onArchive={(id) => void handleArchiveConversation(id)}
        onRename={(id, title) => void handleRenameConversation(id, title)}
        onBulkDelete={(ids) => void handleBulkDeleteConversations(ids)}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((open) => !open)}
        isLoading={showConversationsSkeleton}
        loadError={showConversationsError ? conversationsError : undefined}
        onRetry={() => void mutateConversations()}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-border bg-card/80 backdrop-blur">
          <div className="flex min-h-14 items-center justify-between gap-3 px-4 md:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen((open) => !open)}
                className="h-8 w-8 shrink-0 text-muted-foreground"
                aria-label={sidebarOpen ? "Hide history" : "Show history"}
              >
                {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
              </Button>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-foreground">{conversationTitle}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {activeMode.badge} · results stay on this page
                </p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {user && (mode === "chat" || !showLanding) ? (
                <PersonaSelector
                  value={preferredPersona}
                  onChange={handlePersonaChange}
                  disabled={!user}
                />
              ) : null}
              {!showLanding ? (
                <AiLayoutPanelPicker
                  enabledBlocks={layoutEnabledBlocks}
                  onToggleBlock={handleToggleLayoutBlock}
                />
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto border-t border-border/60 px-4 py-2 md:px-6">
            {AI_MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setMode(m.id)}
                className={cn(
                  "shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide transition-colors",
                  mode === m.id
                    ? cn("ring-1", m.ring, "text-foreground")
                    : "border-border text-muted-foreground hover:text-foreground",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        <BusinessSignalsBanner signals={activeBusinessSignals} />
        {dialogueMode === "guide" ? <PlanProgressIndicator taskState={taskState} /> : null}
        {executionGate && (executionGate.requires_approval || executionGate.can_proceed === false) ? (
          <div className="border-b border-amber-200/60 bg-amber-50/50 px-4 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200 md:px-6">
            {executionGate.reason ?? "Execution requires review before proceeding."}
          </div>
        ) : null}

        <div className="ai-chat-canvas flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto max-w-3xl space-y-6">
            {showLanding ? (
              <AiLanding
                mode={mode}
                onModeChange={setMode}
                input={input}
                onInputChange={setInput}
                routing={routing}
                routedTo={routedTo}
                onSubmit={() => void submitPrompt(input)}
              />
            ) : null}

            {conversationLoading && !sessionBusy && !isChatBusy ? (
              <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Loading conversation…
              </div>
            ) : null}

            {!showLanding && (!conversationLoading || sessionBusy || isChatBusy)
              ? messages.map((message) => {
              const text = normalizeChatText(message)
              const isUser = message.role === "user"
              const displayText = isUser ? text : polishAssistantText(text)
              const lastAssistantId = [...messages].reverse().find((row) => row.role === "assistant")?.id
              return (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
                >
                  {!isUser ? (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary">
                      <Sparkles className="h-4 w-4 text-primary-foreground" />
                    </div>
                  ) : null}
                  <div
                    className={cn(
                      "max-w-[85%] rounded-2xl px-4 py-3 text-sm",
                      isUser
                        ? "bg-primary text-primary-foreground"
                        : "border border-border bg-card text-foreground",
                    )}
                  >
                    {isUser ? (
                      <p className="whitespace-pre-wrap">{text}</p>
                    ) : (
                      <div className="prose prose-sm dark:prose-invert max-w-none">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayText || "…"}</ReactMarkdown>
                        {!isUser && message.id === lastAssistantId ? (
                          <>
                            <ChatExecutionPanel
                              dialogueMode={dialogueMode}
                              executionResult={executionResult}
                              pendingTask={pendingTask}
                              confirming={confirmExecuting}
                              onConfirm={() => void handleConfirmExecution()}
                            />
                            <ExplainabilityPanel
                              explanation={explainability}
                              contextExplanation={contextExplanation}
                            />
                          </>
                        ) : null}
                      </div>
                    )}
                  </div>
                </motion.div>
              )
            })
              : null}

            {!showLanding && !conversationLoading && threadRestoreStale ? (
              <div className="rounded-xl border border-dashed border-amber-500/30 bg-amber-500/5 px-4 py-8 text-center text-sm text-muted-foreground">
                <p className="font-medium text-foreground">Messages could not be restored</p>
                <p className="mt-1 text-xs">
                  This thread has history metadata but no retrievable messages. Send a new message to continue, or start fresh.
                </p>
                <Button variant="outline" size="sm" className="mt-4" onClick={handleNewConversation}>
                  Start fresh
                </Button>
              </div>
            ) : null}

            {!showLanding && !conversationLoading && showWaitingForReply ? (
              <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Gravitre is thinking…
              </div>
            ) : null}

            {!showLanding && !conversationLoading && showEmptyThreadHint ? (
              <div className="rounded-xl border border-dashed border-border bg-card/40 px-4 py-8 text-center text-sm text-muted-foreground">
                <p className="font-medium text-foreground">This conversation is empty</p>
                <p className="mt-1 text-xs">Send a message below to continue this thread.</p>
              </div>
            ) : null}

            {!showLanding && !conversationLoading
              ? inlineTurns.map((turn) => (
              <div key={turn.id} className="space-y-4">
                <div className="flex justify-end">
                  <div className="max-w-[85%] rounded-2xl bg-primary px-4 py-3 text-sm text-primary-foreground">
                    <p className="whitespace-pre-wrap">{turn.prompt}</p>
                    <p className="mt-1 text-[10px] uppercase tracking-wide opacity-70">
                      {getModeMeta(turn.engine).badge}
                    </p>
                  </div>
                </div>

                {turn.engine === "execute" ? (
                  <AiExecuteResults
                    plan={turn.executePlan ?? null}
                    job={turn.executeJob ?? null}
                    isProcessing={turn.status === "running" && executeWorking}
                    error={turn.executeError ?? (turn.status === "running" ? executeHookError : null)}
                    blockOrder={layoutBlockOrder}
                    enabledBlocks={layoutEnabledBlocks}
                    onReorderBlocks={handleReorderLayoutBlocks}
                    blockColumns={layoutBlockColumns}
                    onMoveBlockToColumn={handleMoveLayoutBlockToColumn}
                    column="main"
                  />
                ) : null}

                {turn.engine === "find" ? (
                  <AiFindResults
                    results={turn.findResults ?? []}
                    suggestions={turn.findSuggestions ?? []}
                    isSearching={turn.status === "running"}
                    onSuggestionSelect={(query) => void submitPrompt(query)}
                  />
                ) : null}

                {turn.findError ? (
                  <p className="text-sm text-destructive">{turn.findError}</p>
                ) : null}
              </div>
            ))
              : null}

            {showPinnedLayout ? (
              <AiExecuteResults
                plan={null}
                job={null}
                isProcessing={false}
                error={null}
                blockOrder={layoutBlockOrder}
                enabledBlocks={layoutEnabledBlocks}
                onReorderBlocks={handleReorderLayoutBlocks}
                blockColumns={layoutBlockColumns}
                onMoveBlockToColumn={handleMoveLayoutBlockToColumn}
                column="main"
              />
            ) : null}

            {routing ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Reading your intent…
              </div>
            ) : null}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {showComposer ? (
        <div className="border-t border-border bg-background/95 px-4 py-4 backdrop-blur md:px-8">
          <div className="mx-auto max-w-3xl">
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void submitPrompt(input)
              }}
            >
              <div
                className={cn(
                  "flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm",
                  "focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20",
                )}
              >
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  rows={1}
                  disabled={routing}
                  placeholder="Ask, delegate, or search — results appear here…"
                  className="max-h-[200px] min-h-[24px] flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none placeholder:text-muted-foreground/70"
                  style={{ height: "24px" }}
                  onInput={(event) => {
                    const target = event.target as HTMLTextAreaElement
                    target.style.height = "24px"
                    target.style.height = `${Math.min(target.scrollHeight, 200)}px`
                  }}
                />
                <div className="flex shrink-0 items-center gap-2 pb-0.5">
                  {isChatBusy ? (
                    <Button variant="outline" size="sm" className="h-8" onClick={() => stop()}>
                      <Square className="mr-1 h-3 w-3" />
                      Stop
                    </Button>
                  ) : null}
                  <button
                    type="submit"
                    disabled={!input.trim() || routing || isChatBusy}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-primary-foreground disabled:opacity-40"
                    aria-label="Send"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                </div>
              </div>
              <p className="mt-2 px-1 text-xs text-muted-foreground">{activeMode.blurb}</p>
            </form>
          </div>
        </div>
        ) : null}
      </div>

      <LiveActivityRail
        advisorBrief={advisorBrief}
        layoutPlan={latestExecuteTurn?.executePlan ?? null}
        layoutJob={latestExecuteTurn?.executeJob ?? null}
        layoutProcessing={Boolean(latestExecuteTurn?.status === "running" && executeWorking)}
        layoutError={latestExecuteTurn?.executeError ?? null}
        layoutBlockOrder={layoutBlockOrder}
        layoutEnabledBlocks={layoutEnabledBlocks}
        layoutBlockColumns={layoutBlockColumns}
        onReorderLayoutBlocks={handleReorderLayoutBlocks}
        onMoveLayoutBlockToColumn={handleMoveLayoutBlockToColumn}
      />
    </div>
  )
}
