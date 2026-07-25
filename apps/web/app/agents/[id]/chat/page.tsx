"use client"

import { useEffect, useRef, useState, use, useMemo, useCallback } from "react"
import Link from "next/link"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
import { getEnvironmentHeader } from "@/lib/environment-context"
import { parseChatError } from "@/lib/chat-errors"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  Send,
  Sparkles,
  Copy,
  MessageSquarePlus,
  RefreshCw,
  Square,
  Database,
  Check,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { GravitreeLoader, LoadingIndicator } from "@/components/gravitre/gravitree-loader"
import { GravitreThinkingLoader } from "@/components/gravitre/assistant/thinking-loader"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { cn } from "@/lib/utils"
import { polishAssistantText } from "@/lib/plain-english"
import {
  CHAT_BUBBLE_BASE_CLASS,
  CHAT_BODY_TEXT_CLASS,
  CHAT_COMPOSER_CLASS,
  CHAT_PROSE_CLASS,
  CHAT_ROLE_LABEL_CLASS,
} from "@/lib/chat-typography"
import { Button } from "@/components/ui/button"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { toast } from "sonner"
import { VoiceInputButton } from "@/components/gravitre/assistant/voice-input-button"
import { ReadAloudButton } from "@/components/gravitre/assistant/read-aloud-button"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import type { Agent } from "@/types/api"
import { agentsApi } from "@/lib/api"
import { PersonaSelector } from "@/components/gravitre/assistant/persona-selector"
import { usePreferredPersona } from "@/hooks/use-preferred-persona"

// localStorage key for agent chat persistence
const getStorageKey = (agentId: string) => `gravitre_agent_chat_${agentId}`
const AGENT_CHAT_HEADER_COLLAPSED_KEY = "gravitre:agent-chat-header-collapsed"

// Role-aware starter prompts for agent chat (STA-163)
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

// Parse message content
function normalizeMessage(message: UIMessage): {
  text: string
  tools: { name: string; result?: unknown }[]
  sources: { title: string; url?: string; excerpt?: string }[]
} {
  let text = ""
  const tools: { name: string; result?: unknown }[] = []
  const sources: { title: string; url?: string; excerpt?: string }[] = []

  for (const part of message.parts) {
    if (part.type === "text") {
      text += part.text
    } else if (part.type.startsWith("tool-")) {
      // AI SDK v6 tool parts have the properties directly on the part
      const toolPart = part as { type: string; toolCallId: string; toolName?: string; result?: unknown }
      if (toolPart.toolName) {
        tools.push({ name: toolPart.toolName, result: toolPart.result })
        // Extract sources from tool results
        if (toolPart.toolName === "knowledge_base" && toolPart.result) {
          const result = toolPart.result as { sources?: { title: string; url?: string; excerpt?: string }[] }
          if (result.sources) {
            sources.push(...result.sources)
          }
        }
      }
    }
  }

  return { text, tools, sources }
}

// Copy button component
function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-zinc-800 text-zinc-400 hover:text-zinc-200 opacity-0 group-hover:opacity-100 transition-opacity"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  )
}

