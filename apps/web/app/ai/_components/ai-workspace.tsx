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
import {
  ArrowUp,
  Loader2,
  PanelLeft,
  PanelLeftClose,
  PanelRight,
  Square,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import {
  DEPARTMENT_OPTIONS,
  getDepartmentHeader,
  getQuickDepartment,
  isCrossDepartmentPrompt,
  setSelectedDepartmentInStorage,
} from "@/lib/department-context"
import { resolveOperatorActiveContext } from "@/lib/operator-context"
import { parseChatError } from "@/lib/chat-errors"
import dynamic from "next/dynamic"
import { polishAssistantText } from "@/lib/plain-english"
import { endChatPerf, startChatPerf } from "@/lib/chat-performance"
import { buildConversationTranscript, mergeTranscriptWithLiveMessages } from "@/lib/conversation-transcript"
import { uiMessageText } from "@/lib/chat-messages"
import {
  serializeInlineTurn,
  splitConversationMessages,
  type PersistedInlineTurn,
} from "@/lib/ai-inline-turn-persistence"
import { conversationsApi, searchApi, assistantApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import type { SearchResult } from "@/types/api"
import { ChatTranscript } from "@/components/gravitre/assistant/chat-transcript"
import { ConversationSidebar } from "@/components/gravitre/assistant/conversation-sidebar"
import { PersonaSelector } from "@/components/gravitre/assistant/persona-selector"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
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
import { AI_EXAMPLE_PROMPTS, AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"
import {
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import { useNotifications } from "@/components/gravitre/notification-center"
import {
  clearCachedConversationMessages,
  readCachedConversationMessages,
  readCachedInlineTurns,
  readStoredConversationId,
  writeCachedConversationMessages,
  writeCachedInlineTurns,
  writeStoredConversationId,
} from "@/lib/ai-conversation-storage"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"
import { PlanProgressIndicator } from "@/components/gravitre/assistant/plan-progress-indicator"
import type { BusinessSignal } from "@/components/gravitre/assistant/business-signals-banner"
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

const LiveActivityRail = dynamic(
  () => import("./live-activity-rail").then((module) => ({ default: module.LiveActivityRail })),
  { ssr: false, loading: () => null },
)

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
  return uiMessageText(message)
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
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activityRailOpen, setActivityRailOpen] = useState(false)
  const [inlineTurns, setInlineTurns] = useState<InlineTurn[]>([])
  const [layoutBlockOrder, setLayoutBlockOrder] = useState<ResultBlockId[]>(DEFAULT_RESULT_BLOCK_ORDER)
  const [layoutEnabledBlocks, setLayoutEnabledBlocks] = useState<ResultBlockId[]>([])
  const [layoutBlockColumns, setLayoutBlockColumns] = useState<Partial<Record<ResultBlockId, LayoutColumn>>>({})
  const [conversationLoading, setConversationLoading] = useState(false)
  const [sessionBusy, setSessionBusy] = useState(false)
  const [orgReady, setOrgReady] = useState(false)
  const [threadRestoreStale, setThreadRestoreStale] = useState(false)
  const [messagesHydrated, setMessagesHydrated] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return initialConversationId || readStoredConversationId()
  })
  const [conversationTitle, setConversationTitle] = useState("Chat")
  const [chatMode, setChatMode] = useState<"standard" | "deep">("standard")
  const [selectedDepartment, setSelectedDepartment] = useState(() =>
    typeof window === "undefined" ? "all" : getQuickDepartment(),
  )
  const operatorContextRef = useRef<string | null>(null)
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
  const pendingConversationIdsRef = useRef<Set<string>>(new Set())
  const messagesLoadGenerationRef = useRef(0)
  const chatStatusRef = useRef<"ready" | "submitted" | "streaming" | "error">("ready")
  const sessionBusyRef = useRef(false)
  const operatorSessionRef = useRef<string | null>(null)
  const activeExecuteTurnRef = useRef<string | null>(null)
  const initialPromptSentRef = useRef(false)
  const initialConversationHandledRef = useRef(false)
  const crossDepartmentRef = useRef(false)
  const loadingMessagesForRef = useRef<string | null>(null)
  const messagesLoadResolvedRef = useRef<{ conversationId: string; resolved: boolean } | null>(null)
  const chatFirstTokenMarkedRef = useRef(false)
  const persistedTurnIdsRef = useRef<Set<string>>(new Set())
  const persistedChatPairIdsRef = useRef<Set<string>>(new Set())

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
            ...(getDepartmentHeader() ? { "x-department": getDepartmentHeader()! } : {}),
          }
        },
        body: () => ({
          ...buildChatOrgPayload(),
          mode: chatMode,
          conversation_id: activeConversationIdRef.current,
          preferred_persona: preferredPersonaRef.current,
          department: selectedDepartment === "all" ? undefined : selectedDepartment,
          cross_department: crossDepartmentRef.current,
        }),
      }),
    [chatMode, selectedDepartment],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    onError: (error) => {
      submitLockRef.current = false
      setSessionBusy(false)
      toast.error(parseChatError(error instanceof Error ? error : new Error(String(error))))
    },
    onFinish: ({ messages: finishedMessages }) => {
      submitLockRef.current = false
      setSessionBusy(false)
      const conversationId = activeConversationIdRef.current
      if (conversationId && finishedMessages.length > 0) {
        writeCachedConversationMessages(conversationId, finishedMessages)
      }
      void persistChatTurn(finishedMessages)
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
    startChatPerf("page_load")
    return () => {
      endChatPerf("page_load")
    }
  }, [])

  useEffect(() => {
    chatStatusRef.current = status
  }, [status])

  useEffect(() => {
    sessionBusyRef.current = sessionBusy
  }, [sessionBusy])

  useEffect(() => {
    if (!activeConversationId) return
    if (!conversations.some((conversation) => conversation.id === activeConversationId)) return
    pendingConversationIdsRef.current.delete(activeConversationId)
  }, [activeConversationId, conversations])

  useEffect(() => {
    if (!orgReady || !activeConversationId || conversationsLoading) return
    if (conversations.length === 0) return
    if (conversations.some((conversation) => conversation.id === activeConversationId)) return
    if (pendingConversationRef.current) return
    if (pendingConversationIdsRef.current.has(activeConversationId)) return
    if (sessionBusyRef.current) return
    if (chatStatusRef.current === "submitted" || chatStatusRef.current === "streaming") return
    writeStoredConversationId(null)
    setActiveConversationId(null)
    activeConversationIdRef.current = null
    setMessages([])
    setConversationTitle("Chat")
    setThreadRestoreStale(false)
    setMessagesHydrated(false)
  }, [orgReady, activeConversationId, conversations, conversationsLoading, setMessages])

  useEffect(() => {
    setLayoutBlockOrder(loadLayoutOrder())
    setLayoutEnabledBlocks(loadLayoutEnabled())
    setLayoutBlockColumns(loadLayoutColumns())
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, inlineTurns, status, conversationLoading])

  const resolveEngine = useCallback(
    async (prompt: string, selectedMode: ModeId): Promise<AiEngine> => {
      if (isConversationalOperatorPrompt(prompt)) {
        return "chat"
      }
      // Unified surface: one chat thread handles answer, search, and connector execution.
      if (selectedMode === "auto" || selectedMode === "chat") {
        return "chat"
      }
      return selectedMode
    },
    [],
  )

  const ensureConversation = useCallback(
    async (title: string) => {
      if (activeConversationIdRef.current) return activeConversationIdRef.current
      if (!pendingConversationRef.current) {
        pendingConversationRef.current = conversationsApi
          .create({ title: title.slice(0, 80) })
          .then((created) => {
            activeConversationIdRef.current = created.id
            pendingConversationIdsRef.current.add(created.id)
            setActiveConversationId(created.id)
            setConversationTitle(created.title || title.slice(0, 80))
            writeStoredConversationId(created.id)
            void mutateConversations(
              (current) => {
                if (!current) return current
                if (current.conversations.some((conversation) => conversation.id === created.id)) {
                  return current
                }
                return {
                  ...current,
                  conversations: [created, ...current.conversations],
                }
              },
              { revalidate: false },
            )
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

  const applyConversationMessages = useCallback(
    (id: string, generation: number, nextMessages: UIMessage[], options?: { allowEmpty?: boolean }) => {
      if (messagesLoadGenerationRef.current !== generation) return
      if (activeConversationIdRef.current !== id) return

      setMessages((live) => {
        const chatBusy =
          chatStatusRef.current === "submitted" || chatStatusRef.current === "streaming"
        if (chatBusy || sessionBusyRef.current) {
          return mergeTranscriptWithLiveMessages(nextMessages, live)
        }
        if (live.length > 0 && nextMessages.length === 0 && !options?.allowEmpty) {
          return live
        }
        if (live.length === 0) return nextMessages
        return mergeTranscriptWithLiveMessages(nextMessages, live)
      })
    },
    [setMessages],
  )

  const persistInlineTurn = useCallback(
    async (turn: InlineTurn) => {
      if (turn.status !== "completed" && turn.status !== "failed") return
      if (persistedTurnIdsRef.current.has(turn.id)) return
      const conversationId = activeConversationIdRef.current
      if (!conversationId) return

      const payload: PersistedInlineTurn = {
        id: turn.id,
        prompt: turn.prompt,
        engine: turn.engine,
        status: turn.status,
        executePlan: turn.executePlan ?? null,
        executeError: turn.executeError ?? null,
        findResults: turn.findResults,
        findSuggestions: turn.findSuggestions,
        findError: turn.findError ?? null,
      }

      try {
        const rows = serializeInlineTurn(payload)
        await conversationsApi.appendMessages(
          conversationId,
          rows.map((row) => ({
            role: row.role,
            content: row.content,
            tool_calls: row.tool_calls as unknown[] | undefined,
          })),
        )
        persistedTurnIdsRef.current.add(turn.id)
        void mutateConversations()
      } catch {
        // Best-effort persistence — session cache still holds the turn.
      }
    },
    [mutateConversations],
  )

  const persistChatTurn = useCallback(
    async (finishedMessages: UIMessage[]) => {
      if (finishedMessages.length < 2) return
      const last = finishedMessages[finishedMessages.length - 1]
      const prev = finishedMessages[finishedMessages.length - 2]
      if (last.role !== "assistant" || prev.role !== "user") return

      const pairKey = `${prev.id}:${last.id}`
      if (persistedChatPairIdsRef.current.has(pairKey)) return

      const conversationId = activeConversationIdRef.current
      if (!conversationId) return

      const userText = normalizeChatText(prev).trim()
      const assistantText = polishAssistantText(normalizeChatText(last)).trim()
      if (!userText || !assistantText) return

      try {
        const { messages: stored } = await conversationsApi.getMessages(conversationId)
        const trailingAssistant = stored.length > 0 && stored[stored.length - 1]?.role === "assistant"
        const trailingUser = stored.length > 1 && stored[stored.length - 2]?.role === "user"
        if (
          trailingAssistant &&
          trailingUser &&
          stored[stored.length - 2]?.content.trim() === userText
        ) {
          persistedChatPairIdsRef.current.add(pairKey)
          return
        }

        await conversationsApi.appendMessages(conversationId, [
          { role: "user", content: userText },
          { role: "assistant", content: assistantText },
        ])
        persistedChatPairIdsRef.current.add(pairKey)
        void mutateConversations()
      } catch {
        // Backend persist is primary; this is a best-effort client backup.
      }
    },
    [mutateConversations],
  )

  const loadConversationMessages = useCallback(
    async (id: string, options?: { preferApi?: boolean; silent?: boolean; force?: boolean }) => {
      if (loadingMessagesForRef.current === id && !options?.force) return

      const orgId = await ensureSelectedOrg(true)
      if (!orgId) {
        if (!options?.silent) {
          toast.error("Organization context required", {
            description: "Select a workspace before loading conversations.",
          })
        }
        return
      }

      const generation = messagesLoadGenerationRef.current + 1
      messagesLoadGenerationRef.current = generation

      if (!options?.silent) {
        setMessagesHydrated(false)
        startChatPerf("conversation_load", id)
      }

      const cached = readCachedConversationMessages(id)
      const cachedTurns = readCachedInlineTurns<InlineTurn>(id)
      const showBlockingLoader = !options?.silent && !cached?.length && !cachedTurns?.length
      let fetchedCount = cached?.length ?? 0
      let conversationMeta = conversations.find((conversation) => conversation.id === id) ?? null

      loadingMessagesForRef.current = id
      if (showBlockingLoader) {
        setConversationLoading(true)
        setThreadRestoreStale(false)
      }
      if (!options?.silent && !cached?.length && !cachedTurns?.length) {
        setInlineTurns([])
      }
      if ((cached?.length || cachedTurns?.length) && !options?.silent) {
        if (cached?.length && activeConversationIdRef.current === id) {
          applyConversationMessages(id, generation, cached)
        }
        if (cachedTurns?.length && activeConversationIdRef.current === id) setInlineTurns(cachedTurns)
      }

      try {
        const [messagesResponse, fetchedConversation] = await Promise.all([
          conversationsApi.getMessages(id),
          conversationMeta ? Promise.resolve(conversationMeta) : conversationsApi.get(id).catch(() => null),
        ])
        if (activeConversationIdRef.current !== id) return
        if (messagesLoadGenerationRef.current !== generation) return

        if (fetchedConversation) {
          conversationMeta = fetchedConversation
          if (fetchedConversation.title) setConversationTitle(fetchedConversation.title)
        }

        const { messages: stored } = messagesResponse
        fetchedCount = stored.length
        const { inlineTurns: restoredTurns } = splitConversationMessages(stored)

        if (stored.length > 0) {
          const uiMessages = buildConversationTranscript(stored, {
            conversationTitle: conversationMeta?.title ?? conversationTitle,
          })
          applyConversationMessages(id, generation, uiMessages)
          for (let i = 1; i < stored.length; i += 1) {
            const prev = stored[i - 1]
            const current = stored[i]
            if (prev.role === "user" && current.role === "assistant") {
              persistedChatPairIdsRef.current.add(`${prev.id}:${current.id}`)
            }
          }
          if (restoredTurns.length > 0) {
            setInlineTurns(restoredTurns as InlineTurn[])
            writeCachedInlineTurns(id, restoredTurns)
          } else if (cachedTurns?.length) {
            setInlineTurns(cachedTurns)
          }
          writeCachedConversationMessages(id, uiMessages)
          setThreadRestoreStale(false)
          messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
        } else if (!options?.preferApi) {
          if (cached?.length || cachedTurns?.length) {
            if (cached?.length) applyConversationMessages(id, generation, cached)
            if (cachedTurns?.length) setInlineTurns(cachedTurns)
            setThreadRestoreStale(false)
            messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
          } else {
            applyConversationMessages(id, generation, [], { allowEmpty: true })
            setInlineTurns([])
          }
        } else if (!cached?.length && !cachedTurns?.length) {
          applyConversationMessages(id, generation, [], { allowEmpty: true })
          setInlineTurns([])
        }
      } catch (error) {
        if (activeConversationIdRef.current !== id) return
        if (messagesLoadGenerationRef.current !== generation) return
        if (cached?.length || cachedTurns?.length) {
          if (cached?.length) applyConversationMessages(id, generation, cached)
          if (cachedTurns?.length) setInlineTurns(cachedTurns)
          setThreadRestoreStale(false)
          messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
        } else if (error instanceof ApiError && error.status === 404) {
          writeStoredConversationId(null)
          setActiveConversationId(null)
          activeConversationIdRef.current = null
          applyConversationMessages(id, generation, [], { allowEmpty: true })
          setInlineTurns([])
          setConversationTitle("Chat")
          setThreadRestoreStale(false)
          messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
        } else if (!cached?.length && !cachedTurns?.length) {
          if (error instanceof ApiError && (error.status === 502 || error.status === 503)) {
            toast.error("Chat is reconnecting", {
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
        if (loadingMessagesForRef.current === id) {
          loadingMessagesForRef.current = null
        }
        if (showBlockingLoader) {
          setConversationLoading(false)
        }
        if (!options?.silent) {
          endChatPerf("conversation_load", id)
          if (activeConversationIdRef.current === id) {
            setMessagesHydrated(true)
          }
        }
        if (
          activeConversationIdRef.current === id &&
          fetchedCount === 0 &&
          !cached?.length &&
          !cachedTurns?.length &&
          !messagesLoadResolvedRef.current?.resolved
        ) {
          const stale = (conversationMeta?.message_count ?? 0) > 0
          setThreadRestoreStale(stale)
          messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
        }
      }
    },
    [applyConversationMessages, conversationTitle, conversations],
  )

  const runChat = useCallback(
    async (prompt: string) => {
      submitLockRef.current = true
      setSessionBusy(true)
      chatFirstTokenMarkedRef.current = false
      startChatPerf("total_response")
      startChatPerf("first_token")
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
        if (!operatorContextRef.current) {
          operatorContextRef.current = await resolveOperatorActiveContext()
        }
        await submitJob(
          prompt,
          buildOperatorJobPayload(
            operatorSessionRef.current,
            prompt,
            operatorContextRef.current,
          ),
        )
      } catch (err) {
        if (isBackendUnavailableError(err)) {
          try {
            const sessionId = operatorSessionRef.current ?? (await createOperatorSession(prompt))
            if (sessionId) operatorSessionRef.current = sessionId
            if (!sessionId) throw new Error("Could not create operator session")
            if (!operatorContextRef.current) {
              operatorContextRef.current = await resolveOperatorActiveContext()
            }
            const plan = await runSyncOperatorTask(
              sessionId,
              prompt,
              operatorContextRef.current ?? undefined,
            )
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
        toast.error("Sign in to use Chat")
        return
      }

      setSessionBusy(true)
      await ensureSelectedOrg()
      crossDepartmentRef.current = isCrossDepartmentPrompt(prompt)
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
      if (
        id === activeConversationIdRef.current &&
        messagesHydrated &&
        (messages.length > 0 || inlineTurns.length > 0)
      ) {
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
      setMessagesHydrated(false)
      messagesLoadGenerationRef.current += 1
      const generation = messagesLoadGenerationRef.current
      messagesLoadResolvedRef.current = null
      persistedTurnIdsRef.current = new Set()
      persistedChatPairIdsRef.current = new Set()

      setActiveConversationId(id)
      activeConversationIdRef.current = id
      writeStoredConversationId(id)
      operatorSessionRef.current = null
      resetExecuteJob()

      const cached = readCachedConversationMessages(id)
      const cachedTurns = readCachedInlineTurns<InlineTurn>(id)
      if (cached?.length) {
        applyConversationMessages(id, generation, cached)
      } else {
        applyConversationMessages(id, generation, [], { allowEmpty: true })
      }
      setInlineTurns(cachedTurns ?? [])

      const selected = conversations.find((conversation) => conversation.id === id)
      if (selected?.title) setConversationTitle(selected.title)

      await loadConversationMessages(id, { force: true })
    },
    [applyConversationMessages, conversations, inlineTurns.length, loadConversationMessages, messages.length, messagesHydrated, resetExecuteJob, stop],
  )

  const handleNewConversation = useCallback(() => {
    messagesLoadGenerationRef.current += 1
    if (activeConversationId) clearCachedConversationMessages(activeConversationId)
    setMessages([])
    setInlineTurns([])
    setActiveConversationId(null)
    activeConversationIdRef.current = null
    pendingConversationRef.current = null
    pendingConversationIdsRef.current = new Set()
    operatorSessionRef.current = null
    messagesLoadResolvedRef.current = null
    loadingMessagesForRef.current = null
    persistedTurnIdsRef.current = new Set()
    persistedChatPairIdsRef.current = new Set()
    writeStoredConversationId(null)
    resetExecuteJob()
    setConversationTitle("Chat")
    setConversationLoading(false)
    setThreadRestoreStale(false)
    setMessagesHydrated(true)
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
    if (status !== "streaming") return
    const last = messages[messages.length - 1]
    if (!last || last.role !== "assistant") return
    const text = normalizeChatText(last).trim()
    if (!text || chatFirstTokenMarkedRef.current) return
    chatFirstTokenMarkedRef.current = true
    endChatPerf("first_token")
  }, [status, messages])

  useEffect(() => {
    if (status !== "ready" || !chatFirstTokenMarkedRef.current) return
    endChatPerf("total_response")
    chatFirstTokenMarkedRef.current = false
  }, [status])

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
    if (!orgReady || !user || !activeConversationId || sessionBusy || isChatBusy || conversationLoading) {
      return
    }
    if (messages.length > 0 || inlineTurns.length > 0) return
    if (
      messagesLoadResolvedRef.current?.conversationId === activeConversationId &&
      messagesLoadResolvedRef.current.resolved
    ) {
      return
    }
    void loadConversationMessages(activeConversationId)
  }, [
    orgReady,
    user,
    activeConversationId,
    messages.length,
    inlineTurns.length,
    sessionBusy,
    isChatBusy,
    conversationLoading,
    loadConversationMessages,
  ])

  useEffect(() => {
    for (const turn of inlineTurns) {
      if (turn.status === "completed" || turn.status === "failed") {
        void persistInlineTurn(turn)
      }
    }
  }, [inlineTurns, persistInlineTurn])

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
    messagesHydrated &&
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
    messages.length > 0 &&
    messages[messages.length - 1]?.role === "user"

  const showComposer = !showLanding || Boolean(activeConversationId)

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    void submitPrompt(input)
  }

  return (
    <div className="flex h-full min-h-0 flex-1">
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

      <div className="ai-surface-shell flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="shrink-0 border-b border-emerald-500/15 bg-card/80 backdrop-blur-md">
          <div className="flex min-h-12 items-center gap-2 overflow-x-auto px-3 py-2 md:px-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setSidebarOpen((open) => !open)}
              className="h-8 w-8 shrink-0 text-muted-foreground"
              aria-label={sidebarOpen ? "Hide history" : "Show history"}
            >
              {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
            </Button>

            <div className="min-w-0 shrink">
              <p className="truncate text-sm font-semibold text-foreground">
                {conversationTitle}
              </p>
            </div>

            <div className="hidden h-4 w-px shrink-0 bg-border sm:block" />

            <div className="flex shrink-0 items-center gap-1">
              {AI_MODES.length > 1
                ? AI_MODES.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setMode(m.id)}
                      className={cn(
                        "shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide transition-colors",
                        mode === m.id
                          ? cn("ring-1", m.ring, "text-foreground")
                          : "border-border text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {m.label}
                    </button>
                  ))
                : (
                  <span className="shrink-0 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {activeMode.badge}
                  </span>
                )}
            </div>

            <div className="ml-auto flex shrink-0 items-center gap-1.5">
              <Select
                value={selectedDepartment}
                onValueChange={(value) => {
                  setSelectedDepartment(value)
                  setSelectedDepartmentInStorage(value)
                }}
              >
                <SelectTrigger
                  size="sm"
                  className="hidden h-7 w-[128px] border-border bg-background text-[11px] sm:flex"
                  aria-label="Department context"
                >
                  <SelectValue placeholder="Department" />
                </SelectTrigger>
                <SelectContent align="end" className="z-[60]">
                  {DEPARTMENT_OPTIONS.map((option) => (
                    <SelectItem key={option.id} value={option.id}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <button
                type="button"
                onClick={() => setChatMode((current) => (current === "deep" ? "standard" : "deep"))}
                title={
                  chatMode === "deep"
                    ? "Agent mode — full connector tool surface with ReAct"
                    : "Fast mode — lighter reasoning, fewer tool iterations"
                }
                className={cn(
                  "h-7 rounded-md border px-2 text-[10px] font-medium uppercase tracking-wide",
                  chatMode === "deep"
                    ? "border-blue-500/30 bg-blue-500/10 text-blue-600 dark:text-blue-400"
                    : "border-emerald-500/20 bg-emerald-500/5 text-emerald-700 dark:text-emerald-300",
                )}
              >
                {chatMode === "deep" ? "Agent" : "Fast"}
              </button>

              {user ? (
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

              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 shrink-0 text-muted-foreground"
                aria-label={activityRailOpen ? "Hide activity panel" : "Show activity panel"}
                onClick={() => setActivityRailOpen((open) => !open)}
              >
                <PanelRight className={cn("h-4 w-4", activityRailOpen && "text-emerald-600 dark:text-emerald-400")} />
              </Button>
            </div>
          </div>
        </div>

        {dialogueMode === "guide" ? <PlanProgressIndicator taskState={taskState} /> : null}
        {executionGate && (executionGate.requires_approval || executionGate.can_proceed === false) ? (
          <div className="shrink-0 border-b border-amber-200/60 bg-amber-50/50 px-4 py-1.5 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
            {executionGate.reason ?? "Execution requires review before proceeding."}
          </div>
        ) : null}

        <div className="flex min-h-0 flex-1 flex-col">
        <div className="ai-chat-canvas min-h-0 flex-1 overflow-y-auto px-3 py-3 md:px-5 md:py-4">
          <div className="mx-auto w-full">
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
              <div className="space-y-4 py-4">
                <div className="flex justify-end">
                  <div className="h-12 w-[min(420px,72%)] animate-pulse rounded-2xl bg-primary/20" />
                </div>
                <div className="flex items-start gap-3">
                  <div className="h-8 w-8 shrink-0 animate-pulse rounded-full bg-muted" />
                  <div className="h-24 w-[min(560px,88%)] animate-pulse rounded-2xl bg-muted/60" />
                </div>
              </div>
            ) : null}

            {!showLanding ? (
              <ChatTranscript
                messages={messages}
                showWaiting={showWaitingForReply && !conversationLoading}
                explainability={explainability}
                contextExplanation={contextExplanation}
                dialogueMode={dialogueMode}
                executionResult={executionResult}
                pendingTask={pendingTask}
                confirmExecuting={confirmExecuting}
                onConfirmExecution={() => void handleConfirmExecution()}
              />
            ) : null}

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
                  <div className="max-w-[min(720px,92%)] rounded-2xl bg-gradient-to-br from-emerald-600 to-emerald-500 px-4 py-3.5 text-sm leading-relaxed text-primary-foreground shadow-sm dark:from-emerald-500 dark:to-emerald-400">
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
                    sourcePrompt={turn.prompt}
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
        <div className="shrink-0 border-t border-emerald-500/10 bg-card/90 px-3 py-2 backdrop-blur-md md:px-5">
          <div className="mx-auto w-full max-w-[920px]">
            {!showLanding && messages.length === 0 && inlineTurns.length === 0 && !isChatBusy ? (
              <div className="mb-3 flex flex-wrap justify-center gap-2">
                {AI_EXAMPLE_PROMPTS.slice(0, 4).map((example) => (
                  <button
                    key={example.text}
                    type="button"
                    onClick={() => void submitPrompt(example.text)}
                    className="rounded-full border border-border/70 bg-card/80 px-3 py-1.5 text-center text-xs text-muted-foreground transition-all hover:border-emerald-500/30 hover:bg-emerald-500/5 hover:text-foreground"
                  >
                    {example.text}
                  </button>
                ))}
              </div>
            ) : null}
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void submitPrompt(input)
              }}
            >
              <div
                className={cn(
                  "flex min-h-[72px] flex-col justify-center gap-1.5 rounded-[1.25rem] border border-emerald-500/15 bg-background/90 p-2.5 shadow-sm backdrop-blur-sm focus-within:ring-2 dark:bg-card/90",
                  "focus-within:border-emerald-500/35 focus-within:ring-emerald-500/20",
                )}
              >
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  rows={1}
                  disabled={routing}
                  placeholder="Ask, delegate, or search…"
                  className="max-h-[160px] min-h-[44px] flex-1 resize-none bg-transparent px-2 text-sm outline-none placeholder:text-muted-foreground/70"
                  onInput={(event) => {
                    const target = event.target as HTMLTextAreaElement
                    target.style.height = "44px"
                    target.style.height = `${Math.min(Math.max(target.scrollHeight, 44), 160)}px`
                  }}
                />
                <div className="flex shrink-0 items-center justify-end gap-2 px-1">
                  {isChatBusy ? (
                    <Button variant="outline" size="sm" className="h-8" onClick={() => stop()}>
                      <Square className="mr-1 h-3 w-3" />
                      Stop
                    </Button>
                  ) : null}
                  <button
                    type="submit"
                    disabled={!input.trim() || routing || isChatBusy}
                    className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-600 to-emerald-500 text-primary-foreground shadow-sm transition-all hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-40 dark:from-emerald-500 dark:to-emerald-400"
                    aria-label="Send"
                  >
                    <ArrowUp className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
        ) : null}
        </div>
      </div>

      {activityRailOpen ? (
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
      ) : null}
    </div>
  )
}
