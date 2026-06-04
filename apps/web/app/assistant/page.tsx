"use client"

import { useEffect, useRef, useState, useMemo, useCallback } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { getSelectedOrgFromStorage, DEFAULT_DEMO_ORG_ID } from "@/lib/org-context"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  Send,
  Loader2,
  Sparkles,
  Check,
  ChevronDown,
  Copy,
  MessageSquarePlus,
  Database,
  Bot,
  Plug,
  Trash2,
  PanelLeftClose,
  PanelLeft,
  RefreshCw,
  Square,
  Zap,
  Brain,
  Gauge,
  AlertTriangle,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useAuth, getAccessToken } from "@/lib/auth-context"
import { toast } from "sonner"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeHighlight from "rehype-highlight"
import useSWR from "swr"
import { conversationsApi } from "@/lib/api"
import type { Conversation } from "@/types/api"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"

// localStorage key for message persistence
const STORAGE_KEY = "gravitre_assistant_messages"
const CONVERSATION_ID_KEY = "gravitre_last_conversation_id"
const MODE_KEY = "gravitre_assistant_mode"
const MAX_STORED_MESSAGES = 50

// Intelligence modes
type IntelligenceMode = "fast" | "standard" | "reasoning" | "agent"

interface ModeConfig {
  id: IntelligenceMode
  label: string
  icon: typeof Zap
  description: string
  placeholder: string
}

const intelligenceModes: ModeConfig[] = [
  { id: "fast", label: "Fast", icon: Zap, description: "Quick answers, simple tasks", placeholder: "Ask a quick question..." },
  { id: "standard", label: "Standard", icon: Gauge, description: "Balanced intelligence and speed", placeholder: "Ask anything about your AI team..." },
  { id: "reasoning", label: "Deep Reasoning", icon: Brain, description: "Complex analysis and planning", placeholder: "Describe a complex problem..." },
  { id: "agent", label: "Agent Mode", icon: Bot, description: "Autonomous task execution", placeholder: "Describe a task to execute..." },
]

// Gravitre-specific sample prompts
const samplePrompts = [
  { icon: Bot, label: "What agents are currently running?" },
  { icon: Database, label: "Show me failed workflows from today" },
  { icon: Sparkles, label: "How do I set up a new automation?" },
  { icon: Plug, label: "Which connectors have sync errors?" },
] as const

function parseChatError(error: Error): string {
  const raw = error.message?.trim() ?? ""
  if (!raw) return "Failed to send message"

  const fromBody = (() => {
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown; error?: unknown }
      if (typeof parsed.detail === "string" && parsed.detail) return parsed.detail
      if (typeof parsed.error === "string" && parsed.error) return parsed.error
    } catch {
      // Response body is plain text, not JSON.
    }
    return ""
  })()

  if (fromBody) {
    if (/payment required|budget|usage limit|402/i.test(fromBody)) {
      return "AI usage limit reached — check billing settings"
    }
    if (/too many|rate limit|429/i.test(fromBody)) {
      return "Too many requests — please wait a moment"
    }
    if (/disabled|killswitch|unavailable|503/i.test(fromBody)) {
      return "AI assistant is currently unavailable"
    }
    if (/organization|org_id|forbidden|403/i.test(fromBody)) {
      return "You don't have access to this organization"
    }
    if (/unauthorized|401/i.test(fromBody)) {
      return "Please sign in again to continue"
    }
    if (/FASTAPI_BASE_URL|not configured/i.test(fromBody)) {
      return "AI assistant is not configured — FASTAPI_BASE_URL is not set"
    }
    if (/unreachable|502|connection/i.test(fromBody)) {
      return "Could not reach the AI backend — check your connection"
    }
    return fromBody.length <= 180 ? fromBody : `${fromBody.slice(0, 177)}...`
  }

  if (/401|unauthorized/i.test(raw)) {
    return "Please sign in again to continue"
  }
  if (/402|payment required/i.test(raw)) {
    return "AI usage limit reached — check billing settings"
  }
  if (/403|forbidden/i.test(raw)) {
    return "You don't have access to this organization"
  }
  if (/429|too many requests/i.test(raw)) {
    return "Too many requests — please wait a moment"
  }
  if (/FASTAPI_BASE_URL|not configured/i.test(raw)) {
    return "AI assistant is not configured — FASTAPI_BASE_URL is not set"
  }
  if (/502|unreachable|fetch failed|ECONNREFUSED|connection/i.test(raw)) {
    return "Could not reach the AI backend — check your connection"
  }
  if (/503|disabled|killswitch|unavailable/i.test(raw)) {
    return "AI assistant is currently unavailable"
  }

  return raw.length <= 180 ? raw : "Failed to send message"
}

