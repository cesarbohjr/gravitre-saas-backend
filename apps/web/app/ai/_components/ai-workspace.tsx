"use client"

import {
  useCallback,
  useDeferredValue,
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
  Info,
  Loader2,
  MoreHorizontal,
  PanelLeft,
  PanelLeftClose,
  PanelRight,
  FolderOpen,
} from "lucide-react"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import {
  ensureSelectedOrg,
  buildChatOrgPayload,
  getSelectedOrgFromStorage,
  getQuickOrgId,
} from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import {
  getDepartmentHeader,
  getQuickDepartment,
  isCrossDepartmentPrompt,
  setSelectedDepartmentInStorage,
} from "@/lib/department-context"
import { resolveOperatorActiveContext } from "@/lib/operator-context"
import { parseChatError } from "@/lib/chat-errors"
import dynamic from "next/dynamic"
import { polishAssistantText } from "@/lib/plain-english"
import {
  CHAT_BUBBLE_BASE_CLASS,
  CHAT_COMPOSER_CLASS,
  CHAT_USER_BUBBLE_CLASS,
} from "@/lib/chat-typography"
import { endChatPerf, startChatPerf } from "@/lib/chat-performance"
import { buildConversationTranscript, mergeTranscriptWithLiveMessages } from "@/lib/conversation-transcript"
import { uiMessageText } from "@/lib/chat-messages"
import { messageCreatedAt } from "@/lib/chat-message-time"
import { SharedChatComposerControls } from "@/components/gravitre/assistant/shared-chat-composer-controls"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"
import { useAgentVoicePlayback } from "@/hooks/use-agent-voice-playback"
import { getVoiceStatusDetailed } from "@/lib/tier1-voice-client"
import type { SpeechRecognitionStatus } from "@/lib/speech-recognition"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import {
  serializeInlineTurn,
  splitConversationMessages,
  type PersistedInlineTurn,
} from "@/lib/ai-inline-turn-persistence"
import { agentsApi, conversationsApi, searchApi, assistantApi, authApi } from "@/lib/api"
import {
  deriveConversationTitle,
  shouldRefreshConversationTitle,
} from "@/lib/conversation-title"
import { ApiError } from "@/lib/fetcher"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import type { SearchResult } from "@/types/api"
import { ChatTranscript } from "@/components/gravitre/assistant/chat-transcript"
import {
  ResearchScopePrompt,
  type ResearchCascadePayload,
} from "@/components/gravitre/assistant/research-scope-prompt"
import { ResearchCascadePanel } from "@/components/gravitre/assistant/research-cascade-panel"
import { ResearchPlanPanel } from "@/components/gravitre/assistant/research-plan-panel"
import { hostedFilesFromUnknown } from "@/components/gravitre/assistant/file-reference-chip"
import {
  shouldShowTaskSidePanel,
  TaskSidePanel,
} from "@/components/gravitre/assistant/task-side-panel"
import { ConversationSidebar } from "@/components/gravitre/assistant/conversation-sidebar"
import { ChatThemePicker } from "@/components/gravitre/assistant/chat-theme-picker"
import { ChatSessionControls } from "@/components/gravitre/assistant/chat-session-controls"
import { useChatBackground } from "@/hooks/use-chat-background"
import { Button } from "@/components/ui/button"
import { TOUCH_ICON_BUTTON } from "@/lib/design-system"
import { UserAccountAvatar } from "@/components/gravitre/user-account-avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { usePreferredPersona } from "@/hooks/use-preferred-persona"
import { resolveChatPersonaLabel } from "@/lib/chat-personas"
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
import {
  AI_VOICE_AGENT_DEFAULT,
  AiVoiceAgentPicker,
} from "./ai-voice-agent-picker"
import { voiceProfileIsConfigured } from "@/lib/voice-configure-gate"
import { AI_EXAMPLE_PROMPTS, AI_MODES, getModeMeta, type ModeId } from "./ai-mode-config"
import { ConnectedFilePickerDialog } from "./connected-file-picker-dialog"
import type { ConnectedFileAttachment } from "@/lib/connected-files-api"
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
import {
  isAuthoritativeMissingConversationError,
  shouldVerifyMissingConversation,
} from "@/lib/active-conversation-recovery"
import type { AdvisorBrief } from "@/components/gravitre/assistant/advisor-brief-panel"
import type { BusinessSignal } from "@/components/gravitre/assistant/business-signals-banner"

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
  /** Deep-link message id from /ai?c=&m= — scroll + brief highlight after hydrate. */
  initialMessageId?: string | null
}

function normalizeChatText(message: UIMessage): string {
  return uiMessageText(message)
}