// Chat message component
function ChatMessage({
  message,
  isUser,
  agent,
  agentColor,
  isLast,
  streaming,
  onRegenerate,
}: {
  message: UIMessage
  isUser: boolean
  agent?: Agent
  agentColor: { gradient: string; accent: string; glow: string }
  isLast?: boolean
  streaming?: boolean
  onRegenerate?: () => void
}) {
  const { text, tools, sources } = normalizeMessage(message)
  const displayText = isUser ? text : polishAssistantText(text)

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(text)
    toast.success("Message copied")
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, x: isUser ? 16 : -16 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      transition={{ type: "spring", stiffness: 380, damping: 32 }}
      className={cn(
        "flex gap-3 group",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && agent ? (
        <AgentIdentityAvatar agent={agent} size="sm" className="shadow-lg" />
      ) : null}

      <div
        className={cn(
          "max-w-[min(760px,88%)]",
          CHAT_BUBBLE_BASE_CLASS,
          isUser
            ? "rounded-tr-md bg-emerald-600 text-white"
            : "rounded-tl-md border border-zinc-200 bg-white shadow-sm",
        )}
      >
        {/* Tool activity */}
        {!isUser && tools.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {tools.map((tool, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-100 text-[10px] text-zinc-600 font-medium"
              >
                <Database className="h-2.5 w-2.5" />
                {tool.name.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}

        {/* Message content */}
        <div className={cn(CHAT_PROSE_CLASS, isUser ? "prose-invert" : "dark:prose-invert")}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "")
                const isInline = !match
                return isInline ? (
                  <code className={cn("rounded px-1 py-0.5 font-mono text-xs", isUser ? "bg-emerald-700" : "bg-zinc-100")} {...props}>
                    {children}
                  </code>
                ) : (
                  <div className="group/code relative my-2">
                    <pre className="overflow-x-auto rounded-lg text-xs">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                    <CopyButton text={String(children)} />
                  </div>
                )
              },
              p({ children }) {
                return <p className={cn("mb-2 last:mb-0", CHAT_BODY_TEXT_CLASS)}>{children}</p>
              },
              ul({ children }) {
                return <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>
              },
              ol({ children }) {
                return <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>
              },
            }}
          >
            {displayText}
          </ReactMarkdown>
          {streaming && text && !isUser && (
            <motion.span
              aria-hidden="true"
              className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 rounded-full bg-emerald-500 align-middle"
              animate={{ opacity: [1, 0.2, 1] }}
              transition={{ duration: 0.9, repeat: Infinity, ease: "easeInOut" }}
            />
          )}
        </div>

        {/* Sources */}
        {!isUser && sources.length > 0 && (
          <div className="mt-3 pt-2 border-t border-zinc-100">
            <p className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">Sources</p>
            <div className="space-y-1">
              {sources.slice(0, 3).map((source, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-700">
                  <span className="text-[10px] font-medium text-emerald-600">[{idx + 1}]</span>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noopener noreferrer" className="truncate hover:underline">
                      {source.title}
                    </a>
                  ) : (
                    <span className="truncate">{source.title}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Message actions — always visible on touch; hover-reveal on sm+ */}
        {!isUser && (
          <div className="mt-2 flex flex-wrap items-center gap-1 border-t border-zinc-100 pt-2 opacity-100 sm:opacity-0 sm:transition-opacity sm:group-hover:opacity-100">
            <ReadAloudButton messageId={message.id} text={displayText} compact />
            <button
              onClick={handleCopyMessage}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
            >
              <Copy className="h-3 w-3" />
              Copy
            </button>
            {isLast && onRegenerate && (
              <button
                onClick={onRegenerate}
                className="flex items-center gap-1 px-2 py-1 rounded text-xs text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
                Regenerate
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-lg bg-emerald-600 flex items-center justify-center">
          <span className="text-xs font-medium text-white">You</span>
        </div>
      )}
    </motion.div>
  )
}

export default function AgentChatPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id: agentId } = use(params)
  const { user } = useAuth()
  const { preferredPersona, handlePersonaChange } = usePreferredPersona({
    enabled: Boolean(user),
  })
  const [input, setInput] = useState("")
  const [headerCollapsed, setHeaderCollapsed] = useState(() => {
    if (typeof window === "undefined") return false
    return window.localStorage.getItem(AGENT_CHAT_HEADER_COLLAPSED_KEY) === "1"
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Fetch agent data
  const { data: agent, isLoading: agentLoading } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId)
  )
  const agentColor = useMemo(() => {
    const gradient = agent?.personality?.gradient || "from-emerald-500 to-teal-500"
    const glow = agent?.personality?.glow || "emerald-500/20"
    return { gradient, accent: "emerald", glow }
  }, [agent?.personality?.gradient, agent?.personality?.glow])
  const agentName = agent?.name ?? "Agent"
  const agentInitials = agentName.slice(0, 2).toUpperCase()

  const toggleHeaderCollapsed = () => {
    setHeaderCollapsed((collapsed) => {
      const next = !collapsed
      window.localStorage.setItem(AGENT_CHAT_HEADER_COLLAPSED_KEY, next ? "1" : "0")
      return next
    })
  }

  // Hydrate messages from localStorage
  const [initialMessages] = useState<UIMessage[]>(() => {
    if (typeof window === "undefined") return []
    try {
      const stored = localStorage.getItem(getStorageKey(agentId))
      if (stored) {
        return JSON.parse(stored) as UIMessage[]
      }
    } catch {
      // Ignore parse errors
    }
    return []
  })

  useEffect(() => {
    if (user) void ensureSelectedOrg(true)
  }, [user])

  // Transport with agent context
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
          tools: ["knowledge_base", "agent_status", "connector_status", "workflow_runs", "search_web"],
          preferred_persona: preferredPersona,
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
  const hasSentMessage = messages.some((m) => m.role === "user")

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(getStorageKey(agentId), JSON.stringify(messages.slice(-50)))
      } catch {
        // Ignore storage errors
      }
    }
  }, [messages, agentId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, status])

  // Handle new conversation
  const handleNewConversation = useCallback(() => {
    setMessages([])
    localStorage.removeItem(getStorageKey(agentId))
    inputRef.current?.focus()
  }, [setMessages, agentId])

  // Handle regenerate
  const handleRegenerate = useCallback(() => {
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user")
    if (lastUserMessage) {
      const withoutLastAssistant = messages.filter((m, i) => {
        if (i === messages.length - 1 && m.role === "assistant") return false
        return true
      })
      setMessages(withoutLastAssistant)
      const text = normalizeMessage(lastUserMessage).text
      if (text) {
        sendMessage({ text })
      }
    }
  }, [messages, setMessages, sendMessage])

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
        <div className="flex h-full items-center justify-center">
          <GravitreeLoader size="md" />
        </div>
      </AppShell>
    )
  }

  if (!agent) {
    return (
      <AppShell title="Agent chat">
        <div className="flex h-full flex-col items-center justify-center gap-3 text-center px-6">
          <p className="text-sm text-zinc-600">Agent not found or you don&apos;t have access.</p>
          <Link href="/agents">
            <Button variant="outline" size="sm">Back to AI Team</Button>
          </Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell title="Chat">
      <div className="flex h-full flex-col bg-zinc-50">
        {!headerCollapsed ? (
          <>
            <div className="border-b border-zinc-200 bg-white px-4 py-3 sm:px-6">
              <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2 text-sm text-zinc-500">
                  <Link href="/agents" className="hover:text-zinc-700 transition-colors">
                    AI Team
                  </Link>
                  <span className="text-zinc-300">/</span>
                  <Link href={`/agents/${agentId}`} className="truncate hover:text-zinc-700 transition-colors">
                    {agent.name}
                  </Link>
                  <span className="text-zinc-300">/</span>
                  <span className="font-medium text-zinc-900">Chat</span>
                </div>
                <div className="flex items-center gap-2">
                  <PersonaSelector
                    value={preferredPersona}
                    onChange={handlePersonaChange}
                    disabled={!user}
                    surface="light"
                    label="Response style"
                  />
                  <Link href={`/agents/${agentId}/knowledge`}>
                    <Button variant="outline" size="sm" className="gap-2">
                      <Database className="h-4 w-4" />
                      <span className="hidden sm:inline">Knowledge</span>
                    </Button>
                  </Link>
                  <Button variant="outline" size="sm" onClick={handleNewConversation} className="gap-2">
                    <MessageSquarePlus className="h-4 w-4" />
                    <span className="hidden sm:inline">New Chat</span>
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    onClick={toggleHeaderCollapsed}
                    aria-label="Hide chat overview for more space"
                    className="h-9 w-9 shrink-0"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>

            <div className="border-b border-zinc-200 bg-white/50 px-4 py-3 sm:px-6">
              <div className="mx-auto flex max-w-4xl items-center gap-3">
                <AgentIdentityAvatar agent={agent} size="md" className="shadow-lg" />
                <div className="min-w-0 flex-1">
                  <h1 className="text-base font-semibold text-zinc-900">{agent.name}</h1>
                  <p className="truncate text-xs text-zinc-500">
                    {agent.role} — {agent.description}
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      agent.status === "active" ? "bg-emerald-500" : "bg-amber-500",
                    )}
                  />
                  <span className="text-xs capitalize text-zinc-500">{agent.status}</span>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-200 bg-white px-3 py-2.5 sm:px-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-zinc-900">{agent.name}</p>
              <p className="text-xs text-zinc-500">
                {agent.role} · {agent.status}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <PersonaSelector
                value={preferredPersona}
                onChange={handlePersonaChange}
                disabled={!user}
                surface="light"
                label="Response style"
              />
              <Button
                type="button"
                variant="outline"
                size="icon"
                onClick={toggleHeaderCollapsed}
                aria-label="Show chat overview"
                className="h-9 w-9 shrink-0"
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto space-y-4">
            {!hasSentMessage ? (
              /* Empty state */
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex flex-col items-center justify-center h-[50vh] text-center"
              >
                <AgentIdentityAvatar agent={agent} size="lg" className="mb-6 shadow-xl" />
                <h2 className="text-xl font-semibold text-zinc-900 mb-2">Chat with {agent.name}</h2>
                <p className="text-sm text-zinc-500 max-w-md mb-8">
                  {agent.description || `Ask ${agent.name} anything about their capabilities and expertise.`}
                </p>
                <div className="grid grid-cols-2 gap-3 max-w-lg">
                  {getAgentSuggestions(agent).map((suggestion, i) => (
                    <motion.button
                      key={suggestion}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.15 + i * 0.06, type: "spring", stiffness: 380, damping: 32 }}
                      whileHover={{ y: -2 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => submitText(suggestion)}
                      className="px-4 py-3 rounded-xl border border-zinc-200 bg-white text-sm text-zinc-700 hover:bg-zinc-50 hover:border-emerald-300 hover:shadow-md hover:shadow-emerald-500/10 transition-colors text-left"
                    >
                      {suggestion}
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <>
                <AnimatePresence initial={false}>
                {messages.map((message, index) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isUser={message.role === "user"}
                    agent={agent}
                    agentColor={agentColor}
                    isLast={index === messages.length - 1 && message.role === "assistant"}
                    streaming={isStreaming && index === messages.length - 1 && message.role === "assistant"}
                    onRegenerate={handleRegenerate}
                  />
                ))}
                </AnimatePresence>

                {isLoading && !isStreaming && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex gap-3"
                  >
                    <AgentIdentityAvatar agent={agent} size="sm" />
                    <div className="bg-white border border-zinc-200 rounded-2xl px-4 py-3 shadow-sm">
                      <div className="flex items-center gap-2">
                        <GravitreThinkingLoader size={20} title={`${agent.name} is thinking`} />
                        <span className="text-sm text-zinc-500">{agent.name} is thinking...</span>
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className="border-t border-zinc-200 p-4 bg-white">
          <form onSubmit={onSubmit} className="max-w-4xl mx-auto">
            <div
              className={cn(
                "flex items-end gap-3 rounded-xl border bg-white p-3 transition-all",
                "border-zinc-200 hover:border-zinc-300 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20"
              )}
            >
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={user ? `Message ${agent.name}...` : "Sign in to chat"}
                disabled={!user || isLoading}
                rows={1}
                className={cn("flex-1 resize-none bg-transparent text-zinc-900 placeholder:text-zinc-400 focus:outline-none min-h-[24px] max-h-[120px]", CHAT_COMPOSER_CLASS)}
                style={{ height: "24px" }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = "24px"
                  target.style.height = Math.min(target.scrollHeight, 120) + "px"
                }}
              />
              
              <VoiceInputButton
                value={input}
                onChange={setInput}
                disabled={!user || isLoading}
                onError={(message) => {
                  if (message) toast.error(message)
                }}
              />

              {isStreaming ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => stop()}
                  className="gap-2 border-red-200 text-red-600 hover:bg-red-50 hover:text-red-700"
                >
                  <Square className="h-3.5 w-3.5 fill-current" />
                  Stop
                </Button>
              ) : (
                <Button
                  type="submit"
                  size="sm"
                  disabled={!user || !input.trim() || isLoading}
                  className={cn(
                    "gap-2 text-white transition-transform duration-150 active:scale-90",
                    `bg-gradient-to-r ${agentColor.gradient} hover:opacity-90`,
                    input.trim() && !isLoading && "motion-safe:hover:scale-105",
                  )}
                >
                  {isLoading ? (
                    <LoadingIndicator size="xs" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>
            <p className="text-[11px] text-zinc-500 text-center mt-2">
              {agent.name} uses your organization&apos;s knowledge base and connected systems.
            </p>
          </form>
        </div>
      </div>
    </AppShell>
  )
}