// Tool icons mapping
const toolIcons: Record<string, typeof Database> = {
  searchKnowledgeBase: Database,
  getAgentStatus: Bot,
  getConnectorStatus: Plug,
}

interface ToolInvocation {
  toolCallId: string
  toolName: string
  state: "call" | "result"
  result?: unknown
}

interface SourceCitation {
  title: string
  snippet: string
  relevance: number
}

// Loose view of an AI SDK v6 UIMessage part (text + dynamic tool parts).
interface UIPartLike {
  type: string
  text?: string
  toolCallId?: string
  state?: string
  output?: unknown
}

// Normalize a v6 UIMessage into the bits this UI renders.
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
      className="absolute top-2 right-2 p-1.5 rounded bg-zinc-200/80 hover:bg-zinc-300 transition-colors"
      title="Copy code"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-emerald-600" />
      ) : (
        <Copy className="h-3.5 w-3.5 text-zinc-500" />
      )}
    </button>
  )
}

// Extract plain text from markdown code children (no ref access during render).
function nodeToText(node: React.ReactNode): string {
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(nodeToText).join("")
  return ""
}

// Code block component with copy button
function CodeBlock({ children, className }: { children: React.ReactNode; className?: string }) {
  const language = className?.replace("language-", "") || ""
  const codeString = nodeToText(children)

  return (
    <div className="relative group my-3">
      {language && (
        <div className="absolute top-0 left-0 px-2 py-0.5 text-[10px] text-zinc-500 bg-zinc-100 rounded-br">
          {language}
        </div>
      )}
      <pre className="bg-zinc-50 border border-zinc-200 rounded-lg p-4 pt-6 overflow-x-auto">
        <code className={className}>
          {children}
        </code>
      </pre>
      <CopyButton code={codeString} />
    </div>
  )
}

// Tool activity chip component
function ToolChip({ invocation }: { invocation: ToolInvocation }) {
  const [expanded, setExpanded] = useState(false)
  const isComplete = invocation.state === "result"
  const Icon = toolIcons[invocation.toolName] || Database

  const getToolLabel = (name: string) => {
    switch (name) {
      case "searchKnowledgeBase":
        return "Searched knowledge base"
      case "getAgentStatus":
        return "Checked agent status"
      case "getConnectorStatus":
        return "Checked connector status"
      default:
        return name
    }
  }

  const formatResult = (result: unknown): string => {
    if (!result) return "No results"
    if (typeof result === "string") return result
    try {
      return JSON.stringify(result, null, 2)
    } catch {
      return String(result)
    }
  }

  return (
    <div className="my-2">
      <button
        onClick={() => isComplete && setExpanded(!expanded)}
        disabled={!isComplete}
        className={cn(
          "inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all",
          isComplete
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 cursor-pointer"
            : "bg-zinc-100 text-zinc-500 border border-zinc-200"
        )}
      >
        {isComplete ? (
          <Check className="h-3 w-3" />
        ) : (
          <Loader2 className="h-3 w-3 animate-spin" />
        )}
        <Icon className="h-3 w-3" />
        <span>{getToolLabel(invocation.toolName)}</span>
        {isComplete && (
          <ChevronDown
            className={cn(
              "h-3 w-3 transition-transform",
              expanded && "rotate-180"
            )}
          />
        )}
      </button>

      <AnimatePresence>
        {expanded && invocation.result ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-xs">
              <pre className="text-zinc-600 overflow-x-auto whitespace-pre-wrap">
                {formatResult(invocation.result)}
              </pre>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
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
        <span>{sources.length} source{sources.length !== 1 ? "s" : ""} used</span>
        <ChevronDown
          className={cn(
            "h-3 w-3 transition-transform",
            expanded && "rotate-180"
          )}
        />
      </button>

      <AnimatePresence>
        {expanded ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 space-y-2">
              {sources.map((source, i) => (
                <div
                  key={i}
                  className="p-2 rounded-lg bg-zinc-50 border border-zinc-200"
                >
                  <p className="text-xs font-medium text-zinc-700">{source.title}</p>
                  <p className="text-[11px] text-zinc-500 mt-1 line-clamp-2">
                    {source.snippet.slice(0, 100)}...
                  </p>
                </div>
              ))}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  )
}

// Helper to group conversations by date
function groupConversationsByDate(conversations: Conversation[]) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)

  const groups: { label: string; conversations: Conversation[] }[] = [
    { label: "Today", conversations: [] },
    { label: "Yesterday", conversations: [] },
    { label: "Last 7 days", conversations: [] },
    { label: "Older", conversations: [] },
  ]

  for (const conv of conversations) {
    const date = new Date(conv.updated_at)
    if (date >= today) {
      groups[0].conversations.push(conv)
    } else if (date >= yesterday) {
      groups[1].conversations.push(conv)
    } else if (date >= lastWeek) {
      groups[2].conversations.push(conv)
    } else {
      groups[3].conversations.push(conv)
    }
  }

  return groups.filter((g) => g.conversations.length > 0)
}

