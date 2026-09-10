"use client"

import { useEffect, useRef, useState, use, useMemo, useCallback } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { ensureSelectedOrg, buildChatOrgPayload, getSelectedOrgFromStorage } from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import { parseChatError } from "@/lib/chat-errors"
import { motion } from "framer-motion"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  MessageSquarePlus,
  Database,
  ChevronDown,
  ChevronUp,
  FolderOpen,
} from "lucide-react"
import { CenteredLoader } from "@/components/gravitre/gravitre-loader"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { cn } from "@/lib/utils"
import { CHAT_COMPOSER_CLASS } from "@/lib/chat-typography"
import { Button } from "@/components/ui/button"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { toast } from "sonner"
import type { VoicePresenceState } from "@/components/gravitre/assistant/voice-session-presence"
import type { SpeechRecognitionStatus } from "@/lib/speech-recognition"
import type { ChatModality } from "@/components/gravitre/assistant/voice-mode-toggle"
import { getVoiceStatusDetailed, type VoiceStatus } from "@/lib/tier1-voice-client"
import type { Agent } from "@/types/api"
import { agentsApi, assistantApi, authApi } from "@/lib/api"
import { PersonaSelector } from "@/components/gravitre/assistant/persona-selector"
import { usePreferredPersona } from "@/hooks/use-preferred-persona"
import { useAgentVoicePlayback } from "@/hooks/use-agent-voice-playback"
import { useVoiceDuplexSession } from "@/hooks/use-voice-duplex-session"
import { buildDuplexControls } from "@/lib/voice-duplex-controls"
import { VoiceMicSettingsPopover } from "@/components/gravitre/assistant/voice-mic-settings-popover"
import type { MicFieldProfile } from "@/lib/voice-mic-devices"
import {
  GravitreAIConversationComposer,
  GravitreAIConversationTranscript,
} from "@/components/gravitre/ai-conversation-core"
import { ChatThemePicker } from "@/components/gravitre/assistant/chat-theme-picker"
import { useChatBackground } from "@/hooks/use-chat-background"
import { uiMessageText } from "@/lib/chat-messages"
import { deriveAgentStatusLabel, shouldHideProgressPanel } from "@/lib/chat-agent-status"
import { ResearchPlanPanel } from "@/components/gravitre/assistant/research-plan-panel"
import {
  type ChatExecutionResult,
  type ChatPendingTask,
} from "@/components/gravitre/assistant/chat-execution-panel"
import { ConnectedFilePickerDialog } from "@/app/ai/_components/connected-file-picker-dialog"
import type { ConnectedFileAttachment } from "@/lib/connected-files-api"

const getStorageKey = (agentId: string) => `gravitre_agent_chat_${agentId}`
const AGENT_CHAT_HEADER_COLLAPSED_KEY = "gravitre:agent-chat-header-collapsed"

function getAgentSuggestions(agent: Agent): string[] {
  const role = `${agent.role || ""} ${agent.department || ""}`.toLowerCase()
  if (role.includes("market")) {
    return [
      "What campaigns should we prioritize this quarter?",
      "Draft a segment summary for our ICP.",
      "Which channels drove the most pipeline last month?",
      "What content gaps should we fill next?",
    ]
  }
  if (role.includes("sales") || role.includes("revenue") || role.includes("revops")) {
    return [
      "Which deals are at risk this week?",
      "Summarize pipeline hygiene issues.",
      "What are the top next-best actions for open opportunities?",
      "Flag stale opportunities needing follow-up.",
    ]
  }
  if (role.includes("success") || role.includes("support") || role.includes("cs")) {
    return [
      "Which accounts show churn risk signals?",
      "Summarize open tickets blocking adoption.",
      "Draft a proactive check-in for at-risk accounts.",
      "What SLA risks should we address today?",
    ]
  }
  if (role.includes("finance") || role.includes("billing")) {
    return [
      "Are there invoice or collections anomalies?",
      "Summarize billing vs CRM discrepancies.",
      "Which accounts have overdue balances?",
      "What revenue recognition flags need review?",
    ]
  }
  if (role.includes("devops") || role.includes("sre") || role.includes("engineer")) {
    return [
      "Summarize active incidents and severity.",
      "What changed in the last 24 hours that could affect reliability?",
      "Recommend mitigations for the top alert.",
      "Draft a customer status update for ongoing incident.",
    ]
  }
  return [
    "What can you help me with?",
    "What are you currently working on?",
    "Summarize recent results for this org.",
    "What tools and integrations do you have access to?",
  ]
}

