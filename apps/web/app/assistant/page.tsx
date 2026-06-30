"use client"

import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import Link from "next/link"
import type { User } from "@supabase/supabase-js"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
import { parseChatError } from "@/lib/chat-errors"
import { conversationMessageToUI } from "@/lib/chat-messages"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  Loader2,
  Sparkles,
  Check,
  Copy,
  ChevronDown,
  MessageSquarePlus,
  Database,
  Bot,
  Plug,
  PanelLeftClose,
  PanelLeft,
  RefreshCw,
  Square,
  AlertTriangle,
  CheckCircle2,
  ArrowUp,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { toast } from "sonner"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import useSWR from "swr"
import { conversationsApi, assistantApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import type { Conversation } from "@/types/api"
import { ConversationSidebar } from "@/components/gravitre/assistant/conversation-sidebar"
import { useWorkPageShortcut } from "@/hooks/use-work-page-shortcut"
import {
  AssistantModelSelector,
  getModeConfig,
  inferModeFromModel,
  type IntelligenceMode,
} from "@/components/gravitre/assistant/assistant-model-selector"
import {
  ToolChip,
  extractPendingAuthConnectors,
  type ToolInvocation,
} from "@/components/gravitre/assistant/tool-chip"
import { FollowUpSuggestions } from "@/components/gravitre/assistant/follow-up-suggestions"
import { OrgContextPill } from "@/components/gravitre/assistant/org-context-pill"
import { ConnectorActionCard } from "@/components/gravitre/assistant/connector-action-card"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

// localStorage key for message persistence
const STORAGE_KEY = "gravitre_assistant_messages"
const CONVERSATION_ID_KEY = "gravitre_last_conversation_id"
const MODE_KEY = "gravitre_assistant_mode"
const MODEL_KEY = "gravitre_assistant_model"
const LAST_SESSION_KEY = "gravitre_last_session_date"
const MAX_STORED_MESSAGES = 50

// Intelligence modes — config lives in assistant-model-selector

const WELCOME_QUICK_ACTIONS = [
  {
    id: "agents",
    icon: Bot,
    category: "Agents",
    defaultQuery: "What agents are currently active?",
    iconWrapClass: "bg-violet-50 group-hover:bg-violet-100",
    iconClass: "text-violet-600",
    categoryClass: "text-violet-600",
    cardHoverClass: "hover:border-violet-300 hover:shadow-violet-500/10",
  },
  {
    id: "workflows",
    icon: Database,
    category: "Workflows",
    defaultQuery: "Show failed workflows from today",
    iconWrapClass: "bg-amber-50 group-hover:bg-amber-100",
    iconClass: "text-amber-600",
    categoryClass: "text-amber-600",
    cardHoverClass: "hover:border-amber-300 hover:shadow-amber-500/10",
  },
  {
    id: "connectors",
    icon: Plug,
    category: "Connectors",
    defaultQuery: "Which connectors have sync errors?",
    iconWrapClass: "bg-emerald-50 group-hover:bg-emerald-100",
    iconClass: "text-emerald-600",
    categoryClass: "text-emerald-600",
    cardHoverClass: "hover:border-emerald-300 hover:shadow-emerald-500/10",
  },
] as const

type BriefingBullet = {
  id: string
  text: string
  href: string
  tone: "error" | "success" | "warning"
}

function resolveUserFirstName(user: User | null): string | null {
  if (!user) return null
  const meta = user.user_metadata ?? {}
  const fromMeta = String(meta.full_name || meta.name || meta.display_name || "").trim()
  if (fromMeta) return fromMeta.split(/\s+/)[0]
  const email = user.email ?? ""
  if (email.includes("@")) {
    const local = email.split("@")[0].replace(/[._]/g, " ")
    const token = local.split(/\s+/)[0]
    if (token) return token.charAt(0).toUpperCase() + token.slice(1)
  }
  return null
}

function resolveWelcomeGreeting(
  apiGreeting: string | undefined,
  user: User | null,
): string {
  const firstName = resolveUserFirstName(user)
  if (apiGreeting) {
    if (user?.email && apiGreeting.includes(user.email) && firstName) {
      return apiGreeting.replace(user.email, firstName)
    }
    if (firstName && !apiGreeting.includes(firstName)) {
      if (apiGreeting === "Welcome back" || apiGreeting === "Good morning") {
        return `${apiGreeting}, ${firstName}`
      }
    }
    return apiGreeting
  }
  if (firstName) return `Welcome back, ${firstName}`
  return "How can I help you today?"
}

function normalizeBriefingBullet(
  bullet: string | { id?: string; text: string; href?: string; tone?: BriefingBullet["tone"] },
  index: number,
): BriefingBullet {
  if (typeof bullet === "string") {
    const lower = bullet.toLowerCase()
    if (lower.includes("connector") && lower.includes("auth")) {
      return { id: `legacy-${index}`, text: bullet, href: "/connectors", tone: "error" }
    }
    if (lower.includes("agent") && lower.includes("completed")) {
      return { id: `legacy-${index}`, text: bullet, href: "/agents", tone: "success" }
    }
    if (lower.includes("workflow") && lower.includes("fail")) {
      return { id: `legacy-${index}`, text: bullet, href: "/workflows", tone: "warning" }
    }
    return { id: `legacy-${index}`, text: bullet, href: "/assignments", tone: "warning" }
  }
  return {
    id: bullet.id || `briefing-${index}`,
    text: bullet.text,
    href: bullet.href || "/assignments",
    tone: bullet.tone || "warning",
  }
}

function briefingToneStyles(tone: BriefingBullet["tone"]) {
  if (tone === "error") {
    return {
      icon: Plug,
      iconClass: "text-red-400",
      rowClass: "hover:border-red-500/30 hover:bg-red-500/5",
    }
  }
  if (tone === "success") {
    return {
      icon: CheckCircle2,
      iconClass: "text-emerald-400",
      rowClass: "hover:border-emerald-500/30 hover:bg-emerald-500/5",
    }
  }
  return {
    icon: AlertTriangle,
    iconClass: "text-amber-400",
    rowClass: "hover:border-amber-500/30 hover:bg-amber-500/5",
  }
}


interface SourceCitation {
  title: string
  snippet: string
  relevance: number
}

type IntelligenceMeta = {
  messageId?: string
  confidence?: {
    score?: number
    band?: "high" | "medium" | "low"
    needsClarification?: boolean
  }
  answerExplanation?: string
  conflicts?: Array<Record<string, unknown>>
}

function confidenceBadgeClass(band?: string): string {
  if (band === "high") return "bg-emerald-50 text-emerald-700 border-emerald-200"
  if (band === "medium") return "bg-amber-50 text-amber-700 border-amber-200"
  return "bg-zinc-100 text-zinc-600 border-zinc-200"
}

function WhyThisAnswerPanel({ explanation }: { explanation: string }) {
  const [expanded, setExpanded] = useState(false)
  if (!explanation.trim()) return null
  return (
    <div className="mt-3 pt-3 border-t border-zinc-200">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-700 transition-colors"
      >
        <Sparkles className="h-3 w-3" />
        <span>Why this answer?</span>
        <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} />
      </button>
      {expanded ? (
        <p className="mt-2 text-xs leading-relaxed text-zinc-600">{explanation}</p>
      ) : null}
    </div>
  )
}