// Relative time formatter
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return "just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

// Conversation Sidebar Component
function ConversationSidebar({
  conversations,
  activeConversationId,
  onSelect,
  onNew,
  onDelete,
  isOpen,
  onToggle,
}: {
  conversations: Conversation[]
  activeConversationId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onDelete: (id: string) => void
  isOpen: boolean
  onToggle: () => void
}) {
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [conversationToDelete, setConversationToDelete] = useState<string | null>(null)

  const grouped = useMemo(() => groupConversationsByDate(conversations), [conversations])

  const handleDeleteClick = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setConversationToDelete(id)
    setDeleteDialogOpen(true)
  }

  const confirmDelete = () => {
    if (conversationToDelete) {
      onDelete(conversationToDelete)
      setConversationToDelete(null)
    }
    setDeleteDialogOpen(false)
  }

  return (
    <>
      {/* Mobile toggle button */}
      <Button
        variant="ghost"
        size="icon"
        onClick={onToggle}
        className="fixed top-20 left-4 z-40 md:hidden h-9 w-9 bg-white shadow-md border border-zinc-200"
      >
        {isOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
      </Button>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/20 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-40 w-60 flex flex-col border-r border-zinc-200 bg-white transition-transform duration-200",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-3 border-b border-zinc-200">
          <span className="text-sm font-semibold text-zinc-900">Conversations</span>
          <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onNew}>
            <MessageSquarePlus className="h-4 w-4" />
          </Button>
        </div>

        {/* Conversation list */}
        <ScrollArea className="flex-1">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
              <MessageSquarePlus className="h-8 w-8 text-zinc-300 mb-3" />
              <p className="text-xs text-zinc-500">
                No conversations yet. Start a new conversation above.
              </p>
            </div>
          ) : (
            <div className="py-2">
              {grouped.map((group) => (
                <div key={group.label} className="mb-2">
                  <div className="px-3 py-1.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                      {group.label}
                    </span>
                  </div>
                  {group.conversations.map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => onSelect(conv.id)}
                      className={cn(
                        "w-full group flex items-center gap-2 px-3 py-2 text-left transition-colors",
                        activeConversationId === conv.id
                          ? "bg-emerald-50 text-emerald-700"
                          : "hover:bg-zinc-50 text-zinc-700"
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{conv.title || "New conversation"}</p>
                        <p className="text-[10px] text-zinc-400">{formatRelativeTime(conv.updated_at)}</p>
                      </div>
                      <button
                        onClick={(e) => handleDeleteClick(conv.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-zinc-200 text-zinc-400 hover:text-red-500 transition-all"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </aside>

      {/* Delete confirmation dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this conversation and all its messages. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete} className="bg-red-500 hover:bg-red-600">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

// Intelligence Mode Selector
function ModeSelector({
  value,
  onChange,
}: {
  value: IntelligenceMode
  onChange: (mode: IntelligenceMode) => void
}) {
  const current = intelligenceModes.find((m) => m.id === value) || intelligenceModes[1]
  const Icon = current.icon

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-zinc-200 bg-white text-xs font-medium text-zinc-700 hover:bg-zinc-50 transition-colors">
          <Icon className="h-3.5 w-3.5" />
          <span>{current.label}</span>
          <ChevronDown className="h-3 w-3 text-zinc-400" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        {intelligenceModes.map((mode) => {
          const ModeIcon = mode.icon
          return (
            <DropdownMenuItem
              key={mode.id}
              onClick={() => onChange(mode.id)}
              className={cn("flex items-start gap-3 p-3", value === mode.id && "bg-emerald-50")}
            >
              <ModeIcon className={cn("h-4 w-4 mt-0.5", value === mode.id ? "text-emerald-600" : "text-zinc-500")} />
              <div className="flex-1">
                <p className={cn("text-sm font-medium", value === mode.id && "text-emerald-700")}>{mode.label}</p>
                <p className="text-xs text-zinc-500">{mode.description}</p>
              </div>
              {value === mode.id && <Check className="h-4 w-4 text-emerald-600" />}
            </DropdownMenuItem>
          )
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// Message component with markdown rendering
function ChatMessage({
  message,
  isUser,
  isLast,
  onCopy,
  onRegenerate,
}: {
  message: UIMessage
  isUser: boolean
  isLast?: boolean
  onCopy?: () => void
  onRegenerate?: () => void
}) {
  const { text, tools, sources } = normalizeMessage(message)
  const [showActions, setShowActions] = useState(false)

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(text)
    toast.success("Message copied")
    onCopy?.()
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
        <div className="flex-shrink-0 h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center ring-1 ring-emerald-200">
          <Sparkles className="h-4 w-4 text-emerald-600" />
        </div>
      )}

      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3",
          isUser
            ? "bg-emerald-600 text-white"
            : "bg-white text-zinc-900 border border-zinc-200 shadow-sm"
        )}
      >
        {/* Tool invocations */}
        {!isUser && tools.length > 0 && (
          <div className="space-y-1">
            {tools.map((tool) => (
              <ToolChip key={tool.toolCallId} invocation={tool} />
            ))}
          </div>
        )}

        {/* Message content */}
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{text}</p>
        ) : (
          <div className="prose prose-sm max-w-none prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-code:text-emerald-700 prose-code:bg-emerald-50 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeHighlight]}
              components={{
                pre: ({ children }) => <>{children}</>,
                code: ({ className, children, ...props }) => {
                  const isInline = !className
                  if (isInline) {
                    return (
                      <code className="text-emerald-700 bg-emerald-50 px-1 py-0.5 rounded" {...props}>
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
          </div>
        )}

        {/* Source citations */}
        {!isUser && sources.length > 0 && <SourceCitations sources={sources} />}

        {/* Message actions (copy, regenerate) */}
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

export default function AssistantPage() {
  const { user } = useAuth()
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null)
  
  // Intelligence mode state
  const [mode, setMode] = useState<IntelligenceMode>(() => {
    if (typeof window === "undefined") return "standard"
    return (localStorage.getItem(MODE_KEY) as IntelligenceMode) || "standard"
  })

  // Save mode to localStorage
  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode)
  }, [mode])

  // Fetch conversations list
  const { data: conversationsData, mutate: mutateConversations } = useSWR(
    user ? "conversations" : null,
    () => conversationsApi.list(),
    { fallbackData: { conversations: [] as Conversation[] }, revalidateOnFocus: false }
  )
  const conversations = conversationsData?.conversations ?? []

  // Hydrate once from localStorage (avoid re-reading on every render).
  const [initialMessages] = useState<UIMessage[]>(() => {
    if (typeof window === "undefined") return []
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

  // Transport forwards the Supabase JWT + selected org so the backend can
  // authenticate, enforce tenant isolation, and apply the governance layer.
  // All AI logic lives in the backend; /api/chat is a thin proxy.
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
            mode,
            conversation_id: activeConversationId,
            tools: ["knowledge_base", "agent_status", "connector_status"],
          }
        },
      }),
    [mode, activeConversationId]
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    messages: initialMessages,
    onError: (error) => {
      console.error("[v0] Chat error:", error)
      toast.error(parseChatError(error))
    },
  })

  const isLoading = status === "submitted" || status === "streaming"
  const isStreaming = status === "streaming"
  // Derived from state (no effect needed): true once any user message exists.
  const hasSentMessage = messages.some((m) => m.role === "user")
  const currentModeConfig = intelligenceModes.find((m) => m.id === mode) || intelligenceModes[1]

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      try {
        const toStore = messages.slice(-MAX_STORED_MESSAGES)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore))
      } catch {
        // Ignore storage errors
      }
    }
  }, [messages])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, status])

  // Handle new conversation
  const handleNewConversation = useCallback(() => {
    setMessages([])
    setActiveConversationId(null)
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(CONVERSATION_ID_KEY)
    inputRef.current?.focus()
    void mutateConversations()
  }, [setMessages, mutateConversations])

  // Handle selecting a conversation from sidebar
  const handleSelectConversation = useCallback(async (id: string) => {
    setActiveConversationId(id)
    localStorage.setItem(CONVERSATION_ID_KEY, id)
    // TODO: Load messages from API when backend supports it
    // For now, clear messages and let the conversation context be set
    setMessages([])
  }, [setMessages])

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
      toast.error("Failed to delete conversation")
    }
  }, [activeConversationId, handleNewConversation, mutateConversations])

  // Handle regenerate (retry last assistant message)
  const handleRegenerate = useCallback(() => {
    // Find the last user message and resend it
    const lastUserMessage = [...messages].reverse().find((m) => m.role === "user")
    if (lastUserMessage) {
      // Remove the last assistant message
      const withoutLastAssistant = messages.filter((m, i) => {
        if (i === messages.length - 1 && m.role === "assistant") return false
        return true
      })
      setMessages(withoutLastAssistant)
      // Re-submit the last user message
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
    // Refresh conversations to get the new/updated conversation
    void mutateConversations()
  }

  // Handle form submit
  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submitText(input)
  }

  // Handle enter key (submit on Enter, newline on Shift+Enter)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      submitText(input)
    }
  }

  return (
    <AppShell title="Assistant">
      <div className="flex h-full">
        {/* Conversation Sidebar */}
        <ConversationSidebar
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelect={handleSelectConversation}
          onNew={handleNewConversation}
          onDelete={handleDeleteConversation}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
        />

        {/* Main chat area */}
        <div className="flex-1 flex flex-col min-w-0 bg-zinc-50">
          {/* Header */}
          <div className="border-b border-zinc-200 px-4 md:px-6 py-3 md:py-4 bg-white">
            <div className="flex items-center justify-between max-w-4xl mx-auto">
              <div className="flex items-center gap-3">
                {/* Sidebar toggle for desktop */}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  className="hidden md:flex h-9 w-9"
                >
                  {sidebarOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeft className="h-4 w-4" />}
                </Button>
                <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-100 to-teal-100 ring-1 ring-emerald-200 shrink-0">
                  <Sparkles className="h-4 w-4 md:h-5 md:w-5 text-emerald-600" />
                </div>
                <div className="min-w-0">
                  <h1 className="text-base md:text-lg font-semibold text-zinc-900">Gravitre Assistant</h1>
                  <p className="text-xs md:text-sm text-zinc-500 truncate">
                    AI-powered help for your automation platform
                  </p>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNewConversation}
                className="gap-2 bg-white border-zinc-200 text-zinc-700 hover:bg-zinc-50 hover:text-zinc-900"
              >
                <MessageSquarePlus className="h-4 w-4" />
                <span className="hidden sm:inline">New chat</span>
              </Button>
            </div>
          </div>

          {/* Messages area */}
          <div className="flex-1 overflow-auto p-4 md:p-6">
          <div className="max-w-4xl mx-auto space-y-4">
            {!user ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center py-16 text-center"
              >
                <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center mb-6">
                  <Sparkles className="h-8 w-8 text-emerald-600" />
                </div>
                <h2 className="text-lg font-semibold text-zinc-900 mb-2">Sign in required</h2>
                <p className="text-sm text-zinc-500 max-w-md">
                  Sign in to use the Gravitre AI Assistant.
                </p>
              </motion.div>
            ) : messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center py-16 text-center"
              >
                <div className="relative mb-6">
                  <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center">
                    <Sparkles className="h-8 w-8 text-emerald-600" />
                  </div>
                  <motion.div
                    className="absolute inset-0 rounded-full border-2 border-emerald-300"
                    animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
                    transition={{ duration: 3, repeat: Infinity }}
                  />
                </div>
                <h2 className="text-lg font-semibold text-zinc-900 mb-2">
                  How can I help you today?
                </h2>
                <p className="text-sm text-zinc-500 mb-8 max-w-md">
                  I can help you manage agents, troubleshoot workflows, check connector status, and more.
                </p>

                {/* Sample prompts */}
                {!hasSentMessage && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg">
                    {samplePrompts.map((prompt, i) => {
                      const PromptIcon = prompt.icon
                      return (
                        <button
                          key={i}
                          onClick={() => submitText(prompt.label)}
                          className="flex items-center gap-3 px-4 py-3 rounded-xl border border-zinc-200 bg-white text-sm text-zinc-600 hover:text-zinc-900 hover:border-zinc-300 hover:bg-zinc-50 transition-all text-left shadow-sm"
                        >
                          <PromptIcon className="h-4 w-4 text-emerald-600 flex-shrink-0" />
                          <span>{prompt.label}</span>
                        </button>
                      )
                    })}
                  </div>
                )}
              </motion.div>
            ) : (
              <>
                {messages.map((message, index) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isUser={message.role === "user"}
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
                    <div className="flex-shrink-0 h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-100 to-teal-100 flex items-center justify-center ring-1 ring-emerald-200">
                      <Sparkles className="h-4 w-4 text-emerald-600" />
                    </div>
                    <div className="bg-white border border-zinc-200 rounded-2xl px-4 py-3 shadow-sm">
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 text-emerald-600 animate-spin" />
                        <span className="text-sm text-zinc-500">Thinking...</span>
                      </div>
                    </div>
                  </motion.div>
                )}

                <div ref={messagesEndRef} />
              </>
            )}
          </div>
          </div>

          {/* Agent Mode notice */}
        {mode === "agent" && (
          <div className="mx-4 mb-2">
            <div className="max-w-4xl mx-auto">
              <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs">
                <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" />
                <span>Agent Mode can take actions on your behalf. Review results before applying them.</span>
              </div>
            </div>
          </div>
        )}

        {/* Input area */}
        <div className="border-t border-zinc-200 p-4 bg-white">
          <form onSubmit={onSubmit} className="max-w-4xl mx-auto">
            <div
              className={cn(
                "flex items-end gap-3 rounded-xl border bg-white p-3 transition-all",
                "border-zinc-200 hover:border-zinc-300 focus-within:border-emerald-500 focus-within:ring-2 focus-within:ring-emerald-500/20"
              )}
            >
              {/* Mode selector */}
              <ModeSelector value={mode} onChange={setMode} />

              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={user ? currentModeConfig.placeholder : "Sign in to chat"}
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
              
              {/* Stop button (shown while streaming) */}
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
                  className="gap-2 bg-emerald-600 hover:bg-emerald-500 text-white"
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
              Assistant can make mistakes. Check important information.
            </p>
          </form>
        </div>
      </div>
      </div>
    </AppShell>
  )
}