export function AiWorkspace({
  initialMode = "auto",
  initialPrompt = "",
  initialConversationId = null,
  initialMessageId = null,
}: AiWorkspaceProps) {
  const { user } = useAuth()
  const { data: authMe } = useSWR(user ? "auth-me-chat-approver" : null, () => authApi.me())
  const canApproveWrites = (() => {
    const selectedId = getSelectedOrgFromStorage()?.id
    const orgs = (authMe as { organizations?: Array<{ id?: string; role?: string }> } | undefined)
      ?.organizations
    const matched = selectedId
      ? orgs?.find((org) => org.id === selectedId)?.role
      : undefined
    const role = (
      matched ||
      (authMe as { role?: string } | undefined)?.role ||
      authMe?.user?.role ||
      ""
    )
      .toString()
      .toLowerCase()
    return role === "admin" || role === "owner"
  })()
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
  const [voiceAgentId, setVoiceAgentId] = useState<string>(() => {
    if (typeof window === "undefined") return AI_VOICE_AGENT_DEFAULT
    return localStorage.getItem("gravitre_ai_voice_agent_id") || AI_VOICE_AGENT_DEFAULT
  })
  const { data: agentsData, isLoading: agentsLoading } = useSWR(
    user ? "ai-voice-agents" : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )
  const voiceAgents = agentsData?.agents ?? []
  // Spoken-voice pick only — must have a configured ElevenLabs profile.
  // Response style / transcript identity stay on preferredPersona.
  const selectedVoiceAgent = useMemo(() => {
    const match = voiceAgents.find((agent) => agent.id === voiceAgentId) ?? null
    if (!match || (match.status && match.status !== "active")) return null
    return voiceProfileIsConfigured(match.voiceProfile) ? match : null
  }, [voiceAgents, voiceAgentId])
  // Session identity for transcript + voice pills (You / persona). Avatar disc
  // stays the Gravitre mark on every surface — only the label differs.
  const assistantLabel = useMemo(
    () => resolveChatPersonaLabel(preferredPersona),
    [preferredPersona],
  )
  const handleVoiceAgentChange = useCallback((next: string) => {
    setVoiceAgentId(next)
    if (typeof window !== "undefined") {
      localStorage.setItem("gravitre_ai_voice_agent_id", next)
    }
  }, [])
  // Drop stale localStorage picks that are not voice-ready.
  useEffect(() => {
    if (voiceAgentId === AI_VOICE_AGENT_DEFAULT) return
    if (agentsLoading) return
    if (selectedVoiceAgent) return
    handleVoiceAgentChange(AI_VOICE_AGENT_DEFAULT)
  }, [voiceAgentId, agentsLoading, selectedVoiceAgent, handleVoiceAgentChange])
  const [conversationLoading, setConversationLoading] = useState(false)
  const [sessionBusy, setSessionBusy] = useState(false)
  // Seed from localStorage so conversation list/messages can start without waiting on orgs list().
  const [orgReady, setOrgReady] = useState(() => Boolean(typeof window !== "undefined" && getQuickOrgId()))
  const [threadRestoreStale, setThreadRestoreStale] = useState(false)
  const [messagesHydrated, setMessagesHydrated] = useState(false)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return initialConversationId || readStoredConversationId()
  })
  const cachePaintedForRef = useRef<string | null>(null)
  const apiRefreshNeededRef = useRef(false)
  const [conversationTitle, setConversationTitle] = useState("Chat")
  const [chatMode, setChatMode] = useState<"fast" | "deep">("fast")
  const { background: chatBackground, setBackground: setChatBackground } = useChatBackground()
  const [selectedDepartment, setSelectedDepartment] = useState(() =>
    typeof window === "undefined" ? "all" : getQuickDepartment(),
  )
  // Internal staff voice modality (same pipeline as agent chat) — not Twilio/Vapi telephony.
  const [modality, setModality] = useState<ChatModality>("text")
  const modalityRef = useRef<ChatModality>("text")
  const [voiceEntitled, setVoiceEntitled] = useState(true)
  const [voiceUnavailableReason, setVoiceUnavailableReason] = useState<string | undefined>()
  const [micStatus, setMicStatus] = useState<SpeechRecognitionStatus>("idle")
  const lastSpokenMessageIdRef = useRef<string | null>(null)
  const {
    isSpeaking: ttsSpeaking,
    billingIssue: voiceBilling,
    billingDetail: voiceBillingDetail,
    serviceError: voiceServiceError,
    serviceDetail: voiceServiceDetail,
    speak: speakAgentVoice,
    stop: stopAgentVoice,
    clearErrors: clearVoiceErrors,
  } = useAgentVoicePlayback()

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
  const [researchCascade, setResearchCascade] = useState<ResearchCascadePayload | null>(null)
  const [researchProgressSteps, setResearchProgressSteps] = useState<string[]>([])
  const notifications = useNotifications()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeConversationIdRef = useRef<string | null>(activeConversationId)
  const conversationTitleRef = useRef(conversationTitle)
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
  const researchScopeRef = useRef<string | null>(null)
  const lastUserPromptRef = useRef<string>("")
  const loadingMessagesForRef = useRef<string | null>(null)
  const messagesLoadResolvedRef = useRef<{ conversationId: string; resolved: boolean } | null>(null)
  const chatFirstTokenMarkedRef = useRef(false)
  const persistedTurnIdsRef = useRef<Set<string>>(new Set())
  const persistedChatPairIdsRef = useRef<Set<string>>(new Set())
  const missingConversationVerificationRef = useRef<string | null>(null)
  const connectedFileRefsRef = useRef<ConnectedFileAttachment[]>([])
  const [connectedFilePickerOpen, setConnectedFilePickerOpen] = useState(false)
  const [connectedFileAttachments, setConnectedFileAttachments] = useState<ConnectedFileAttachment[]>([])

  const activeMode = useMemo(() => getModeMeta(mode), [mode])

  /**
   * Hosted files for the task side panel's Outputs section. Reuses the existing
   * executionResult payload — no new fetch. Scoped to the active conversation
   * when the result declares one, so files from a prior task cannot leak into
   * the current panel.
   */
  const taskPanelHostedFiles = useMemo(() => {
    const structured = executionResult?.structured
    if (!structured) return []
    const resultConversationId = String(structured.conversationId || "").trim()
    if (resultConversationId && resultConversationId !== String(activeConversationId || "")) {
      return []
    }
    return hostedFilesFromUnknown(structured)
  }, [executionResult, activeConversationId])

  const [historySearch, setHistorySearch] = useState("")
  const deferredHistorySearch = useDeferredValue(historySearch.trim())
  const {
    data: conversationsData,
    error: conversationsError,
    isLoading: conversationsLoading,
    mutate: mutateConversations,
  } = useSWR(
    user && orgReady ? ["ai-conversations", deferredHistorySearch] : null,
    async () => {
      startChatPerf("conversation_list")
      try {
        return await conversationsApi.list({
          limit: 100,
          includeArchived: true,
          search: deferredHistorySearch || undefined,
        })
      } finally {
        endChatPerf("conversation_list")
      }
    },
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
          research_scope: researchScopeRef.current ?? undefined,
          connected_file_refs:
            connectedFileRefsRef.current.length > 0 ? connectedFileRefsRef.current : undefined,
          // Same spoken_mode path as agent chat → execute_task_streaming(spoken_mode=True).
          spoken_mode: modalityRef.current === "voice",
          surface: modalityRef.current === "voice" ? "voice" : "ai_chat",
        }),
      }),
    [chatMode, selectedDepartment],
  )

  useEffect(() => {
    if (!user) return
    let cancelled = false
    void getVoiceStatusDetailed(true)
      .then((result) => {
        if (cancelled) return
        if (result.blocked) {
          setVoiceEntitled(false)
          setVoiceUnavailableReason(result.reason)
          return
        }
        setVoiceEntitled(true)
        setVoiceUnavailableReason(undefined)
      })
      .catch(() => {
        if (!cancelled) setVoiceEntitled(true)
      })
    return () => {
      cancelled = true
    }
  }, [user])

  const { messages, sendMessage, status, setMessages, stop, regenerate } = useChat({
    transport,
    onError: (error) => {
      connectedFileRefsRef.current = []
      submitLockRef.current = false
      setSessionBusy(false)
      toast.error(parseChatError(error instanceof Error ? error : new Error(String(error))))
    },
    onFinish: ({ messages: finishedMessages }) => {
      connectedFileRefsRef.current = []
      submitLockRef.current = false
      setSessionBusy(false)
      // Stamp provisional created_at when missing so live bubbles show a time until hydrate.
      const stamped = finishedMessages.map((message) => {
        if (messageCreatedAt(message)) return message
        return {
          ...message,
          metadata: {
            ...(typeof message.metadata === "object" && message.metadata ? message.metadata : {}),
            created_at: new Date().toISOString(),
          },
        }
      })
      setMessages(stamped)
      const conversationId = activeConversationIdRef.current
      if (conversationId && stamped.length > 0) {
        writeCachedConversationMessages(conversationId, stamped)
      }
      void persistChatTurn(stamped)
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
        researchCascade?: ResearchCascadePayload
        progressSteps?: string[]
      }
      if (payload.dialogueMode) setDialogueMode(payload.dialogueMode)
      if (payload.pendingTask) setPendingTask(payload.pendingTask)
      if (payload.taskState) setTaskState(payload.taskState)
      if (payload.strategicPlan) setStrategicPlan(payload.strategicPlan)
      if (payload.advisorBrief) setAdvisorBrief(payload.advisorBrief)
      if (payload.explainability) setExplainability(payload.explainability)
      if (payload.contextExplanation) setContextExplanation(payload.contextExplanation)
      if (payload.executionGate) setExecutionGate(payload.executionGate)
      if (payload.researchCascade) setResearchCascade(payload.researchCascade)
      if (Array.isArray(payload.progressSteps) && payload.progressSteps.length > 0) {
        setResearchProgressSteps(payload.progressSteps)
      }
      if (Array.isArray(payload.businessSignals) && payload.businessSignals.length > 0) {
        setActiveBusinessSignals(payload.businessSignals)
      }
      if (payload.executionResult) {
        setExecutionResult(payload.executionResult)
        if (payload.executionResult.success && notifications) {
          const resultUrl = payload.executionResult.result_url ?? undefined
          notifications.addNotification({
            type: "task_complete",
            title: payload.executionResult.task_label || payload.executionResult.title || "Task completed",
            message:
              polishAssistantText(payload.executionResult.body || "") ||
              "Your request was executed in Gravitre.",
            link: resultUrl && resultUrl !== "/ai" ? resultUrl : "/runs",
          })
        }
      }
    },
  })

  // Side-rail intelligence is not on the chat critical path. Defer until the
  // shell is interactive so /business-signals + /advisor-brief (multi-second
  // backend fan-out) cannot contend with conversation list / composer mount.
  const [deferSideRailIntel, setDeferSideRailIntel] = useState(false)
  useEffect(() => {
    if (!user || !orgReady) {
      setDeferSideRailIntel(false)
      return
    }
    let cancelled = false
    const enable = () => {
      if (!cancelled) setDeferSideRailIntel(true)
    }
    let idleId: number | undefined
    if (typeof window !== "undefined" && "requestIdleCallback" in window) {
      idleId = window.requestIdleCallback(enable, { timeout: 2500 })
    }
    const timer = window.setTimeout(enable, 2500)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
      if (idleId != null && "cancelIdleCallback" in window) {
        window.cancelIdleCallback(idleId)
      }
    }
  }, [user, orgReady])

  const { data: businessSignalsPayload } = useSWR(
    deferSideRailIntel && user ? "ai-business-signals" : null,
    () => assistantApi.businessSignals(),
    { revalidateOnFocus: false },
  )

  const { data: advisorBriefPayload } = useSWR(
    deferSideRailIntel && user ? "ai-advisor-brief" : null,
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
        const userText = result.persisted_user_text || "Approved"
        const assistantText =
          result.persisted_assistant_text ||
          result.execution_result.body ||
          result.message ||
          "Done."
        const stamp = Date.now()
        setMessages((prev) => [
          ...prev,
          {
            id: `approve-user-${stamp}`,
            role: "user",
            parts: [{ type: "text", text: userText }],
            createdAt: new Date(stamp),
          } as (typeof prev)[number],
          {
            id: `approve-assistant-${stamp + 1}`,
            role: "assistant",
            parts: [{ type: "text", text: polishAssistantText(assistantText) || assistantText }],
            createdAt: new Date(stamp + 1),
          } as (typeof prev)[number],
        ])
        void mutateConversations()
        if (result.history_persisted === false) {
          toast.error("Action ran, but chat history failed to save. Refresh and verify the outcome card.")
        }
        if (result.execution_result.success && notifications) {
          const resultUrl = result.execution_result.result_url ?? undefined
          notifications.addNotification({
            type: "task_complete",
            title: result.execution_result.task_label || result.execution_result.title || "Task completed",
            message: result.execution_result.body || result.message,
            link: resultUrl && resultUrl !== "/ai" ? resultUrl : "/runs",
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
  }, [confirmExecuting, mutateConversations, notifications, setMessages])

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
    conversationTitleRef.current = conversationTitle
  }, [conversationTitle])

  useEffect(() => {
    if (!user) {
      setOrgReady(false)
      return
    }
    // Paint path: use stored org immediately; validate membership in background.
    if (getQuickOrgId()) setOrgReady(true)
    void ensureSelectedOrg(false).then((orgId) => setOrgReady(Boolean(orgId)))
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
    if (missingConversationVerificationRef.current === activeConversationId) {
      missingConversationVerificationRef.current = null
    }
  }, [activeConversationId, conversations])

  useEffect(() => {
    const hasConversationInList = Boolean(
      activeConversationId && conversations.some((conversation) => conversation.id === activeConversationId),
    )
    const shouldVerify = shouldVerifyMissingConversation({
      orgReady,
      activeConversationId,
      conversationsLoading,
      hasConversationInList,
      hasPendingConversation: Boolean(
        pendingConversationRef.current ||
          (activeConversationId && pendingConversationIdsRef.current.has(activeConversationId)),
      ),
      isSessionBusy: sessionBusyRef.current,
      chatStatus: chatStatusRef.current,
    })
    if (!shouldVerify || !activeConversationId) return
    if (missingConversationVerificationRef.current === activeConversationId) return

    const verificationId = activeConversationId
    missingConversationVerificationRef.current = verificationId
    let cancelled = false

    void conversationsApi
      .get(verificationId)
      .then((conversation) => {
        if (cancelled || activeConversationIdRef.current !== verificationId) return
        pendingConversationIdsRef.current.delete(verificationId)
        if (conversation.title) {
          setConversationTitle(conversation.title)
        }
        if (!deferredHistorySearch) {
          void mutateConversations(
            (current) => {
              if (!current) return { conversations: [conversation] }
              if (current.conversations.some((row) => row.id === conversation.id)) return current
              return {
                ...current,
                conversations: [conversation, ...current.conversations],
              }
            },
            { revalidate: false },
          )
        }
      })
      .catch((error) => {
        if (cancelled || activeConversationIdRef.current !== verificationId) return
        if (!isAuthoritativeMissingConversationError(error)) return
        writeStoredConversationId(null)
        setActiveConversationId(null)
        activeConversationIdRef.current = null
        setMessages([])
        setConversationTitle("Chat")
        setThreadRestoreStale(false)
        setMessagesHydrated(false)
      })
      .finally(() => {
        if (!cancelled && missingConversationVerificationRef.current === verificationId) {
          missingConversationVerificationRef.current = null
        }
      })

    return () => {
      cancelled = true
    }
  }, [
    orgReady,
    activeConversationId,
    conversations,
    conversationsLoading,
    deferredHistorySearch,
    mutateConversations,
    setMessages,
  ])

  useEffect(() => {
    // Keep auto-scroll inside the chat canvas so the history sidebar is not yanked.
    const canvas = document.querySelector(".ai-chat-canvas") as HTMLElement | null
    if (canvas) {
      canvas.scrollTo({ top: canvas.scrollHeight, behavior: "smooth" })
      return
    }
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" })
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

  const refreshConversationTitleIfNeeded = useCallback(
    (conversationId: string, prompt: string) => {
      const currentTitle = conversationTitleRef.current
      if (!shouldRefreshConversationTitle(currentTitle, prompt)) return
      const nextTitle = deriveConversationTitle(prompt)
      conversationTitleRef.current = nextTitle
      setConversationTitle(nextTitle)
      void conversationsApi
        .update(conversationId, { title: nextTitle })
        .then((updated) => {
          void mutateConversations(
            (current) => {
              if (!current) return current
              return {
                ...current,
                conversations: current.conversations.map((conversation) =>
                  conversation.id === conversationId
                    ? { ...conversation, title: updated.title || nextTitle }
                    : conversation,
                ),
              }
            },
            { revalidate: false },
          )
          void mutateConversations()
        })
        .catch(() => {
          // Title refresh is best-effort UX; never block the send path.
        })
    },
    [mutateConversations],
  )

  const ensureConversation = useCallback(
    async (title: string) => {
      const existingId = activeConversationIdRef.current
      // STA-308: reuse keeps the create-time title unless the new ask diverges.
      if (existingId) {
        refreshConversationTitleIfNeeded(existingId, title)
        return existingId
      }
      if (!pendingConversationRef.current) {
        const createTitle = deriveConversationTitle(title)
        const newId = crypto.randomUUID()
        pendingConversationRef.current = Promise.resolve(newId).finally(() => {
          pendingConversationRef.current = null
        })
        activeConversationIdRef.current = newId
        pendingConversationIdsRef.current.add(newId)
        setActiveConversationId(newId)
        setConversationTitle(createTitle)
        conversationTitleRef.current = createTitle
        writeStoredConversationId(newId)
        // Row is created on the backend when the first message persists — not here.
        return newId
      }
      return pendingConversationRef.current
    },
    [refreshConversationTitleIfNeeded],
  )

  const applyConversationMessages = useCallback(
    (
      id: string,
      generation: number,
      nextMessages: UIMessage[],
      options?: { allowEmpty?: boolean; replace?: boolean },
    ) => {
      if (messagesLoadGenerationRef.current !== generation) return
      if (activeConversationIdRef.current !== id) return

      setMessages((live) => {
        const chatBusy =
          chatStatusRef.current === "submitted" || chatStatusRef.current === "streaming"
        // Hard replace on conversation switch — but never wipe an in-flight turn.
        if (options?.replace) {
          if (chatBusy || sessionBusyRef.current) {
            return mergeTranscriptWithLiveMessages(nextMessages, live)
          }
          return nextMessages
        }
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

  // Paint bubbles from sessionStorage before org/API — cold tabs still wait on network.
  useEffect(() => {
    if (!activeConversationId) {
      cachePaintedForRef.current = null
      return
    }
    if (cachePaintedForRef.current === activeConversationId) return
    if (sessionBusyRef.current) return
    if (chatStatusRef.current === "submitted" || chatStatusRef.current === "streaming") return

    const cached = readCachedConversationMessages(activeConversationId)
    const cachedTurns = readCachedInlineTurns<InlineTurn>(activeConversationId)
    if (!cached?.length && !cachedTurns?.length) return

    cachePaintedForRef.current = activeConversationId
    apiRefreshNeededRef.current = true
    messagesLoadGenerationRef.current += 1
    const generation = messagesLoadGenerationRef.current
    if (cached?.length) {
      applyConversationMessages(activeConversationId, generation, cached, { replace: true })
    }
    if (cachedTurns?.length) setInlineTurns(cachedTurns)
    setMessagesHydrated(true)
    setConversationLoading(false)
  }, [activeConversationId, applyConversationMessages])

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
        const { messages: stored } = await conversationsApi.getMessages(conversationId, { limit: 80 })
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

      const orgId = await ensureSelectedOrg(false)
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

      const cached = readCachedConversationMessages(id)
      const cachedTurns = readCachedInlineTurns<InlineTurn>(id)
      const hasCache = Boolean(cached?.length || cachedTurns?.length)
      // Silent/background refresh when cache already painted — never blank the thread.
      const silentRefresh = Boolean(options?.silent || hasCache)
      if (!silentRefresh) {
        setMessagesHydrated(false)
        startChatPerf("conversation_load", id)
      } else {
        startChatPerf("conversation_load", id)
      }

      const showBlockingLoader = !silentRefresh
      let fetchedCount = cached?.length ?? 0
      let conversationMeta = conversations.find((conversation) => conversation.id === id) ?? null

      loadingMessagesForRef.current = id
      if (showBlockingLoader) {
        setConversationLoading(true)
        setThreadRestoreStale(false)
      }
      if (!silentRefresh) {
        setInlineTurns([])
      }
      if (hasCache && !options?.silent) {
        if (cached?.length && activeConversationIdRef.current === id) {
          applyConversationMessages(id, generation, cached, { replace: true })
        }
        if (cachedTurns?.length && activeConversationIdRef.current === id) setInlineTurns(cachedTurns)
        setMessagesHydrated(true)
      }

      try {
        const [messagesResponse, fetchedConversation] = await Promise.all([
          conversationsApi.getMessages(id, { limit: 80 }),
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
          applyConversationMessages(id, generation, uiMessages, { replace: true })
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
            if (cached?.length) applyConversationMessages(id, generation, cached, { replace: true })
            if (cachedTurns?.length) setInlineTurns(cachedTurns)
            setThreadRestoreStale(false)
            messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
          } else {
            applyConversationMessages(id, generation, [], { allowEmpty: true, replace: true })
            setInlineTurns([])
          }
        } else if (!cached?.length && !cachedTurns?.length) {
          applyConversationMessages(id, generation, [], { allowEmpty: true, replace: true })
          setInlineTurns([])
        }
      } catch (error) {
        if (activeConversationIdRef.current !== id) return
        if (messagesLoadGenerationRef.current !== generation) return
        if (cached?.length || cachedTurns?.length) {
          if (cached?.length) applyConversationMessages(id, generation, cached, { replace: true })
          if (cachedTurns?.length) setInlineTurns(cachedTurns)
          setThreadRestoreStale(false)
          messagesLoadResolvedRef.current = { conversationId: id, resolved: true }
        } else if (error instanceof ApiError && error.status === 404) {
          writeStoredConversationId(null)
          setActiveConversationId(null)
          activeConversationIdRef.current = null
          applyConversationMessages(id, generation, [], { allowEmpty: true, replace: true })
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
        endChatPerf("conversation_load", id)
        if (activeConversationIdRef.current === id) {
          setMessagesHydrated(true)
        }
        if (activeConversationIdRef.current === id) {
          apiRefreshNeededRef.current = false
          cachePaintedForRef.current = id
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
    async (prompt: string, attachments: ConnectedFileAttachment[] = []) => {
      submitLockRef.current = true
      sessionBusyRef.current = true
      setSessionBusy(true)
      chatFirstTokenMarkedRef.current = false
      startChatPerf("total_response")
      startChatPerf("first_token")
      lastUserPromptRef.current = prompt
      connectedFileRefsRef.current = attachments
      await ensureConversation(prompt)
      sendMessage({
        text: prompt,
        metadata: { created_at: new Date().toISOString() },
      })
    },
    [ensureConversation, sendMessage],
  )

  const handleEditResend = useCallback(
    (messageId: string, text: string) => {
      const idx = messages.findIndex((message) => message.id === messageId)
      if (idx < 0) return
      // Truncate local UI from the edited message; prior DB rows remain recoverable.
      setMessages(messages.slice(0, idx))
      void runChat(text.trim())
    },
    [messages, runChat, setMessages],
  )

  const handleCopyMessageText = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast.success("Copied")
    } catch {
      toast.error("Could not copy")
    }
  }, [])

  const handleCopyMessageLink = useCallback(
    async (messageId: string) => {
      if (!activeConversationId) return
      const url = `${window.location.origin}/ai?c=${encodeURIComponent(activeConversationId)}&m=${encodeURIComponent(messageId)}`
      try {
        await navigator.clipboard.writeText(url)
        toast.success("Link copied")
      } catch {
        toast.error("Could not copy link")
      }
    },
    [activeConversationId],
  )

  const handleRegenerateAssistant = useCallback(
    (assistantMessageId: string) => {
      const assistantIdx = messages.findIndex((message) => message.id === assistantMessageId)
      if (assistantIdx < 0) {
        toast.error("Nothing to regenerate")
        return
      }
      const hasPriorUser = messages.slice(0, assistantIdx).some((message) => message.role === "user")
      if (!hasPriorUser) {
        toast.error("Nothing to regenerate")
        return
      }
      submitLockRef.current = true
      setSessionBusy(true)
      chatFirstTokenMarkedRef.current = false
      startChatPerf("total_response")
      startChatPerf("first_token")
      // AI SDK regenerate keeps the prompting user turn and replaces the assistant reply.
      void regenerate({ messageId: assistantMessageId })
    },
    [messages, regenerate],
  )

  const handleSaveQuestion = useCallback(
    async (messageId: string, text: string) => {
      const questionText = text.trim()
      if (!questionText) return
      try {
        await conversationsApi.saveQuestion({
          question_text: questionText,
          conversation_id: activeConversationId,
          message_id: messageId,
        })
        toast.success("Question saved")
      } catch (error) {
        toast.error(error instanceof ApiError ? error.message : "Could not save question")
      }
    },
    [activeConversationId],
  )

  const handleResearchScopeSelect = useCallback(
    async (scope: string) => {
      researchScopeRef.current = scope
      setResearchCascade(null)
      setResearchProgressSteps([])
      const prompt = lastUserPromptRef.current.trim()
      if (!prompt) return
      await runChat(prompt)
    },
    [runChat],
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
      const attachments = connectedFileAttachments
      if ((!prompt && attachments.length === 0) || routing || submitLockRef.current) return
      if (!user) {
        toast.error("Sign in to use Chat")
        return
      }

      const effectivePrompt =
        prompt ||
        "Please read the attached connected file(s) and summarize the key points I should know."

      setSessionBusy(true)
      await ensureSelectedOrg()
      crossDepartmentRef.current = isCrossDepartmentPrompt(effectivePrompt)
      researchScopeRef.current = null
      setResearchCascade(null)
      setResearchProgressSteps([])
      await ensureConversation(effectivePrompt)
      const engine = await resolveEngine(effectivePrompt, mode)
      setInput("")
      setConnectedFileAttachments([])

      if (engine === "chat") {
        await runChat(effectivePrompt, attachments)
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
    [mode, resolveEngine, routing, runChat, runExecute, runFind, user, ensureConversation, connectedFileAttachments],
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

      const orgId = getQuickOrgId() || (await ensureSelectedOrg(false))
      if (!orgId) {
        toast.error("Organization context required", {
          description: "Select a workspace before opening conversations.",
        })
        return
      }
      setOrgReady(true)

      // Clear busy flags synchronously so apply/replace is never forced into merge.
      sessionBusyRef.current = false
      chatStatusRef.current = "ready"
      setSessionBusy(false)
      submitLockRef.current = false
      setSidebarOpen(false)
      stop()
      setThreadRestoreStale(false)
      setDialogueMode(null)
      setPendingTask(null)
      setExecutionResult(null)
      setExecutionGate(null)
      setTaskState(null)
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
      cachePaintedForRef.current = id
      // Drop previous thread, then paint cache in the same tick when available.
      if (cached?.length) {
        applyConversationMessages(id, generation, cached, { replace: true })
        setMessagesHydrated(true)
        apiRefreshNeededRef.current = true
      } else {
        setMessagesHydrated(false)
        applyConversationMessages(id, generation, [], { allowEmpty: true, replace: true })
      }
      setInlineTurns(cachedTurns ?? [])

      const selected = conversations.find((conversation) => conversation.id === id)
      if (selected?.title) setConversationTitle(selected.title)

      await loadConversationMessages(id, { force: true, silent: Boolean(cached?.length) })
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
    cachePaintedForRef.current = null
    apiRefreshNeededRef.current = false
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

  const handleUnarchiveConversation = useCallback(
    async (id: string) => {
      await conversationsApi.unarchive(id)
      void mutateConversations()
    },
    [mutateConversations],
  )

  const handlePinConversation = useCallback(
    async (id: string) => {
      await conversationsApi.pin(id)
      void mutateConversations()
    },
    [mutateConversations],
  )

  const handleUnpinConversation = useCallback(
    async (id: string) => {
      await conversationsApi.unpin(id)
      void mutateConversations()
    },
    [mutateConversations],
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
  const isStreaming = status === "streaming"

  // Auto-TTS after assistant reply in Voice modality — same /api/voice/tts as agent chat.
  useEffect(() => {
    if (modality !== "voice" || !voiceEntitled) return
    if (isChatBusy) return
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant")
    if (!lastAssistant) return
    if (lastSpokenMessageIdRef.current === lastAssistant.id) return
    const text = uiMessageText(lastAssistant).trim()
    if (!text) return
    lastSpokenMessageIdRef.current = lastAssistant.id
    void speakAgentVoice(text, {
      messageId: lastAssistant.id,
      agentId:
        voiceAgentId !== AI_VOICE_AGENT_DEFAULT && selectedVoiceAgent
          ? selectedVoiceAgent.id
          : undefined,
    })
  }, [
    modality,
    voiceEntitled,
    isChatBusy,
    messages,
    speakAgentVoice,
    voiceAgentId,
    selectedVoiceAgent,
  ])

  useEffect(() => {
    if (modality !== "voice") {
      stopAgentVoice()
      clearVoiceErrors()
      lastSpokenMessageIdRef.current = null
    }
  }, [modality, stopAgentVoice, clearVoiceErrors])

  // Live-floor chrome (11a/11b) only when Voice is armed or the mic/TTS owns
  // the floor — never treat ordinary Text streaming as "agent speaking".
  const voicePresence: VoicePresenceState =
    voiceBilling || voiceServiceError
      ? "error"
      : micStatus === "listening"
        ? "listening"
        : micStatus === "permission-denied" || micStatus === "audio-capture"
          ? "error"
          : ttsSpeaking || (modality === "voice" && isStreaming)
            ? "speaking"
            : "idle"
  const voicePresenceDetail = voiceBilling
    ? voiceBillingDetail
    : voiceServiceError
      ? voiceServiceDetail
      : undefined

  // Armed by the in-input waveform (no Text|Voice toggle). Once voice is used,
  // spoken_mode + auto-TTS stay on for the session; orb is presentation only.
  const handleModalityChange = useCallback(
    (next: ChatModality) => {
      setModality(next)
      modalityRef.current = next
      if (next === "text") {
        stopAgentVoice()
        clearVoiceErrors()
      }
    },
    [stopAgentVoice, clearVoiceErrors],
  )
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

  const deepLinkMessageHandledRef = useRef<string | null>(null)
  useEffect(() => {
    if (!initialMessageId || !messagesHydrated || conversationLoading) return
    if (deepLinkMessageHandledRef.current === initialMessageId) return
    if (!messages.some((message) => message.id === initialMessageId)) return
    deepLinkMessageHandledRef.current = initialMessageId
    const frame = window.requestAnimationFrame(() => {
      const el = document.getElementById(`msg-${initialMessageId}`)
      if (!el) return
      el.scrollIntoView({ behavior: "smooth", block: "center" })
      el.classList.add("ai-message-deep-link-target")
      window.setTimeout(() => {
        el.classList.remove("ai-message-deep-link-target")
      }, 2200)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [initialMessageId, messages, messagesHydrated, conversationLoading])

  useEffect(() => {
    if (!orgReady || !user || !activeConversationId || sessionBusy || isChatBusy || conversationLoading) {
      return
    }
    const alreadyResolved =
      messagesLoadResolvedRef.current?.conversationId === activeConversationId &&
      messagesLoadResolvedRef.current.resolved
    // Still refresh when cache painted early — otherwise stale sessionStorage sticks.
    if (alreadyResolved && !apiRefreshNeededRef.current) return
    if (
      !apiRefreshNeededRef.current &&
      (messages.length > 0 || inlineTurns.length > 0) &&
      alreadyResolved
    ) {
      return
    }
    void loadConversationMessages(activeConversationId, {
      silent: apiRefreshNeededRef.current || messages.length > 0 || inlineTurns.length > 0,
    })
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
    if (!activeConversationId || !messagesHydrated || messages.length === 0) return
    writeCachedConversationMessages(activeConversationId, messages)
  }, [activeConversationId, messages, messagesHydrated])

  useEffect(() => {
    if (!activeConversationId) return
    writeCachedInlineTurns(activeConversationId, inlineTurns)
  }, [activeConversationId, inlineTurns])

  const showLanding =
    !activeConversationId &&
    messages.length === 0 &&
    inlineTurns.length === 0 &&
    !isChatBusy &&
    !routing &&
    !initialPrompt.trim() &&
    !conversationLoading

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

  const lastMessage = messages[messages.length - 1]
  const lastAssistantEmpty =
    lastMessage?.role === "assistant" && !uiMessageText(lastMessage).trim()
  const showWaitingForReply =
    !showLanding &&
    !conversationLoading &&
    (sessionBusy || isChatBusy) &&
    messages.length > 0 &&
    !isStreaming &&
    (lastMessage?.role === "user" || lastAssistantEmpty)

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
        onUnarchive={(id) => void handleUnarchiveConversation(id)}
        onPin={(id) => void handlePinConversation(id)}
        onUnpin={(id) => void handleUnpinConversation(id)}
        onRename={(id, title) => void handleRenameConversation(id, title)}
        onBulkDelete={(ids) => void handleBulkDeleteConversations(ids)}
        isOpen={sidebarOpen}
        onToggle={() => {
          setSidebarOpen((open) => {
            const next = !open
            // Overlay viewports cannot host both drawers — Activity is also fixed.
            if (next) setActivityRailOpen(false)
            return next
          })
        }}
        isLoading={showConversationsSkeleton}
        loadError={showConversationsError ? conversationsError : undefined}
        onRetry={() => void mutateConversations()}
        searchQuery={historySearch}
        onSearchQueryChange={setHistorySearch}
      />

      <div className="ai-surface-shell ai-chat-surface flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="shrink-0 border-b border-[color:var(--chat-surface-border)] bg-[color:var(--chat-surface)]">
          {/* Primary header — handoff 5a/5b (desktop) / 4* top row (mobile) */}
          <div className="flex h-12 items-center gap-2.5 px-3.5 sm:h-[46px]">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => {
                setSidebarOpen((open) => {
                  const next = !open
                  if (next) setActivityRailOpen(false)
                  return next
                })
              }}
              className={cn(TOUCH_ICON_BUTTON, "shrink-0 text-[color:var(--chat-surface-muted)]")}
              aria-label={sidebarOpen ? "Hide history" : "Show history"}
            >
              {sidebarOpen ? <PanelLeftClose /> : <PanelLeft />}
            </Button>

            <div className="min-w-0 shrink">
              <p className="truncate text-[15px] font-bold sm:text-sm">Chat</p>
            </div>

            <span className="hidden shrink-0 text-[9px] font-medium uppercase tracking-[0.08em] text-[color:var(--chat-surface-muted)] md:inline">
              Answer · Search · Execute
            </span>

            <div className="ml-auto flex shrink-0 items-center gap-1 sm:gap-1.5">
              {/* Desktop chrome */}
              <ChatThemePicker
                value={chatBackground}
                onChange={setChatBackground}
                className={cn(TOUCH_ICON_BUTTON, "hidden sm:inline-flex")}
              />
              <a
                href="/ai/help/control"
                className={cn(
                  TOUCH_ICON_BUTTON,
                  "hidden items-center justify-center rounded-full border border-[color:var(--chat-surface-border)] text-[color:var(--chat-surface-muted)] hover:bg-black/[0.03] hover:text-foreground sm:inline-flex dark:hover:bg-white/[0.04]",
                )}
                title="How Gravitre keeps you in control"
                aria-label="How Gravitre keeps you in control"
              >
                <Info />
              </a>

              <div className="hidden sm:block">
                <ChatSessionControls
                  department={selectedDepartment}
                  onDepartmentChange={(value) => {
                    setSelectedDepartment(value)
                    setSelectedDepartmentInStorage(value)
                  }}
                  persona={preferredPersona}
                  onPersonaChange={handlePersonaChange}
                  personaDisabled={!user}
                  chatMode={chatMode}
                  onChatModeChange={setChatMode}
                />
              </div>

              <AiVoiceAgentPicker
                agents={voiceAgents}
                value={selectedVoiceAgent?.id ?? AI_VOICE_AGENT_DEFAULT}
                onChange={handleVoiceAgentChange}
                disabled={!user}
                loading={Boolean(user) && agentsLoading}
                className="hidden h-8 gap-1 px-2.5 text-[11px] sm:inline-flex"
              />

              <Button
                variant="ghost"
                size="icon"
                className={cn(
                  TOUCH_ICON_BUTTON,
                  "hidden shrink-0 text-muted-foreground sm:inline-flex",
                )}
                aria-label={activityRailOpen ? "Hide activity panel" : "Show activity panel"}
                onClick={() => {
                  setActivityRailOpen((open) => {
                    const next = !open
                    if (next) setSidebarOpen(false)
                    return next
                  })
                }}
              >
                <PanelRight className={cn(activityRailOpen && "text-primary")} />
              </Button>

              {/* Mobile overflow — theme / help / activity */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className={cn(TOUCH_ICON_BUTTON, "shrink-0 text-muted-foreground sm:hidden")}
                    aria-label="More chat options"
                  >
                    <MoreHorizontal />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="z-[70] w-52">
                  <DropdownMenuItem asChild>
                    <a href="/ai/help/control">How control works</a>
                  </DropdownMenuItem>
                  {!showLanding ? (
                    <DropdownMenuItem
                      onClick={() => {
                        setActivityRailOpen((open) => {
                          const next = !open
                          if (next) setSidebarOpen(false)
                          return next
                        })
                      }}
                    >
                      {activityRailOpen ? "Hide activity" : "Show activity"}
                    </DropdownMenuItem>
                  ) : null}
                </DropdownMenuContent>
              </DropdownMenu>

              <div className="sm:hidden">
                <UserAccountAvatar useCurrentUser size="sm" className="h-8 w-8" />
              </div>
            </div>
          </div>

          {/* Mobile session chips — handoff 4* second row (Modes / Tuners) */}
          <div className="flex items-center gap-1.5 overflow-x-auto border-t border-[color:var(--chat-surface-border)] px-3 py-2 sm:hidden">
            <ChatSessionControls
              department={selectedDepartment}
              onDepartmentChange={(value) => {
                setSelectedDepartment(value)
                setSelectedDepartmentInStorage(value)
              }}
              persona={preferredPersona}
              onPersonaChange={handlePersonaChange}
              personaDisabled={!user}
              chatMode={chatMode}
              onChatModeChange={setChatMode}
            />
            <AiVoiceAgentPicker
              agents={voiceAgents}
              value={selectedVoiceAgent?.id ?? AI_VOICE_AGENT_DEFAULT}
              onChange={handleVoiceAgentChange}
              disabled={!user}
              loading={Boolean(user) && agentsLoading}
              className="h-8 shrink-0 px-2.5 text-[11px]"
            />
            <div className="ml-auto shrink-0">
              <ChatThemePicker
                value={chatBackground}
                onChange={setChatBackground}
                className={TOUCH_ICON_BUTTON}
              />
            </div>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col">
        <div
          className="ai-chat-canvas min-h-0 flex-1 overflow-y-auto px-3 py-3 md:px-5 md:py-4"
          data-chat-bg={chatBackground}
        >
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
                onExampleSelect={(text) => void submitPrompt(text)}
                modality={modality}
                onModalityChange={handleModalityChange}
                voiceEntitled={voiceEntitled}
                voiceUnavailableReason={voiceUnavailableReason}
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
              <div className="flex items-start gap-4">
                <div className="min-w-0 flex-1">
                  <ResearchScopePrompt
                    cascade={researchCascade}
                    onSelectScope={(scope) => void handleResearchScopeSelect(scope)}
                    className="mb-4"
                  />
                  <ResearchPlanPanel
                    cascade={researchCascade}
                    progressSteps={researchProgressSteps}
                    strategicPlan={strategicPlan}
                    className="mb-4"
                  />
                  <ResearchCascadePanel cascade={researchCascade} className="mb-4" />
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
                    canApprove={canApproveWrites}
                    onEditResend={handleEditResend}
                    conversationId={activeConversationId}
                    onCopyText={(text) => void handleCopyMessageText(text)}
                    onCopyLink={(messageId) => void handleCopyMessageLink(messageId)}
                    onRegenerate={handleRegenerateAssistant}
                    onSaveQuestion={(messageId, text) => void handleSaveQuestion(messageId, text)}
                    assistantLabel={assistantLabel}
                    waitingLabel={`${assistantLabel} is thinking…`}
                  />
                </div>
                {shouldShowTaskSidePanel(researchProgressSteps, pendingTask) ? (
                  <TaskSidePanel
                    conversationId={activeConversationId}
                    progressSteps={researchProgressSteps}
                    pendingTask={pendingTask}
                    contextExplanation={contextExplanation}
                    hostedFiles={taskPanelHostedFiles}
                    className="sticky top-2 hidden lg:flex"
                  />
                ) : null}
              </div>
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
                  <div className={cn("max-w-[min(720px,92%)]", CHAT_BUBBLE_BASE_CLASS, CHAT_USER_BUBBLE_CLASS)}>
                    <p className="whitespace-pre-wrap">{turn.prompt}</p>
                    <p className="mt-1 text-[10px] uppercase tracking-wide text-muted-foreground">
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
        <div className="shrink-0 border-t border-[color:var(--chat-surface-border)] bg-[color:var(--chat-surface)] px-4 py-3 md:px-5">
          <div className="mx-auto w-full max-w-[920px]">
            {!showLanding && messages.length === 0 && inlineTurns.length === 0 && !isChatBusy ? (
              <div className="mb-3 flex flex-wrap justify-center gap-2">
                {AI_EXAMPLE_PROMPTS.slice(0, 4).map((example) => (
                  <button
                    key={example.text}
                    type="button"
                    onClick={() => void submitPrompt(example.text)}
                    className="rounded-full border border-[color:var(--chat-surface-border)] bg-white/80 px-3 py-1.5 text-center text-xs text-[color:var(--chat-surface-muted)] transition-all hover:border-[#16a374]/40 hover:text-foreground dark:bg-[#262626]"
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
              {connectedFileAttachments.length > 0 ? (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {connectedFileAttachments.map((file) => (
                    <span
                      key={`${file.vendor}-${file.file_id}`}
                      className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-[#16a374]/25 bg-white px-2.5 py-1 text-xs dark:bg-[#262626]"
                      title={
                        file.web_link
                          ? `${file.name} — stays in your connected account (read-only for this chat)`
                          : file.name
                      }
                    >
                      <FolderOpen className="h-3 w-3 shrink-0 text-[#16a374]" />
                      <span className="truncate">{file.name}</span>
                      <button
                        type="button"
                        className="text-[color:var(--chat-surface-muted)] hover:text-foreground"
                        aria-label={`Remove ${file.name}`}
                        onClick={() =>
                          setConnectedFileAttachments((prev) =>
                            prev.filter((f) => !(f.vendor === file.vendor && f.file_id === file.file_id)),
                          )
                        }
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}
              {/* SHARED_CHAT_COMPOSER_CONTROLS — in-input waveform + Browse + send. */}
              <SharedChatComposerControls
                modality={modality}
                onModalityChange={handleModalityChange}
                voiceEntitled={voiceEntitled}
                unavailableReason={voiceUnavailableReason}
                input={input}
                onInputChange={setInput}
                inputRef={inputRef}
                onKeyDown={onKeyDown}
                placeholder={
                  modality === "voice"
                    ? "Speak or type — replies play aloud…"
                    : "Ask, delegate, or search…"
                }
                textareaClassName={CHAT_COMPOSER_CLASS}
                disabled={routing || isChatBusy}
                isStreaming={isStreaming || ttsSpeaking}
                ttsSpeaking={ttsSpeaking}
                onStop={() => {
                  stop()
                  stopAgentVoice()
                }}
                canSubmit={Boolean(input.trim() || connectedFileAttachments.length > 0) && !routing && !isChatBusy}
                showSubmit
                onMicStatusChange={setMicStatus}
                voicePresence={voicePresence}
                voiceBilling={voiceBilling}
                voicePresenceDetail={voicePresenceDetail}
                agentLabel={assistantLabel}
                onVoiceInputError={(message) => {
                  if (message) toast.error(message)
                }}
                trailingExtras={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="mb-0.5 hidden h-8 w-8 shrink-0 rounded-full text-[color:var(--chat-surface-muted)] hover:bg-muted/60 hover:text-foreground sm:inline-flex"
                    disabled={routing || isChatBusy}
                    title="Browse connected cloud files (read-only — not uploaded to Gravitre)"
                    aria-label="Browse files"
                    onClick={() => setConnectedFilePickerOpen(true)}
                  >
                    <FolderOpen className="h-4 w-4" />
                  </Button>
                }
              />
            </form>
          </div>
        </div>
        ) : null}
        </div>
      </div>

      {activityRailOpen ? (
      <>
        {/* Mobile/tablet scrim — tap to dismiss the overlay drawer. */}
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm xl:hidden"
          onClick={() => setActivityRailOpen(false)}
          aria-hidden
        />
        <LiveActivityRail
          advisorBrief={advisorBrief}
          onClose={() => setActivityRailOpen(false)}
        />
      </>
      ) : null}
      <ConnectedFilePickerDialog
        open={connectedFilePickerOpen}
        onOpenChange={setConnectedFilePickerOpen}
        selected={connectedFileAttachments}
        onConfirm={(files) => setConnectedFileAttachments(files)}
      />
    </div>
  )
}
