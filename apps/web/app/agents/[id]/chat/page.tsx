"use client"

import { useEffect, useRef, useState, use, useMemo, useCallback } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
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
import { SharedChatComposerControls } from "@/components/gravitre/assistant/shared-chat-composer-controls"
import { getVoiceStatusDetailed } from "@/lib/tier1-voice-client"
import type { Agent } from "@/types/api"
import { agentsApi } from "@/lib/api"
import { PersonaSelector } from "@/components/gravitre/assistant/persona-selector"
import { usePreferredPersona } from "@/hooks/use-preferred-persona"
import { useAgentVoicePlayback } from "@/hooks/use-agent-voice-playback"
import { ChatTranscript } from "@/components/gravitre/assistant/chat-transcript"
import { ChatThemePicker } from "@/components/gravitre/assistant/chat-theme-picker"
import { useChatBackground } from "@/hooks/use-chat-background"
import { uiMessageText } from "@/lib/chat-messages"

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
  const { preferredPersona, handlePersonaChange } = usePreferredPersona({
    enabled: Boolean(user),
  })
  const { background: chatBackground, setBackground: setChatBackground } = useChatBackground()
  const [input, setInput] = useState("")
  const [modality, setModality] = useState<ChatModality>("text")
  const modalityRef = useRef<ChatModality>("text")
  const [voiceEntitled, setVoiceEntitled] = useState(true)
  const [voiceUnavailableReason, setVoiceUnavailableReason] = useState<string | undefined>(undefined)
  // Mirrored from the mic button so the presence strip shows the real recognition
  // state. Presentation only — the button remains the owner of the session.
  const [micStatus, setMicStatus] = useState<SpeechRecognitionStatus>("idle")
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
  } = useAgentVoicePlayback()

  const { data: agent, isLoading: agentLoading } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId),
  )

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
          preferred_persona: preferredPersona,
          // Same conversation + Module B memory; spoken_mode stacks SPOKEN register.
          spoken_mode: modalityRef.current === "voice",
          surface: modalityRef.current === "voice" ? "voice" : "agent_chat",
        }),
      }),
    [agentId, preferredPersona],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    messages: initialMessages,
    onError: (error) => {
      console.error("[v0] Agent chat error:", error)
      toast.error(parseChatError(error))
    },
  })

  const isLoading = status === "submitted" || status === "streaming"
  const isStreaming = status === "streaming"

  // Auto-TTS after assistant reply completes — same /api/voice/tts pipeline as /ai Read aloud.
  // Chat still uses execute_task_streaming(spoken_mode=True) via /api/chat body.
  useEffect(() => {
    if (modality !== "voice" || !voiceEntitled) return
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
  ])

  useEffect(() => {
    if (modality !== "voice") {
      stopAgentVoice()
      clearVoiceErrors()
      lastSpokenMessageIdRef.current = null
    }
  }, [modality, stopAgentVoice, clearVoiceErrors])

  // Presence: real TTS playback + real 402 billing (not inferred from stream alone).
  const voicePresence: VoicePresenceState =
    voiceBilling || voiceServiceError
      ? "error"
      : micStatus === "listening"
        ? "listening"
        : micStatus === "permission-denied" || micStatus === "audio-capture"
          ? "error"
          : ttsSpeaking || isStreaming
            ? "speaking"
            : "idle"
  const voicePresenceDetail = voiceBilling
    ? voiceBillingDetail
    : voiceServiceError
      ? voiceServiceDetail
      : undefined
  const hasSentMessage = messages.some((m) => m.role === "user")

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
    if (!trimmed || isLoading) return
    sendMessage({ text: trimmed })
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
      <div className="ai-surface-shell flex h-full min-h-0 flex-col">
        <div className="flex h-9 shrink-0 items-center gap-2 border-b border-success/10 bg-card/80 px-3 backdrop-blur-md md:px-4">
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
                    agent.status === "active" ? "bg-emerald-500" : "bg-amber-500",
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
          className="ai-chat-canvas min-h-0 flex-1 overflow-y-auto px-3 py-3 md:px-5 md:py-4"
          data-chat-bg={chatBackground}
        >
          {!hasSentMessage ? (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              className="mx-auto flex h-full max-w-[880px] flex-col items-center justify-center px-2 text-center"
            >
              <AgentIdentityAvatar agent={agent} size="lg" className="mb-5 shadow-lg" />
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
                    className="rounded-xl border border-success/15 bg-card/80 px-3 py-2.5 text-left text-xs text-muted-foreground transition-all hover:border-success/30 hover:bg-success/5 hover:text-foreground"
                  >
                    {suggestion}
                  </motion.button>
                ))}
              </div>
            </motion.div>
          ) : (
            <>
              <ChatTranscript
                messages={messages}
                showWaiting={isLoading && !isStreaming}
                assistantLabel={agent.name}
                // Identity as data, so the transcript renders this agent's real
                // icon and color WITH the shared state animations. Passing a
                // pre-rendered node here is exactly what disabled those states.
                assistantAgent={agent}
                waitingLabel={`${agent.name} is thinking…`}
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

        <div className="shrink-0 border-t border-[color:var(--chat-surface-border)] bg-card/90 px-3 py-2 backdrop-blur-md md:px-5">
          <form onSubmit={onSubmit} className="mx-auto w-full max-w-[920px]">
            <SharedChatComposerControls
              modality={modality}
              onModalityChange={(next) => {
                setModality(next)
                modalityRef.current = next
                if (next === "text") {
                  stopAgentVoice()
                  clearVoiceErrors()
                }
              }}
              voiceEntitled={voiceEntitled}
              unavailableReason={voiceUnavailableReason}
              // Real agent name, so the orb / pill read the agent rather than
              // the generic Gravitre default used by main chat.
              agentLabel={agent?.name || "Gravitre"}
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
              isStreaming={isStreaming}
              ttsSpeaking={ttsSpeaking}
              onStop={() => {
                stop()
                stopAgentVoice()
              }}
              canSubmit={Boolean(user && input.trim() && !isLoading)}
              showSubmit
              onMicStatusChange={setMicStatus}
              voicePresence={voicePresence}
              voiceBilling={voiceBilling}
              voicePresenceDetail={voicePresenceDetail}
              onVoiceInputError={(message) => {
                if (message) toast.error(message)
              }}
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
    </AppShell>
  )
}
