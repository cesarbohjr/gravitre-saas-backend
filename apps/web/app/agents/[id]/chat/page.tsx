"use client"

import { useEffect, useRef, useState, use, useMemo, useCallback } from "react"
import Link from "next/link"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { getSelectedOrgFromStorage, DEFAULT_DEMO_ORG_ID } from "@/lib/org-context"
import { motion, AnimatePresence } from "framer-motion"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  Send,
  Loader2,
  Sparkles,
  Copy,
  MessageSquarePlus,
  RefreshCw,
  Square,
  Database,
  Check,
  ChevronDown,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { toast } from "sonner"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import { agentsApi } from "@/lib/api"
import type { Agent } from "@/types/api"
import { Icon } from "@/lib/icons"

// localStorage key for agent chat persistence
const getStorageKey = (agentId: string) => `gravitre_agent_chat_${agentId}`

// Mock agent data
const mockAgent: Agent = {
  id: "agent-001",
  name: "Atlas",
  role: "Marketing Agent",
  department: "Marketing",
  description: "Marketing campaign orchestration",
  status: "active",
  personality: { color: "#10B981", gradient: "from-emerald-500 to-teal-500", glow: "emerald-500/20" },
  stats: { tasksToday: 12, successRate: 95, avgResponseTime: "2.4s", workflowsUsing: 3 },
  capabilities: ["campaign_management", "content_creation", "analytics"],
  permissions: ["read", "write", "execute"],
  lastAction: "Generated campaign report",
  lastActionTime: new Date().toISOString(),
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

// Agent personality colors
const agentColors: Record<string, { gradient: string; accent: string; glow: string }> = {
  "agent-001": { gradient: "from-emerald-500 to-teal-500", accent: "emerald", glow: "emerald-500/20" },
  "agent-002": { gradient: "from-blue-500 to-cyan-500", accent: "blue", glow: "blue-500/20" },
  "agent-003": { gradient: "from-violet-500 to-purple-500", accent: "violet", glow: "violet-500/20" },
  default: { gradient: "from-emerald-500 to-teal-500", accent: "emerald", glow: "emerald-500/20" },
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
  agentName,
  agentColor,
  isLast,
  onRegenerate,
}: {
  message: UIMessage
  isUser: boolean
  agentName: string
  agentColor: { gradient: string; accent: string; glow: string }
  isLast?: boolean
  onRegenerate?: () => void
}) {
  const { text, tools, sources } = normalizeMessage(message)
  const [showActions, setShowActions] = useState(false)

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(text)
    toast.success("Message copied")
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex gap-3 group",
        isUser ? "justify-end" : "justify-start"
      )}
      onMouseEnter={() => setShowActions(true)}
      onMouseLeave={() => setShowActions(false)}
    >
      {!isUser && (
        <div className={cn(
          "flex-shrink-0 h-8 w-8 rounded-lg bg-gradient-to-br flex items-center justify-center",
          agentColor.gradient,
          `shadow-lg shadow-${agentColor.glow}`
        )}>
          <span className="text-xs font-bold text-white">{agentName.slice(0, 2).toUpperCase()}</span>
        </div>
      )}

      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3",
          isUser
            ? "bg-emerald-600 text-white"
            : "bg-white border border-zinc-200 shadow-sm"
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
        <div className={cn(
          "prose prose-sm max-w-none",
          isUser ? "prose-invert" : "prose-zinc"
        )}>
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeHighlight]}
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "")
                const isInline = !match
                return isInline ? (
                  <code className={cn("px-1 py-0.5 rounded text-xs font-mono", isUser ? "bg-emerald-700" : "bg-zinc-100")} {...props}>
                    {children}
                  </code>
                ) : (
                  <div className="relative group/code my-2">
                    <pre className="rounded-lg overflow-x-auto text-xs">
                      <code className={className} {...props}>
                        {children}
                      </code>
                    </pre>
                    <CopyButton text={String(children)} />
                  </div>
                )
              },
              p({ children }) {
                return <p className="mb-2 last:mb-0 text-sm leading-relaxed">{children}</p>
              },
              ul({ children }) {
                return <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>
              },
              ol({ children }) {
                return <ol className="list-decimal pl-4 mb-2 space-y-1">{children}</ol>
              },
            }}
          >
            {text}
          </ReactMarkdown>
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

        {/* Message actions */}
        {!isUser && showActions && (
          <div className="flex items-center gap-1 mt-2 pt-2 border-t border-zinc-100">
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
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Fetch agent data
  const { data: agentData } = useSWR(
    user && agentId ? `agent/${agentId}` : null,
    () => agentsApi.get(agentId),
    { fallbackData: mockAgent }
  )
  const agent = agentData || mockAgent
  const agentColor = agentColors[agentId] || agentColors.default

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

  // Transport with agent context
  const transport = useMemo(
    () =>
      new DefaultChatTransport({
        api: "/api/chat",
        headers: async () => {
          const token = await getAccessToken()
          const org = getSelectedOrgFromStorage()
          return {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            "x-org-id": org?.id ?? DEFAULT_DEMO_ORG_ID,
          }
        },
        body: () => {
          const org = getSelectedOrgFromStorage()
          return {
            org_id: org?.id ?? DEFAULT_DEMO_ORG_ID,
            agent_id: agentId,
            mode: "agent",
            tools: ["knowledge_base", "agent_status", "connector_status"],
          }
        },
      }),
    [agentId]
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    messages: initialMessages,
    onError: (error) => {
      console.error("[v0] Agent chat error:", error)
      toast.error("Failed to send message. Please try again.")
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

  return (
    <AppShell title={`Chat with ${agent.name}`}>
      <div className="flex h-full flex-col bg-zinc-50">
        {/* Header */}
        <div className="border-b border-zinc-200 px-6 py-4 bg-white">
          <div className="flex items-center justify-between max-w-4xl mx-auto">
            <div className="flex items-center gap-4">
              {/* Breadcrumb */}
              <div className="flex items-center gap-2 text-sm">
                <Link
                  href="/agents"
                  className="text-zinc-500 hover:text-zinc-700 transition-colors"
                >
                  AI Team
                </Link>
                <span className="text-zinc-300">/</span>
                <Link
                  href={`/agents/${agentId}`}
                  className="text-zinc-500 hover:text-zinc-700 transition-colors"
                >
                  {agent.name}
                </Link>
                <span className="text-zinc-300">/</span>
                <span className="text-zinc-900 font-medium">Chat</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Link href={`/agents/${agentId}/knowledge`}>
                <Button variant="outline" size="sm" className="gap-2">
                  <Database className="h-4 w-4" />
                  Knowledge
                </Button>
              </Link>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNewConversation}
                className="gap-2"
              >
                <MessageSquarePlus className="h-4 w-4" />
                New Chat
              </Button>
            </div>
          </div>
        </div>

        {/* Agent Info Bar */}
        <div className="border-b border-zinc-200 px-6 py-3 bg-white/50">
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            <div className={cn(
              "h-10 w-10 rounded-xl bg-gradient-to-br flex items-center justify-center shadow-lg",
              agentColor.gradient,
              `shadow-${agentColor.glow}`
            )}>
              <span className="text-sm font-bold text-white">{agent.name.slice(0, 2).toUpperCase()}</span>
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-base font-semibold text-zinc-900">{agent.name}</h1>
              <p className="text-xs text-zinc-500 truncate">{agent.role} - {agent.description}</p>
            </div>
            <div className="flex items-center gap-1.5">
              <span className={cn(
                "h-2 w-2 rounded-full",
                agent.status === "active" ? "bg-emerald-500" : "bg-amber-500"
              )} />
              <span className="text-xs text-zinc-500 capitalize">{agent.status}</span>
            </div>
          </div>
        </div>

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
                <div className={cn(
                  "h-16 w-16 rounded-2xl bg-gradient-to-br flex items-center justify-center shadow-xl mb-6",
                  agentColor.gradient,
                  `shadow-${agentColor.glow}`
                )}>
                  <span className="text-xl font-bold text-white">{agent.name.slice(0, 2).toUpperCase()}</span>
                </div>
                <h2 className="text-xl font-semibold text-zinc-900 mb-2">Chat with {agent.name}</h2>
                <p className="text-sm text-zinc-500 max-w-md mb-8">
                  {agent.description || `Ask ${agent.name} anything about their capabilities and expertise.`}
                </p>
                <div className="grid grid-cols-2 gap-3 max-w-lg">
                  {[
                    `What can you help me with?`,
                    `What are you currently working on?`,
                    `Show me recent results`,
                    `What's your success rate?`,
                  ].map((suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => submitText(suggestion)}
                      className="px-4 py-3 rounded-xl border border-zinc-200 bg-white text-sm text-zinc-700 hover:bg-zinc-50 hover:border-zinc-300 transition-all text-left"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isUser={message.role === "user"}
                    agentName={agent.name}
                    agentColor={agentColor}
                    isLast={index === messages.length - 1 && message.role === "assistant"}
                    onRegenerate={handleRegenerate}
                  />
                ))}

                {isLoading && !isStreaming && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex gap-3"
                  >
                    <div className={cn(
                      "flex-shrink-0 h-8 w-8 rounded-lg bg-gradient-to-br flex items-center justify-center",
                      agentColor.gradient
                    )}>
                      <span className="text-xs font-bold text-white">{agent.name.slice(0, 2).toUpperCase()}</span>
                    </div>
                    <div className="bg-white border border-zinc-200 rounded-2xl px-4 py-3 shadow-sm">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 text-emerald-600 animate-spin" />
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
                className="flex-1 bg-transparent text-zinc-900 placeholder:text-zinc-400 focus:outline-none text-sm resize-none min-h-[24px] max-h-[120px]"
                style={{ height: "24px" }}
                onInput={(e) => {
                  const target = e.target as HTMLTextAreaElement
                  target.style.height = "24px"
                  target.style.height = Math.min(target.scrollHeight, 120) + "px"
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
                    "gap-2 text-white",
                    `bg-gradient-to-r ${agentColor.gradient} hover:opacity-90`
                  )}
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
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