interface UIPartLike {
  type: string
  text?: string
  toolCallId?: string
  state?: string
  output?: unknown
}

function normalizeMessage(message: UIMessage): {
  text: string
  tools: ToolInvocation[]
  sources: SourceCitation[]
} {
  const parts = (message.parts ?? []) as unknown as UIPartLike[]
  const text = parts
    .filter((p) => p.type === "text" && typeof p.text === "string")
    .map((p) => p.text as string)
    .join("")

  const tools: ToolInvocation[] = []
  const sources: SourceCitation[] = []

  for (const part of parts) {
    if (!part.type.startsWith("tool-")) continue
    const toolName = part.type.replace(/^tool-/, "")
    const isResult = part.state === "output-available"
    tools.push({
      toolCallId: part.toolCallId ?? `${toolName}-${tools.length}`,
      toolName,
      state: isResult ? "result" : "call",
      result: part.output,
    })
    if (toolName === "searchKnowledgeBase" && isResult && part.output) {
      const out = part.output as { results?: SourceCitation[] }
      if (Array.isArray(out.results)) sources.push(...out.results)
    }
  }

  return { text, tools, sources }
}

// Copy button for code blocks
function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1.5 rounded-md bg-zinc-800/80 hover:bg-zinc-700 transition-colors opacity-0 group-hover:opacity-100"
      title="Copy code"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <Copy className="h-3.5 w-3.5 text-zinc-400" />
      )}
    </button>
  )
}

function nodeToText(node: React.ReactNode): string {
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(nodeToText).join("")
  return ""
}

function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  const language = className?.replace("language-", "") || ""
  const codeString = nodeToText(children)

  return (
    <div className="relative group my-3 rounded-lg overflow-hidden">
      {language && (
        <div className="flex items-center justify-between px-4 py-2 bg-zinc-900 border-b border-zinc-800">
          <span className="text-xs text-zinc-400 font-mono">{language}</span>
        </div>
      )}
      <pre className="bg-zinc-900 p-4 overflow-x-auto">
        <code className={cn("text-sm text-zinc-100", className)}>{children}</code>
      </pre>
      <CopyButton code={codeString} />
    </div>
  )
}