export default function AgentChatPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: agentId } = use(params)
  const searchParams = useSearchParams()
  // QA-only: ?qaForceVoiceError=billing — backend ignores unless QA hooks enabled.
  const qaForceVoiceError = (searchParams.get("qaForceVoiceError") || "").trim() || null
  const { user } = useAuth()
  const { data: authMe } = useSWR(user ? "auth-me-agent-chat-approver" : null, () => authApi.me())
  // Same admin/owner-role gate ChatExecutionPanel uses on /ai (approval-batch-panel.tsx
  // pattern) — parity fix, not new capability: reuses the existing role check verbatim.
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
  const { preferredPersona, handlePersonaChange, syncPersona } = usePreferredPersona({
    enabled: Boolean(user),
  })
  const { background: chatBackground, setBackground: setChatBackground } = useChatBackground()
  const [input, setInput] = useState("")
  const [modality, setModality] = useState<ChatModality>("text")
  const [micDeviceId, setMicDeviceId] = useState<string | null>(null)
  const [micProfileOverride, setMicProfileOverride] = useState<MicFieldProfile>("auto")
  const [voiceStatusSnapshot, setVoiceStatusSnapshot] = useState<VoiceStatus | null>(null)
  const modalityRef = useRef<ChatModality>("text")
  const [voiceEntitled, setVoiceEntitled] = useState(true)
  const [voiceUnavailableReason, setVoiceUnavailableReason] = useState<string | undefined>(undefined)
  // Mirrored from the mic button so the presence strip shows the real recognition
  // state. Presentation only — the button remains the owner of the session.
  const [micStatus, setMicStatus] = useState<SpeechRecognitionStatus>("idle")
  const [duplexVoiceError, setDuplexVoiceError] = useState<string | undefined>(undefined)
  // Parity fix (approved Phase 1 scope — see docs/delivery/ai-agent-floating-workspace-architecture-2026-09-07.md
  // Part B2 open decision #1): agent chat previously wired NO approval/execution-panel/
  // file-picker props at all (confirmed absent before this change — no onData handler,
  // no ChatExecutionPanel props, no ConnectedFilePickerDialog). This conversation id is
  // generated client-side and only used to let the existing, shared /api/chat +
  // /api/assistant/conversation/{id}/execute endpoints (already used by /ai, unchanged
  // here) track a pending task for this session — no backend contract change.
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  const activeConversationIdRef = useRef<string | null>(null)
  const [dialogueMode, setDialogueMode] = useState<string | null>(null)
  const [pendingTask, setPendingTask] = useState<ChatPendingTask | null>(null)
  const [executionResult, setExecutionResult] = useState<ChatExecutionResult | null>(null)
  const [confirmExecuting, setConfirmExecuting] = useState(false)
  const [researchProgressSteps, setResearchProgressSteps] = useState<string[]>([])
  const [agentStatusExplanation, setAgentStatusExplanation] = useState<string | null>(null)
  const [agentUserStatusLabel, setAgentUserStatusLabel] = useState<string | null>(null)
  const [connectedIntegrations, setConnectedIntegrations] = useState<string[]>([])
  const connectedFileRefsRef = useRef<ConnectedFileAttachment[]>([])
  const [connectedFilePickerOpen, setConnectedFilePickerOpen] = useState(false)
  const [connectedFileAttachments, setConnectedFileAttachments] = useState<ConnectedFileAttachment[]>([])
  const [headerCollapsed, setHeaderCollapsed] = useState(() => {
    if (typeof window === "undefined") return false
    return window.localStorage.getItem(AGENT_CHAT_HEADER_COLLAPSED_KEY) === "1"
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
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
    // Separate blocked-autoplay signal from the "read typed reply aloud" TTS
    // path — distinct from voiceDuplex's own gate. Combined below into the
    // single playbackBlocked/resumeBlockedPlayback pair the composer reads.
    playbackBlocked: agentVoicePlaybackBlocked,
    resumeBlockedPlayback: resumeAgentVoicePlayback,
  } = useAgentVoicePlayback()

  const { data: agent, isLoading: agentLoading } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId),
  )

  // Agent profile response style wins for this chat surface when configured.
  useEffect(() => {
    if (!agent?.responseStyle) return
    syncPersona(agent.responseStyle)
  }, [agent?.id, agent?.responseStyle, syncPersona])

  const toggleHeaderCollapsed = () => {
    setHeaderCollapsed((collapsed) => {
      const next = !collapsed
      window.localStorage.setItem(AGENT_CHAT_HEADER_COLLAPSED_KEY, next ? "1" : "0")
      return next
    })
  }

  const [initialMessages] = useState<UIMessage[]>(() => {
    if (typeof window === "undefined") return []
    try {
      const stored = localStorage.getItem(getStorageKey(agentId))
      if (stored) return JSON.parse(stored) as UIMessage[]
    } catch {
      // Ignore parse errors
    }
    return []
  })

  useEffect(() => {
    if (user) void ensureSelectedOrg(true)
  }, [user])

  useEffect(() => {
    modalityRef.current = modality
  }, [modality])


  useEffect(() => {
    if (!user) return
    void getVoiceStatusDetailed(true)
      .then((result) => {
        if (result.blocked) {
          setVoiceEntitled(false)
          setVoiceUnavailableReason(result.reason)
          return
        }
        if (!result.status) {
          // Transient miss — plan-included default stays available; avoid false lock.
          setVoiceEntitled(true)
          setVoiceUnavailableReason(undefined)
          return
        }
        setVoiceEntitled(true)
        setVoiceUnavailableReason(undefined)
        if (result.status) setVoiceStatusSnapshot(result.status)
      })
      .catch(() => {
        // Network blip: do not permanently hide Voice for plan-included orgs.
        setVoiceEntitled(true)
      })
  }, [user])

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
          agent_id: agentId,
          mode: "agent",
          // Phase 1: do not ship a hardcoded tool list — backend resolves agent
          // systems/tools via resolve_permitted_tools (same as unified LIVE).
          preferred_persona: agent?.responseStyle || preferredPersona,
          // Same conversation + Module B memory; spoken_mode stacks SPOKEN register.
          spoken_mode: modalityRef.current === "voice",
          surface: modalityRef.current === "voice" ? "voice" : "agent_chat",
          // Parity fix: conversation_id + connected_file_refs are the same,
          // already-generic /api/chat fields /ai sends (assistant.py's
          // AssistantChatRequest treats conversation_id and agent_id as
          // independent optional fields) — enables approvals/execution here too.
          conversation_id: activeConversationIdRef.current,
          connected_file_refs:
            connectedFileRefsRef.current.length > 0 ? connectedFileRefsRef.current : undefined,
        }),
      }),
    [agentId, preferredPersona, agent?.responseStyle],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    messages: initialMessages,
    onError: (error) => {
      console.error("[v0] Agent chat error:", error)
      connectedFileRefsRef.current = []
      toast.error(parseChatError(error))
    },
    onFinish: () => {
      connectedFileRefsRef.current = []
    },
    onData: (dataPart) => {
      if (dataPart.type !== "data-intelligence" || !dataPart.data || typeof dataPart.data !== "object") {
        return
      }
      const payload = dataPart.data as {
        dialogueMode?: string
        executionResult?: ChatExecutionResult
        pendingTask?: ChatPendingTask
        progressSteps?: string[]
        answerExplanation?: string
        userStatus?: { label?: string | null }
        connectedIntegrations?: string[]
      }
      if (payload.dialogueMode) setDialogueMode(payload.dialogueMode)
      if (payload.pendingTask) setPendingTask(payload.pendingTask)
      if (payload.executionResult) setExecutionResult(payload.executionResult)
      if (Array.isArray(payload.progressSteps) && payload.progressSteps.length > 0) {
        setResearchProgressSteps(payload.progressSteps)
      }
      if (typeof payload.answerExplanation === "string" && payload.answerExplanation.trim()) {
        setAgentStatusExplanation(payload.answerExplanation.trim())
      }
      if (typeof payload.userStatus?.label === "string" && payload.userStatus.label.trim()) {
        setAgentUserStatusLabel(payload.userStatus.label.trim())
      }
      if (Array.isArray(payload.connectedIntegrations) && payload.connectedIntegrations.length > 0) {
        setConnectedIntegrations(payload.connectedIntegrations.map((item) => String(item)))
      }
    },
  })

  const ensureAgentConversation = useCallback(() => {
    if (activeConversationIdRef.current) return activeConversationIdRef.current
    const newId = crypto.randomUUID()
    activeConversationIdRef.current = newId
    setActiveConversationId(newId)
    return newId
  }, [])

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
          result.persisted_assistant_text || result.execution_result.body || result.message || "Done."
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
            parts: [{ type: "text", text: assistantText }],
            createdAt: new Date(stamp + 1),
          } as (typeof prev)[number],
        ])
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
  }, [confirmExecuting, setMessages])

  const handleRejectExecution = useCallback(() => {
    setDialogueMode(null)
    setPendingTask(null)
    sendMessage({ text: "no" })
  }, [sendMessage])

  const handleModifyExecution = useCallback(() => {
    setInput("I'd like to change: ")
    toast.message("Tell me what to change in the composer, then send.")
  }, [])

  const isLoading = status === "submitted" || status === "streaming"
  const isStreaming = status === "streaming"

  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const voiceDuplex = useVoiceDuplexSession({
    enabled: voiceEntitled,
    agentId,
    micDeviceId,
    micProfileOverride,
    getHistory: () =>
      messagesRef.current.slice(-24).map((m) => ({
        role: m.role,
        content: uiMessageText(m),
      })),
    onUserFinal: (_text) => {
      modalityRef.current = "voice"
      setModality("voice")
      setDuplexVoiceError(undefined)
    },
    onTurnComplete: (result) => {
      if (result.cancelled && !result.assistantText.trim()) return
      setDuplexVoiceError(undefined)
      const stamp = Date.now()
      const spokeDuringTurn = typeof result.latency?.session_ttfa_ms === "number"
      setMessages((prev) => {
        const next = [
          ...prev,
          {
            id: `voice-user-${result.turnId || stamp}`,
            role: "user" as const,
            parts: [{ type: "text" as const, text: result.userText }],
          } as (typeof prev)[number],
        ]
        if (result.assistantText.trim()) {
          next.push({
            id: `voice-assistant-${result.turnId || stamp}`,
            role: "assistant" as const,
            parts: [{ type: "text" as const, text: result.assistantText }],
          } as (typeof prev)[number])
          lastSpokenMessageIdRef.current =
            spokeDuringTurn && !result.cancelled
              ? `voice-assistant-${result.turnId || stamp}`
              : null
        }
        return next
      })
    },
    onError: (message) => {
      setDuplexVoiceError(message)
      if (!/playback.+blocked/i.test(message)) {
        toast.error(message)
      }
    },
  })

  // Auto-TTS after assistant reply completes — same /api/voice/tts pipeline as /ai Read aloud.
  // Skip when full-duplex session already streamed progressive TTS.
  useEffect(() => {
    if (modality !== "voice" || !voiceEntitled) return
    if (voiceDuplex.isActive) return
    if (isLoading || isStreaming) return
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant")
    if (!lastAssistant) return
    if (lastSpokenMessageIdRef.current === lastAssistant.id) return
    const text = uiMessageText(lastAssistant).trim()
    if (!text) return
    lastSpokenMessageIdRef.current = lastAssistant.id
    void speakAgentVoice(text, {
      messageId: lastAssistant.id,
      agentId,
      qaForceError: qaForceVoiceError,
    })
  }, [
    modality,
    voiceEntitled,
    isLoading,
    isStreaming,
    messages,
    agentId,
    qaForceVoiceError,
    speakAgentVoice,
    voiceDuplex.isActive,
  ])

  const stopDuplex = voiceDuplex.stop
  const duplexIsActive = voiceDuplex.isActive
  useEffect(() => {
    if (modality !== "voice") {
      stopAgentVoice()
      clearVoiceErrors()
      setDuplexVoiceError(undefined)
      lastSpokenMessageIdRef.current = null
      if (duplexIsActive) stopDuplex()
    }
  }, [modality, stopAgentVoice, clearVoiceErrors, duplexIsActive, stopDuplex])

  // Live-floor chrome only when Voice is armed or mic/TTS owns the floor.
  const voicePresence: VoicePresenceState =
    voiceBilling || voiceServiceError || Boolean(duplexVoiceError)
      ? "error"
      : voiceDuplex.isActive || voiceDuplex.presence !== "idle"
        ? voiceDuplex.presence
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
      : duplexVoiceError
        ? duplexVoiceError
      : undefined
  const hasSentMessage = messages.some((m) => m.role === "user")

  const activeToolName = useMemo(() => {
    const lastAssistant = [...messages].reverse().find((row) => row.role === "assistant")
    if (!lastAssistant?.parts) return null
    for (const part of lastAssistant.parts) {
      const row = part as { type?: string; toolName?: string; state?: string }
      if (!row.type?.startsWith("tool-") && row.type !== "dynamic-tool") continue
      if (row.state === "output-available") continue
      return row.toolName || row.type?.replace(/^tool-/, "") || null
    }
    return null
  }, [messages])

  const agentStatusLabel = useMemo(
    () =>
      deriveAgentStatusLabel({
        assistantLabel: agent?.name || "Gravitre",
        activeToolName,
        progressSteps: researchProgressSteps,
        answerExplanation: agentStatusExplanation,
        userStatusLabel: agentUserStatusLabel,
        pendingTask,
        connectedIntegrations,
        isStreaming,
        isBusy: isLoading,
      }),
    [
      agent?.name,
      activeToolName,
      researchProgressSteps,
      agentStatusExplanation,
      agentUserStatusLabel,
      pendingTask,
      connectedIntegrations,
      isStreaming,
      isLoading,
    ],
  )

  const lastMessage = messages[messages.length - 1]
  const lastAssistantEmpty =
    lastMessage?.role === "assistant" && !uiMessageText(lastMessage).trim()
  const showWaitingForReply =
    isLoading && messages.length > 0 && (lastMessage?.role === "user" || lastAssistantEmpty)

  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(getStorageKey(agentId), JSON.stringify(messages.slice(-50)))
      } catch {
        // Ignore storage errors
      }
    }
  }, [messages, agentId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, status])

  const handleNewConversation = useCallback(() => {
    setMessages([])
    localStorage.removeItem(getStorageKey(agentId))
    activeConversationIdRef.current = null
    setActiveConversationId(null)
    setDialogueMode(null)
    setPendingTask(null)
    setExecutionResult(null)
    setConnectedFileAttachments([])
    inputRef.current?.focus()
  }, [setMessages, agentId])

  const handleRegenerate = useCallback(
    (assistantMessageId: string) => {
      const idx = messages.findIndex((m) => m.id === assistantMessageId)
      if (idx < 0) return
      const lastUserMessage = [...messages.slice(0, idx)].reverse().find((m) => m.role === "user")
      if (!lastUserMessage) return
      setMessages(messages.slice(0, idx))
      const text = uiMessageText(lastUserMessage)
      if (text) sendMessage({ text })
    },
    [messages, setMessages, sendMessage],
  )

  const submitText = (text: string) => {
    const trimmed = text.trim()
    if ((!trimmed && connectedFileAttachments.length === 0) || isLoading) return
    ensureAgentConversation()
    connectedFileRefsRef.current = connectedFileAttachments
    setConnectedFileAttachments([])
    sendMessage({
      text:
        trimmed ||
        "Please read the attached connected file(s) and summarize the key points I should know.",
    })
    setInput("")
  }

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submitText(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submitText(input)
    }
  }

  if (agentLoading && !agent) {
    return (
      <AppShell title="Agent chat">
        <CenteredLoader size="md" label="Loading agent chat" fill="parent" />
      </AppShell>
    )
  }

  if (!agent) {
    return (
      <AppShell title="Agent chat">
        <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-sm text-muted-foreground">Agent not found or you don&apos;t have access.</p>
          <Link href="/agents">
            <Button variant="outline" size="sm">
              Back to AI Team
            </Button>
          </Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Chat">
      <div className="ai-surface-shell ai-chat-surface flex h-full min-h-0 min-w-0 flex-1 flex-col">
        <div className="flex h-9 shrink-0 items-center gap-2 border-b border-divide bg-[color:var(--chat-surface,var(--g-canvas))] px-3 md:px-4">
          {!headerCollapsed ? (
            <>
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <AgentIdentityAvatar agent={agent} size="sm" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">{agent.name}</p>
                  <p className="truncate text-[11px] text-muted-foreground">
                    {agent.role}
                    {agent.description ? ` — ${agent.description}` : ""}
                  </p>
                </div>
                <span
                  className={cn(
                    "ml-1 hidden h-1.5 w-1.5 shrink-0 rounded-full sm:inline-block",
                    agent.status === "active"
                      ? "bg-[color:var(--status-verified)]"
                      : "bg-[color:var(--status-pending)]",
                  )}
                  title={agent.status}
                />
              </div>
              <div className="flex items-center gap-1.5">
                <PersonaSelector
                  value={preferredPersona}
                  onChange={handlePersonaChange}
                  disabled={!user}
                  surface="light"
                  label="Response style"
                />
                <ChatThemePicker value={chatBackground} onChange={setChatBackground} />
                <Link href={`/agents/${agentId}/knowledge`}>
                  <Button variant="ghost" size="sm" className="h-7 gap-1.5 px-2 text-xs">
                    <Database className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Knowledge</span>
                  </Button>
                </Link>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleNewConversation}
                  className="h-7 gap-1.5 px-2 text-xs"
                >
                  <MessageSquarePlus className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">New</span>
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={toggleHeaderCollapsed}
                  aria-label="Collapse agent header"
                  className="h-7 w-7"
                >
                  <ChevronUp className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="flex min-w-0 flex-1 items-center gap-2">
                <AgentIdentityAvatar agent={agent} size="sm" />
                <p className="truncate text-sm font-semibold text-foreground">{agent.name}</p>
                <span className="text-[11px] capitalize text-muted-foreground">{agent.status}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <PersonaSelector
                  value={preferredPersona}
                  onChange={handlePersonaChange}
                  disabled={!user}
                  surface="light"
                  label="Response style"
                />
                <ChatThemePicker value={chatBackground} onChange={setChatBackground} />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={toggleHeaderCollapsed}
                  aria-label="Expand agent header"
                  className="h-7 w-7"
                >
                  <ChevronDown className="h-3.5 w-3.5" />
                </Button>
              </div>
            </>
          )}
        </div>

        <div
          className="ai-chat-canvas min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-3 md:px-5 md:py-4"
          data-chat-bg={chatBackground}
        >
          <div className="ai-chat-canvas-inner mx-auto w-full max-w-[880px]">
          {!hasSentMessage ? (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              className="mx-auto flex h-full max-w-[880px] flex-col items-center justify-center px-2 text-center"
            >
            <AgentIdentityAvatar agent={agent} size="lg" className="mb-5" />
              <h2 className="mb-1.5 text-xl font-semibold text-foreground">Chat with {agent.name}</h2>
              <p className="mb-8 max-w-md text-sm text-muted-foreground">
                {agent.description ||
                  `Ask ${agent.name} anything about their capabilities and expertise.`}
              </p>
              <div className="grid max-w-lg grid-cols-2 gap-2">
                {getAgentSuggestions(agent).map((suggestion, i) => (
                  <motion.button
                    key={suggestion}
                    type="button"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 + i * 0.05 }}
                    onClick={() => submitText(suggestion)}
                    className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] px-3 py-2.5 text-left text-xs text-muted-foreground shadow-[var(--np-shadow)] transition-all hover:border-[color:var(--g-brand-border)] hover:bg-[color:var(--g-brand-soft)] hover:text-foreground"
                  >
                    {suggestion}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          ) : (
            <>
              {!shouldHideProgressPanel(researchProgressSteps, pendingTask) ? (
                <ResearchPlanPanel
                  cascade={null}
                  progressSteps={researchProgressSteps}
                  pendingTask={pendingTask}
                  className="mb-4"
                />
              ) : null}
              <GravitreAIConversationTranscript
                routeKey="/agents/[id]/chat"
                messages={messages}
                showWaiting={showWaitingForReply}
                isStreaming={isLoading}
                status={status}
                isBusy={isLoading}
                agentStatusLabel={agentStatusLabel}
                assistantLabel={agent.name}
                waitingLabel={agentStatusLabel}
                dialogueMode={dialogueMode}
                executionResult={executionResult}
                pendingTask={pendingTask}
                confirmExecuting={confirmExecuting}
                onConfirmExecution={() => void handleConfirmExecution()}
                onRejectExecution={handleRejectExecution}
                onModifyExecution={handleModifyExecution}
                canApprove={canApproveWrites}
                conversationId={activeConversationId}
                onRegenerate={handleRegenerate}
                onCopyText={(text) => {
                  void navigator.clipboard.writeText(text)
                  toast.success("Message copied")
                }}
              />
              <div ref={messagesEndRef} />
            </>
          )}
          </div>
        </div>

        <div className="shrink-0 border-t border-[color:var(--chat-surface-border)] bg-[color:var(--chat-surface)] px-3 py-2 md:px-5 md:py-3">
          <form onSubmit={onSubmit} className="mx-auto w-full max-w-[920px]">
            {connectedFileAttachments.length > 0 ? (
              <div className="mb-2 flex flex-wrap gap-1.5">
                {connectedFileAttachments.map((file) => (
                  <span
                    key={`${file.vendor}-${file.file_id}`}
                    className="inline-flex max-w-full items-center gap-1.5 rounded-[var(--np-radius-md)] border border-[color:var(--g-brand-border)] bg-[color:var(--g-surface-1)] px-2.5 py-1 text-xs shadow-[var(--np-shadow)]"
                    title={
                      file.web_link
                        ? `${file.name} — stays in your connected account (read-only for this chat)`
                        : file.name
                    }
                  >
                    <FolderOpen className="h-3 w-3 shrink-0 text-[color:var(--g-brand)]" />
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
            <GravitreAIConversationComposer
              modality={modality}
              onModalityChange={(next) => {
                setModality(next)
                modalityRef.current = next
                if (next === "text") {
                  stopAgentVoice()
                  clearVoiceErrors()
                  setDuplexVoiceError(undefined)
                }
              }}
              voiceEntitled={voiceEntitled}
              unavailableReason={voiceUnavailableReason}
              // Real agent name, so the orb / pill read the agent rather than
              // the generic Gravitre default used by main chat.
              agentLabel={agent?.name || "Gravitre"}
              activityLabel={agentStatusLabel}
              input={input}
              onInputChange={setInput}
              inputRef={inputRef}
              onKeyDown={handleKeyDown}
              placeholder={user ? `Message ${agent.name}…` : "Sign in to chat"}
              textareaClassName={cn(
                "max-h-[160px] min-h-[44px] placeholder:text-muted-foreground/70",
                CHAT_COMPOSER_CLASS,
              )}
              disabled={!user || isLoading}
              isStreaming={isStreaming || voiceDuplex.presence === "thinking"}
              ttsSpeaking={ttsSpeaking || voiceDuplex.presence === "speaking"}
              onStop={() => {
                void voiceDuplex.bargeIn()
                voiceDuplex.stop()
                stop()
                stopAgentVoice()
                setDuplexVoiceError(undefined)
              }}
              canSubmit={Boolean(
                user && (input.trim() || connectedFileAttachments.length > 0) && !isLoading,
              )}
              showSubmit
              onMicStatusChange={setMicStatus}
              voicePresence={voicePresence}
              voiceBilling={voiceBilling}
              voicePresenceDetail={voicePresenceDetail}
              onClearVoiceError={() => {
                setDuplexVoiceError(undefined)
                clearVoiceErrors()
              }}
              duplex={buildDuplexControls(voiceDuplex, {
                alsoPlaybackBlocked: agentVoicePlaybackBlocked,
                alsoResumePlayback: resumeAgentVoicePlayback,
              })}
              onVoiceInputError={(message) => {
                if (!message) return
                setDuplexVoiceError(message)
                toast.error(message)
              }}
              trailingExtras={
                <>
                  <VoiceMicSettingsPopover
                    voiceStatus={voiceDuplex.voiceStatus || voiceStatusSnapshot}
                    selectedDeviceId={micDeviceId}
                    onDeviceChange={setMicDeviceId}
                    profileOverride={micProfileOverride}
                    onProfileChange={setMicProfileOverride}
                    liveLevels={voiceDuplex.micLevels}
                    effectiveSettings={voiceDuplex.micEffective}
                  />
                  {/* Parity fix: /ai's connected-file browse button, added here too. */}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="mb-0.5 hidden h-8 w-8 shrink-0 rounded-full text-[color:var(--chat-surface-muted)] hover:bg-muted/60 hover:text-foreground sm:inline-flex"
                    disabled={isLoading}
                    title="Browse connected cloud files (read-only — not uploaded to Gravitre)"
                    aria-label="Browse files"
                    onClick={() => setConnectedFilePickerOpen(true)}
                  >
                    <FolderOpen className="h-4 w-4" />
                  </Button>
                </>
              }
            />
            <p className="mt-2 text-center text-[11px] text-muted-foreground">
              {agent.name} uses your organization&apos;s knowledge base and connected systems.
              {modality === "voice"
                ? " Voice writes still require the same typed/spoken yes confirmation as text."
                : ""}
            </p>
          </form>
        </div>
      </div>
      <ConnectedFilePickerDialog
        open={connectedFilePickerOpen}
        onOpenChange={setConnectedFilePickerOpen}
        selected={connectedFileAttachments}
        onConfirm={(files) => setConnectedFileAttachments(files)}
      />
    </AppShell>
  )
}