// Source citations component
function SourceCitations({ sources }: { sources: SourceCitation[] }) {
  const [expanded, setExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-3 pt-3 border-t border-zinc-200">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs text-zinc-500 hover:text-zinc-700 transition-colors"
      >
        <Database className="h-3 w-3" />
        <span>{sources.length} source{sources.length !== 1 ? "s" : ""}</span>
        <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} />
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2">
              {sources.map((source, i) => (
                <div key={i} className="p-2.5 rounded-lg bg-zinc-50 border border-zinc-200">
                  <p className="text-xs font-medium text-zinc-700">{source.title}</p>
                  <p className="text-[11px] text-zinc-500 mt-1 line-clamp-2">{source.snippet.slice(0, 100)}...</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// Message component with markdown rendering
function ChatMessage({
  message,
  isUser,
  isLast,
  streaming,
  onRegenerate,
  followUpSuggestions,
  onFollowUp,
  showFollowUps,
  expandedToolId,
  onToggleTool,
  intelligenceMeta,
  onFeedback,
}: {
  message: UIMessage
  isUser: boolean
  isLast?: boolean
  streaming?: boolean
  onRegenerate?: () => void
  followUpSuggestions?: string[]
  onFollowUp?: (text: string) => void
  showFollowUps?: boolean
  expandedToolId?: string | null
  onToggleTool?: (id: string) => void
  intelligenceMeta?: IntelligenceMeta | null
  onFeedback?: (helpful: boolean) => void
}) {
  const { text, tools, sources } = normalizeMessage(message)
  const [copied, setCopied] = useState(false)
  const reduceMotion = useReducedMotion()
  const pendingConnectors = extractPendingAuthConnectors(tools)

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    toast.success("Copied to clipboard")
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, x: isUser ? 16 : -16 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      transition={{ type: "spring", stiffness: 380, damping: 32 }}
      className={cn("flex gap-4 group", isUser ? "justify-end" : "justify-start")}
    >
      {!isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
          <Sparkles className="h-4 w-4 text-white" />
        </div>
      )}

      <div className={cn("max-w-[85%] md:max-w-[75%]", isUser ? "order-first" : "")}>
        <div
          className={cn(
            "rounded-2xl px-4 py-3",
            isUser
              ? "bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-500/20"
              : "bg-white text-zinc-900 border border-zinc-200 shadow-sm"
          )}
        >
          {/* Tool invocations */}
          {!isUser && tools.length > 0 && (
            <div className="space-y-1 mb-3">
              {tools.map((tool) => (
                <ToolChip
                  key={tool.toolCallId}
                  invocation={tool}
                  expanded={expandedToolId === tool.toolCallId}
                  onToggle={() => onToggleTool?.(tool.toolCallId)}
                />
              ))}
            </div>
          )}

          {/* Message content */}
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{text}</p>
          ) : (
            <div
              aria-live={streaming ? "polite" : "off"}
              aria-busy={streaming || undefined}
              className="prose prose-sm max-w-none prose-p:my-2 prose-p:leading-relaxed prose-headings:my-3 prose-headings:font-semibold prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-code:text-emerald-700 prose-code:bg-emerald-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-strong:font-semibold"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeHighlight]}
                components={{
                  pre: ({ children }) => <>{children}</>,
                  code: ({ className, children, ...props }) => {
                    const isInline = !className
                    if (isInline) {
                      return (
                        <code className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded text-[13px]" {...props}>
                          {children}
                        </code>
                      )
                    }
                    return <CodeBlock className={className}>{children}</CodeBlock>
                  },
                }}
              >
                {text}
              </ReactMarkdown>
              {streaming && text && (
                reduceMotion ? (
                  <span
                    aria-hidden="true"
                    className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 rounded-full bg-emerald-500 align-middle"
                  />
                ) : (
                  <motion.span
                    aria-hidden="true"
                    className="ml-0.5 inline-block h-4 w-[2px] translate-y-0.5 rounded-full bg-emerald-500 align-middle"
                    animate={{ opacity: [1, 0.2, 1] }}
                    transition={{ duration: 0.9, repeat: Infinity, ease: "easeInOut" }}
                  />
                )
              )}
            </div>
          )}

          {/* Source citations */}
          {!isUser && intelligenceMeta?.confidence?.score != null && !streaming && (
            <div className="mb-2">
              <span
                className={cn(
                  "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium tabular-nums",
                  confidenceBadgeClass(intelligenceMeta.confidence.band),
                )}
              >
                {Math.round((intelligenceMeta.confidence.score ?? 0) * 100)}% confidence
              </span>
            </div>
          )}
          {!isUser && sources.length > 0 && <SourceCitations sources={sources} />}
          {!isUser && intelligenceMeta?.answerExplanation && !streaming && (
            <WhyThisAnswerPanel explanation={intelligenceMeta.answerExplanation} />
          )}
          {!isUser && pendingConnectors.length > 0 && <ConnectorActionCard connectors={pendingConnectors} />}
        </div>

        {!isUser && isLast && followUpSuggestions && onFollowUp && (
          <FollowUpSuggestions
            suggestions={followUpSuggestions}
            onSelect={onFollowUp}
            visible={Boolean(showFollowUps)}
          />
        )}

        {/* Message actions */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-2 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={handleCopyMessage}
                    className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 transition-colors"
                  >
                    {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">Copy</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => onFeedback?.(true)}
                    className="p-1.5 rounded-md text-zinc-400 hover:text-emerald-600 hover:bg-zinc-100 transition-colors"
                    title="Good response"
                  >
                    👍
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">Helpful</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={() => onFeedback?.(false)}
                    className="p-1.5 rounded-md text-zinc-400 hover:text-red-500 hover:bg-zinc-100 transition-colors"
                    title="Poor response"
                  >
                    👎
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="text-xs">Not helpful</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            {isLast && onRegenerate && (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      onClick={onRegenerate}
                      className="p-1.5 rounded-md text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 transition-colors"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="text-xs">Regenerate</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 h-8 w-8 rounded-full bg-zinc-900 flex items-center justify-center">
          <span className="text-[10px] font-semibold text-white">You</span>
        </div>
      )}
    </motion.div>
  )
}

// Typing indicator
function TypingIndicator() {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex gap-4">
      <div className="flex-shrink-0 h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-lg shadow-emerald-500/20">
        <Sparkles className="h-4 w-4 text-white" />
      </div>
      <div className="bg-white border border-zinc-200 rounded-2xl px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1.5">
          <motion.div
            className="w-2 h-2 rounded-full bg-emerald-500"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: 0 }}
          />
          <motion.div
            className="w-2 h-2 rounded-full bg-emerald-500"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
          />
          <motion.div
            className="w-2 h-2 rounded-full bg-emerald-500"
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ duration: 0.6, repeat: Infinity, delay: 0.4 }}
          />
        </div>
      </div>
    </motion.div>
  )
}

function ConversationMessagesSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex justify-end gap-3">
        <Skeleton className="h-16 w-[min(72%,20rem)] rounded-2xl rounded-br-md" />
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
      </div>
      <div className="flex gap-4">
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        <div className="space-y-2">
          <Skeleton className="h-20 w-[min(80%,24rem)] rounded-2xl rounded-bl-md" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
      <div className="flex justify-end gap-3">
        <Skeleton className="h-12 w-[min(60%,16rem)] rounded-2xl rounded-br-md" />
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
      </div>
      <div className="flex gap-4">
        <Skeleton className="h-8 w-8 shrink-0 rounded-full" />
        <Skeleton className="h-24 w-[min(85%,26rem)] rounded-2xl rounded-bl-md" />
      </div>
    </div>
  )
}

export default function AssistantPage() {
  const { user } = useAuth()
  const [input, setInput] = useState("")
  const [followUpSuggestions, setFollowUpSuggestions] = useState<string[]>([])
  const [expandedToolId, setExpandedToolId] = useState<string | null>(null)
  const [conversationTitle, setConversationTitle] = useState<string>("Gravitre Assistant")
  const [editingTitle, setEditingTitle] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeConversationIdRef = useRef<string | null>(null)
  const recentInputsRef = useRef<string[]>([])
  const submitLockRef = useRef(false)
  const pendingConversationRef = useRef<Promise<string | null> | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  // G2: inline stream-health error (empty completion or transport failure) with retry.
  const [streamError, setStreamError] = useState<string | null>(null)
  const [intelligenceByMessageId, setIntelligenceByMessageId] = useState<Record<string, IntelligenceMeta>>({})
  const pendingIntelligenceRef = useRef<IntelligenceMeta | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [conversationMessagesLoading, setConversationMessagesLoading] = useState(false)
  const [conversationMessagesError, setConversationMessagesError] = useState<string | null>(null)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(CONVERSATION_ID_KEY)
  })

  const [mode, setMode] = useState<IntelligenceMode>(() => {
    if (typeof window === "undefined") return "standard"
    return (localStorage.getItem(MODE_KEY) as IntelligenceMode) || "standard"
  })

  const [modelOverride, setModelOverride] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(MODEL_KEY)
  })

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode)
  }, [mode])

  useEffect(() => {
    if (modelOverride) localStorage.setItem(MODEL_KEY, modelOverride)
    else localStorage.removeItem(MODEL_KEY)
  }, [modelOverride])

  useEffect(() => {
    if (!user) return
    void assistantApi.getPreferences().then((prefs) => {
      if (prefs.preferred_mode) setMode(prefs.preferred_mode as IntelligenceMode)
      if (prefs.preferred_model) setModelOverride(prefs.preferred_model)
    }).catch(() => {})
  }, [user])

  const persistPreferences = useCallback((nextMode: IntelligenceMode, nextModel: string | null) => {
    void assistantApi.updatePreferences({
      preferred_mode: nextMode,
      preferred_model: nextModel || undefined,
    }).catch(() => {})
  }, [])

  // Resolve org from membership before first chat request (replaces stale demo org in storage).
  useEffect(() => {
    if (user) void ensureSelectedOrg(true)
  }, [user])

  // Fetch conversations list
  const {
    data: conversationsData,
    error: conversationsError,
    isLoading: conversationsLoading,
    mutate: mutateConversations,
  } = useSWR(
    user ? "conversations" : null,
    () => conversationsApi.list({ limit: 100, includeArchived: true }),
    { revalidateOnFocus: false },
  )
  const conversations = conversationsData?.conversations ?? []
  const showConversationsSkeleton = Boolean(user) && conversationsLoading && !conversationsData
  const showConversationsError = Boolean(user) && Boolean(conversationsError) && !conversationsLoading

  // Hydrate once from localStorage (only for ad-hoc sessions without a saved conversation id)
  const [initialMessages] = useState<UIMessage[]>(() => {
    if (typeof window === "undefined") return []
    if (localStorage.getItem(CONVERSATION_ID_KEY)) return []
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored) as UIMessage[]
        return parsed.slice(-MAX_STORED_MESSAGES)
      }
    } catch {
      // Ignore parse errors
    }
    return []
  })

  // Transport configuration (ref read happens only inside body/headers at request time)
  const transport = useMemo(
    () =>
      // eslint-disable-next-line react-hooks/refs -- activeConversationIdRef is read in body(), not during render
      new DefaultChatTransport({
        api: "/api/chat",
        headers: async () => {
          const token = await getAccessToken()
          const orgId = await ensureSelectedOrg()
          return {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(orgId ? { "x-org-id": orgId } : {}),
          }
        },
        body: () => ({
          ...buildChatOrgPayload(),
          mode,
          model_override: modelOverride,
          conversation_id: activeConversationIdRef.current,
        }),
      }),
    [mode, modelOverride],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    messages: initialMessages,
    onError: (error) => {
      console.error("[v0] Chat error:", error)
      submitLockRef.current = false
      setIsSubmitting(false)
      setStreamError(parseChatError(error))
      toast.error(parseChatError(error))
    },
    onFinish: ({ message, isAbort, isDisconnect }) => {
      submitLockRef.current = false
      setIsSubmitting(false)
      if (message?.role === "assistant" && message.id && pendingIntelligenceRef.current) {
        const intel = pendingIntelligenceRef.current
        pendingIntelligenceRef.current = null
        setIntelligenceByMessageId((prev) => ({
          ...prev,
          [message.id]: { ...intel, messageId: intel.messageId ?? message.id },
        }))
      }
      // G2 stream health: a finished assistant turn with no text means the
      // provider stream produced nothing (silent failover/guardrail). Surface
      // an inline retry instead of leaving an empty bubble. Ignore user-initiated
      // stops (isAbort) so the Stop button never looks like an error.
      const finishedText = message?.role === "assistant" ? normalizeMessage(message).text.trim() : ""
      if (!isAbort && message?.role === "assistant" && !finishedText) {
        setStreamError(
          isDisconnect
            ? "The connection dropped before the assistant could respond. Please try again."
            : "The assistant didn't return a response. Please try again.",
        )
      } else {
        setStreamError(null)
      }
      void mutateConversations()
    },
    onData: (dataPart) => {
      if (dataPart.type === "data-suggestions" && dataPart.data && typeof dataPart.data === "object") {
        const payload = dataPart.data as { suggestions?: string[] }
        if (Array.isArray(payload.suggestions)) {
          setFollowUpSuggestions(payload.suggestions)
        }
      }
      if (dataPart.type === "data-intelligence" && dataPart.data && typeof dataPart.data === "object") {
        const payload = dataPart.data as IntelligenceMeta
        pendingIntelligenceRef.current = payload
      }
    },
  })

  const { data: dailyBriefing } = useSWR(
    user && messages.length === 0 ? "assistant-daily-briefing" : null,
    () => assistantApi.dailyBriefing(),
    { revalidateOnFocus: false },
  )

  const welcomeGreeting = resolveWelcomeGreeting(dailyBriefing?.greeting, user)
  const briefingBullets = useMemo(
    () => (dailyBriefing?.bullets ?? []).map((bullet, index) => normalizeBriefingBullet(bullet, index)),
    [dailyBriefing?.bullets],
  )
  const welcomeQuickActions = useMemo(
    () =>
      WELCOME_QUICK_ACTIONS.map((action, index) => ({
        ...action,
        query: dailyBriefing?.suggestions?.[index] ?? action.defaultQuery,
      })),
    [dailyBriefing?.suggestions],
  )

  const isLoading = status === "submitted" || status === "streaming"
  const isStreaming = status === "streaming"
  const isBusy = isLoading || isSubmitting
  const hasSentMessage = messages.some((m) => m.role === "user")
  const handleMessageFeedback = useCallback(async (messageId: string | undefined, helpful: boolean) => {
    const resolvedId = messageId ?? pendingIntelligenceRef.current?.messageId
    if (!resolvedId) {
      toast.error("Feedback is not available for this message yet.")
      return
    }
    try {
      await assistantApi.submitFeedback({ message_id: resolvedId, helpful })
      toast.success(helpful ? "Thanks for the feedback" : "Feedback recorded")
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not submit feedback")
    }
  }, [])

  const currentModeConfig = getModeConfig(mode)
  const activeConversation = conversations.find((c) => c.id === activeConversationId)

  // Keep ref in sync for transport body closure.
  useEffect(() => {
    activeConversationIdRef.current = activeConversationId
  }, [activeConversationId])

  // Hydrate active conversation messages from API when restoring last session.
  const loadConversationMessages = useCallback(
    async (id: string) => {
      setConversationMessagesLoading(true)
      setConversationMessagesError(null)
      try {
        const { messages: stored } = await conversationsApi.getMessages(id)
        setMessages(stored.map(conversationMessageToUI))
      } catch (error) {
        console.error("[v0] Load conversation failed:", error)
        setMessages([])
        if (error instanceof ApiError && error.status === 404) {
          localStorage.removeItem(CONVERSATION_ID_KEY)
          setActiveConversationId(null)
          activeConversationIdRef.current = null
          setConversationMessagesError(null)
          void mutateConversations()
          return
        }
        setConversationMessagesError(
          "We couldn't load this conversation. Check your connection and try again.",
        )
      } finally {
        setConversationMessagesLoading(false)
      }
    },
    [setMessages, mutateConversations],
  )

  useEffect(() => {
    if (!user || !activeConversationId || messages.length > 0) return
    const timer = window.setTimeout(() => {
      void loadConversationMessages(activeConversationId)
    }, 0)
    return () => window.clearTimeout(timer)
  }, [user, activeConversationId, messages.length, loadConversationMessages])

  // Persist ad-hoc sessions to localStorage (conversation threads are stored via API)
  useEffect(() => {
    if (activeConversationId) return
    if (messages.length > 0) {
      try {
        const toStore = messages.slice(-MAX_STORED_MESSAGES)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore))
      } catch {
        // Ignore storage errors
      }
    }
  }, [messages, activeConversationId])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, status])

  // Handle new conversation
  const handleNewConversation = useCallback(() => {
    setMessages([])
    setActiveConversationId(null)
    activeConversationIdRef.current = null
    pendingConversationRef.current = null
    submitLockRef.current = false
    setIsSubmitting(false)
    setConversationMessagesLoading(false)
    setConversationMessagesError(null)
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(CONVERSATION_ID_KEY)
    inputRef.current?.focus()
    void mutateConversations()
  }, [setMessages, mutateConversations])

  // Handle selecting a conversation from sidebar
  const handleSelectConversation = useCallback(
    async (id: string) => {
      setActiveConversationId(id)
      activeConversationIdRef.current = id
      localStorage.setItem(CONVERSATION_ID_KEY, id)
      localStorage.removeItem(STORAGE_KEY)
      await loadConversationMessages(id)
    },
    [loadConversationMessages],
  )

  const retryLoadConversation = useCallback(() => {
    if (activeConversationId) {
      void loadConversationMessages(activeConversationId)
    }
  }, [activeConversationId, loadConversationMessages])

  // Handle deleting a conversation
  const handleDeleteConversation = useCallback(async (id: string) => {
    try {
      await conversationsApi.delete(id)
      if (activeConversationId === id) {
        handleNewConversation()
      }
      await mutateConversations()
      toast.success("Conversation deleted")
    } catch (error) {
      console.error("[v0] Delete conversation failed:", error)
      const message = error instanceof Error ? error.message : "Failed to delete conversation"
      toast.error(message)
    }
  }, [activeConversationId, handleNewConversation, mutateConversations])

  const handleArchiveConversation = useCallback(async (id: string) => {
    try {
      await conversationsApi.archive(id)
      if (activeConversationId === id) handleNewConversation()
      await mutateConversations()
      toast.success("Conversation archived")
    } catch {
      toast.error("Failed to archive conversation")
    }
  }, [activeConversationId, handleNewConversation, mutateConversations])

  const handleRenameConversation = useCallback(async (id: string, title: string) => {
    try {
      await conversationsApi.update(id, { title })
      if (activeConversationId === id) setConversationTitle(title)
      await mutateConversations()
    } catch {
      toast.error("Failed to rename conversation")
    }
  }, [activeConversationId, mutateConversations])

  const handleBulkDeleteConversations = useCallback(async (ids: string[]) => {
    try {
      await conversationsApi.bulkDelete(ids)
      if (activeConversationId && ids.includes(activeConversationId)) handleNewConversation()
      await mutateConversations()
      toast.success(`Deleted ${ids.length} conversation${ids.length === 1 ? "" : "s"}`)
    } catch (error) {
      console.error("[v0] Bulk delete conversations failed:", error)
      const message = error instanceof Error ? error.message : "Failed to delete conversations"
      toast.error(message)
    }
  }, [activeConversationId, handleNewConversation, mutateConversations])

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

  const fillFollowUp = useCallback((text: string) => {
    setInput(text)
    setFollowUpSuggestions([])
    inputRef.current?.focus()
  }, [])

  // G2: retry after a failed/empty stream. Preserves conversation_id (ref persists)
  // so the thread is not orphaned, and strips any trailing empty assistant bubble.
  const retryStream = useCallback(() => {
    setStreamError(null)
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user")
    if (!lastUserMessage) return
    const cleaned = messages.filter((m, i) => {
      if (i === messages.length - 1 && m.role === "assistant") {
        return normalizeMessage(m).text.trim().length > 0
      }
      return true
    })
    setMessages(cleaned)
    const text = normalizeMessage(lastUserMessage).text
    if (text) sendMessage({ text })
  }, [messages, setMessages, sendMessage, setStreamError])

  const submitText = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isBusy || submitLockRef.current) return

    submitLockRef.current = true
    setIsSubmitting(true)
    setStreamError(null)
    setFollowUpSuggestions([])
    setExpandedToolId(null)
    setInput(trimmed)
    recentInputsRef.current = [trimmed, ...recentInputsRef.current.filter((v) => v !== trimmed)].slice(0, 20)

    try {
      const orgId = await ensureSelectedOrg(true)
      if (!orgId) {
        console.warn("[assistant] No org in client cache — backend will resolve from JWT membership")
      }

      if (!activeConversationIdRef.current) {
        if (!pendingConversationRef.current) {
          pendingConversationRef.current = conversationsApi
            .create({ title: trimmed.slice(0, 80) })
            .then((created) => {
              activeConversationIdRef.current = created.id
              setActiveConversationId(created.id)
              setConversationTitle(created.title || trimmed.slice(0, 80))
              localStorage.setItem(CONVERSATION_ID_KEY, created.id)
              void mutateConversations()
              return created.id
            })
            .catch((error) => {
              console.warn("[assistant] Conversation create failed — continuing without sidebar thread:", error)
              return null
            })
            .finally(() => {
              pendingConversationRef.current = null
            })
        }
        await pendingConversationRef.current
      }

      sendMessage({ text: trimmed })
      setInput("")
    } catch (error) {
      console.error("[assistant] Submit failed:", error)
      toast.error("Failed to send message")
      submitLockRef.current = false
      setIsSubmitting(false)
    }
  }, [isBusy, mutateConversations, sendMessage])

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void submitText(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault()
      void submitText(input)
      return
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      void submitText(input)
      return
    }
    if (e.key === "Escape" && input) {
      e.preventDefault()
      setInput("")
      return
    }
    if (e.key === "ArrowUp" && !input && recentInputsRef.current.length > 0) {
      e.preventDefault()
      setInput(recentInputsRef.current[0])
    }
  }

  useWorkPageShortcut("new", handleNewConversation)
  useWorkPageShortcut("focus-search", () => inputRef.current?.focus())

  return (
    <AppShell title="Assistant">
      <div className="flex h-full bg-zinc-50">
        {/* Conversation Sidebar */}
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          onArchive={handleArchiveConversation}
          onRename={handleRenameConversation}
          onBulkDelete={handleBulkDeleteConversations}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          isLoading={showConversationsSkeleton}
          loadError={showConversationsError ? conversationsError : undefined}
          onRetry={() => void mutateConversations()}
        />

        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Minimal header */}
          <div className="h-14 flex items-center justify-between px-4 md:px-6 border-b border-zinc-200 bg-white">
            <div className="flex items-center gap-3">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="h-8 w-8 text-zinc-500 hover:text-zinc-900"
              >
                {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
              </Button>
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
                <Sparkles className="h-4 w-4 text-white" />
              </div>
              <div>
                {editingTitle && activeConversationId ? (
                  <input
                    value={conversationTitle}
                    onChange={(e) => setConversationTitle(e.target.value)}
                    onBlur={() => {
                      setEditingTitle(false)
                      if (activeConversationId) void handleRenameConversation(activeConversationId, conversationTitle)
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") (e.target as HTMLInputElement).blur()
                      if (e.key === "Escape") setEditingTitle(false)
                    }}
                    className="text-sm font-semibold text-zinc-900 bg-transparent border-b border-emerald-400 outline-none"
                    autoFocus
                  />
                ) : (
                  <button
                    onClick={() => activeConversationId && setEditingTitle(true)}
                    className="text-left"
                  >
                    <h1 className="text-sm font-semibold text-zinc-900">
                      {activeConversation?.title || conversationTitle}
                    </h1>
                  </button>
                )}
                <p className="text-[11px] text-zinc-500">AI-powered automation help</p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleNewConversation}
              className="gap-2 h-8 text-xs"
            >
              <MessageSquarePlus className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">New</span>
            </Button>
          </div>

          <OrgContextPill enabled={Boolean(user)} />

          {/* Messages area */}
          <div className="flex-1 overflow-auto">
            <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
              {!user ? (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center justify-center py-20 text-center"
                >
                  <div className="h-16 w-16 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center mb-6 shadow-lg shadow-emerald-500/30">
                    <Sparkles className="h-7 w-7 text-white" />
                  </div>
                  <h2 className="text-xl font-semibold text-zinc-900 mb-2">Sign in to continue</h2>
                  <p className="text-sm text-zinc-500 max-w-sm">
                    Sign in to use the Gravitre AI Assistant and get help with your automation workflows.
                  </p>
                </motion.div>
              ) : conversationMessagesLoading && activeConversationId ? (
                <ConversationMessagesSkeleton />
              ) : conversationMessagesError && activeConversationId ? (
                <WorkSectionErrorCard
                  title="Couldn't load conversation"
                  message={conversationMessagesError}
                  onRetry={retryLoadConversation}
                  className="border-zinc-200 bg-red-50/90"
                />
              ) : messages.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <div className="relative mb-8">
                    <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-xl shadow-emerald-500/30">
                      <Sparkles className="h-9 w-9 text-white" />
                    </div>
                    <motion.div
                      className="absolute inset-0 rounded-full border-2 border-emerald-400/50"
                      animate={{ scale: [1, 1.3, 1], opacity: [0.6, 0, 0.6] }}
                      transition={{ duration: 2.5, repeat: Infinity }}
                    />
                  </div>
                  <h2 className="text-2xl font-semibold text-zinc-900 mb-3">
                    {welcomeGreeting}
                  </h2>
                  {briefingBullets.length ? (
                    <div className="mb-6 max-w-md w-full rounded-xl border border-zinc-200/80 bg-white p-4 text-sm shadow-sm shadow-zinc-200/60 ring-1 ring-zinc-100/80">
                      <p className="font-medium text-zinc-800 mb-3">Since you were last here:</p>
                      <ul className="space-y-1">
                        {briefingBullets.map((bullet) => {
                          const tone = briefingToneStyles(bullet.tone)
                          const ToneIcon = tone.icon
                          return (
                            <li key={bullet.id}>
                              <Link
                                href={bullet.href}
                                className={cn(
                                  "group flex items-start gap-2.5 rounded-lg border border-transparent px-2 py-2 -mx-2 transition-all",
                                  tone.rowClass,
                                )}
                              >
                                <ToneIcon className={cn("h-4 w-4 mt-0.5 shrink-0", tone.iconClass)} />
                                <span className="text-zinc-600 transition-colors group-hover:text-zinc-900">
                                  {bullet.text}
                                </span>
                              </Link>
                            </li>
                          )
                        })}
                      </ul>
                    </div>
                  ) : null}
                  <p className="text-sm text-zinc-500 mb-10 max-w-md">
                    I can help manage agents, troubleshoot workflows, check connector status, and answer questions about your automation platform.
                  </p>

                  {!hasSentMessage && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 w-full max-w-2xl">
                      {welcomeQuickActions.map((action, i) => {
                        const PromptIcon = action.icon
                        return (
                          <motion.button
                            key={action.id}
                            type="button"
                            disabled={isBusy}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            whileHover={isBusy ? undefined : { scale: 1.02 }}
                            whileTap={isBusy ? undefined : { scale: 0.98 }}
                            transition={{ delay: i * 0.08 }}
                            onClick={() => void submitText(action.query)}
                            className={cn(
                              "group flex flex-col items-start gap-3 p-4 rounded-xl border border-zinc-200 bg-white text-left shadow-sm transition-all",
                              action.cardHoverClass,
                              isBusy && "opacity-60 pointer-events-none",
                            )}
                          >
                            <div
                              className={cn(
                                "h-9 w-9 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors",
                                action.iconWrapClass,
                              )}
                            >
                              <PromptIcon className={cn("h-4 w-4", action.iconClass)} />
                            </div>
                            <div className="flex-1 min-w-0 w-full">
                              <p className={cn("text-xs font-semibold mb-1.5", action.categoryClass)}>
                                {action.category}
                              </p>
                              <p className="text-sm text-zinc-700 leading-snug group-hover:text-zinc-900">
                                {action.query}
                              </p>
                            </div>
                          </motion.button>
                        )
                      })}
                    </div>
                  )}
                </motion.div>
              ) : (
                <>
                  <AnimatePresence initial={false}>
                  {messages.map((message, index) => (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      isUser={message.role === "user"}
                      isLast={index === messages.length - 1 && message.role === "assistant"}
                      streaming={isStreaming && index === messages.length - 1 && message.role === "assistant"}
                      onRegenerate={handleRegenerate}
                      followUpSuggestions={followUpSuggestions}
                      onFollowUp={fillFollowUp}
                      showFollowUps={!input.trim() && !isLoading}
                      expandedToolId={expandedToolId}
                      onToggleTool={(id) => setExpandedToolId((prev) => (prev === id ? null : id))}
                      intelligenceMeta={message.role === "assistant" ? intelligenceByMessageId[message.id] ?? null : null}
                      onFeedback={
                        message.role === "assistant"
                          ? (helpful) =>
                              void handleMessageFeedback(
                                intelligenceByMessageId[message.id]?.messageId ?? message.id,
                                helpful,
                              )
                          : undefined
                      }
                    />
                  ))}
                  </AnimatePresence>

                  {isLoading && !isStreaming && <TypingIndicator />}

                  {streamError && !isLoading && (
                    <WorkSectionErrorCard
                      title="Response interrupted"
                      message={streamError}
                      onRetry={retryStream}
                      className="border-zinc-200 bg-red-50/90"
                    />
                  )}

                  <div ref={messagesEndRef} />
                </>
              )}
            </div>
          </div>

          {/* Agent Mode notice */}
          {mode === "agent" && (
            <div className="px-4 pb-2">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs">
                  <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                  <span>Agent Mode can take actions on your behalf. Review results before applying.</span>
                </div>
              </div>
            </div>
          )}

          {/* Input area */}
          <div className="border-t border-zinc-200 bg-white p-4">
            <form onSubmit={onSubmit} className="max-w-3xl mx-auto">
              <div
                className={cn(
                  "flex items-end gap-3 rounded-2xl border bg-zinc-50 p-2 transition-all",
                  "border-zinc-200 focus-within:border-emerald-400 focus-within:bg-white focus-within:shadow-lg focus-within:shadow-emerald-500/10"
                )}
              >
                <AssistantModelSelector
                  mode={mode}
                  modelOverride={modelOverride}
                  onModeChange={(next) => {
                    setMode(next)
                    persistPreferences(next, modelOverride)
                    inputRef.current?.focus()
                  }}
                  onModelChange={(next) => {
                    setModelOverride(next)
                    const nextMode = next ? inferModeFromModel(next) : mode
                    if (next) setMode(nextMode)
                    persistPreferences(nextMode, next)
                  }}
                />

                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value)
                    if (e.target.value.trim()) setFollowUpSuggestions([])
                  }}
                  onKeyDown={handleKeyDown}
                  placeholder={user ? `[${currentModeConfig.label}] ${currentModeConfig.placeholder}` : "Sign in to chat"}
                  disabled={!user || isBusy}
                  rows={1}
                  className="flex-1 bg-transparent text-zinc-900 placeholder:text-zinc-400 focus:outline-none text-sm resize-none min-h-[24px] max-h-[200px] py-1.5"
                  style={{ height: "24px" }}
                  onInput={(e) => {
                    const target = e.target as HTMLTextAreaElement
                    target.style.height = "24px"
                    target.style.height = Math.min(target.scrollHeight, 200) + "px"
                  }}
                />
                {input.length > 200 && (
                  <span className="text-[10px] text-zinc-400 self-end pb-1">{input.length}</span>
                )}

                {isStreaming ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => stop()}
                    aria-label="Stop generating"
                    className="h-8 px-3 gap-1.5 border-red-200 text-red-600 hover:bg-red-50"
                  >
                    <Square className="h-3 w-3 fill-current" />
                    Stop
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    size="sm"
                    aria-label={isBusy ? "Sending message" : "Send message"}
                    disabled={!user || !input.trim() || isBusy}
                    className={cn(
                      "h-8 w-8 p-0 bg-emerald-500 hover:bg-emerald-600",
                      "disabled:cursor-not-allowed disabled:opacity-40",
                      "transition-transform duration-150 active:scale-90",
                      input.trim() && !isBusy && "motion-safe:hover:scale-110",
                    )}
                  >
                    {isBusy ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    ) : (
                      <ArrowUp className="h-4 w-4" aria-hidden />
                    )}
                  </Button>
                )}
              </div>
              <p className="text-[10px] text-zinc-400 text-center mt-2">
                Gravitre Assistant may produce inaccurate information. Verify important details.
              </p>
            </form>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
