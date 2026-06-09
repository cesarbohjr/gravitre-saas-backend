"use client"

import { useEffect, useRef, useState, useMemo, useCallback } from "react"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport, type UIMessage } from "ai"
import { ensureSelectedOrg, buildChatOrgPayload } from "@/lib/org-context"
import { parseChatError } from "@/lib/chat-errors"
import { conversationMessageToUI } from "@/lib/chat-messages"
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
  MessageCircle,
  Search,
  ArrowUp,
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
const MAX_STORED_MESSAGES = 50

// Intelligence modes
type IntelligenceMode = "fast" | "standard" | "reasoning" | "agent"

interface ModeConfig {
  id: IntelligenceMode
  label: string
  icon: typeof Zap
  description: string
  placeholder: string
  color: string
}

const intelligenceModes: ModeConfig[] = [
  { id: "fast", label: "Fast", icon: Zap, description: "Quick answers", placeholder: "Ask a quick question...", color: "text-amber-500" },
  { id: "standard", label: "Standard", icon: Gauge, description: "Balanced", placeholder: "Ask anything about your AI team...", color: "text-emerald-500" },
  { id: "reasoning", label: "Reasoning", icon: Brain, description: "Deep analysis", placeholder: "Describe a complex problem...", color: "text-violet-500" },
  { id: "agent", label: "Agent", icon: Bot, description: "Autonomous", placeholder: "Describe a task to execute...", color: "text-sky-500" },
]

// Gravitre-specific sample prompts
const samplePrompts = [
  { icon: Bot, label: "What agents are currently active?", category: "Agents" },
  { icon: Database, label: "Show failed workflows from today", category: "Workflows" },
  { icon: Sparkles, label: "How do I create a new automation?", category: "Help" },
  { icon: Plug, label: "Which connectors have sync errors?", category: "Connectors" },
] as const

// Tool icons mapping
const toolIcons: Record<string, typeof Database> = {
  searchKnowledgeBase: Search,
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

// Tool activity chip component
function ToolChip({ invocation }: { invocation: ToolInvocation }) {
  const [expanded, setExpanded] = useState(false)
  const isComplete = invocation.state === "result"
  const Icon = toolIcons[invocation.toolName] || Database

  const getToolLabel = (name: string) => {
    switch (name) {
      case "searchKnowledgeBase": return "Searched knowledge base"
      case "getAgentStatus": return "Checked agent status"
      case "getConnectorStatus": return "Checked connector status"
      default: return name
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
          "inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
          isComplete
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20 cursor-pointer"
            : "bg-zinc-800 text-zinc-400 border border-zinc-700"
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
          <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} />
        )}
      </button>

      <AnimatePresence>
        {expanded && invocation.result != null && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-2 p-3 rounded-lg bg-zinc-900 border border-zinc-800 text-xs">
              <pre className="text-zinc-300 overflow-x-auto whitespace-pre-wrap font-mono">
                {formatResult(invocation.result)}
              </pre>
            </div>
          </motion.div>
        )}
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

function groupConversationsByDate(conversations: Conversation[]) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000)

  const groups: { label: string; conversations: Conversation[] }[] = [
    { label: "Today", conversations: [] },
    { label: "Yesterday", conversations: [] },
    { label: "Previous 7 days", conversations: [] },
    { label: "Older", conversations: [] },
  ]

  for (const conv of conversations) {
    const date = new Date(conv.updated_at)
    if (date >= today) groups[0].conversations.push(conv)
    else if (date >= yesterday) groups[1].conversations.push(conv)
    else if (date >= lastWeek) groups[2].conversations.push(conv)
    else groups[3].conversations.push(conv)
  }

  return groups.filter((g) => g.conversations.length > 0)
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return "now"
  if (diffMins < 60) return `${diffMins}m`
  if (diffHours < 24) return `${diffHours}h`
  if (diffDays < 7) return `${diffDays}d`
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" })
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
      {isOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden backdrop-blur-sm" onClick={onToggle} />}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-40 w-64 flex flex-col bg-zinc-50 border-r border-zinc-200 transition-all duration-300",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-zinc-200 bg-white">
          <span className="text-sm font-semibold text-zinc-900">History</span>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8 text-zinc-500 hover:text-zinc-900" onClick={onNew}>
                  <MessageSquarePlus className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">New conversation</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Conversation list */}
        <ScrollArea className="flex-1">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <div className="h-12 w-12 rounded-full bg-zinc-200 flex items-center justify-center mb-4">
                <MessageCircle className="h-5 w-5 text-zinc-400" />
              </div>
              <p className="text-sm font-medium text-zinc-600 mb-1">No conversations</p>
              <p className="text-xs text-zinc-400">Start a new chat to begin</p>
            </div>
          ) : (
            <div className="py-2">
              {grouped.map((group) => (
                <div key={group.label} className="mb-1">
                  <div className="px-4 py-2">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400">
                      {group.label}
                    </span>
                  </div>
                  {group.conversations.map((conv) => (
                    <button
                      key={conv.id}
                      onClick={() => onSelect(conv.id)}
                      className={cn(
                        "w-full group flex items-center gap-3 px-4 py-2.5 text-left transition-all",
                        activeConversationId === conv.id
                          ? "bg-emerald-50 border-r-2 border-emerald-500"
                          : "hover:bg-zinc-100"
                      )}
                    >
                      <div className="flex-1 min-w-0">
                        <p className={cn(
                          "text-sm truncate",
                          activeConversationId === conv.id ? "text-emerald-700 font-medium" : "text-zinc-700"
                        )}>
                          {conv.title || "New conversation"}
                        </p>
                        <p className="text-[10px] text-zinc-400 mt-0.5">{formatRelativeTime(conv.updated_at)}</p>
                      </div>
                      <button
                        onClick={(e) => handleDeleteClick(conv.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-red-100 text-zinc-400 hover:text-red-500 transition-all"
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
              This will permanently delete this conversation. This action cannot be undone.
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
function ModeSelector({ value, onChange }: { value: IntelligenceMode; onChange: (mode: IntelligenceMode) => void }) {
  const current = intelligenceModes.find((m) => m.id === value) || intelligenceModes[1]
  const Icon = current.icon

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className={cn(
          "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all",
          "border-zinc-200 bg-white hover:bg-zinc-50 text-zinc-700"
        )}>
          <Icon className={cn("h-3.5 w-3.5", current.color)} />
          <span>{current.label}</span>
          <ChevronDown className="h-3 w-3 text-zinc-400 ml-0.5" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-48">
        {intelligenceModes.map((mode) => {
          const ModeIcon = mode.icon
          return (
            <DropdownMenuItem
              key={mode.id}
              onClick={() => onChange(mode.id)}
              className={cn("flex items-center gap-3 py-2.5", value === mode.id && "bg-emerald-50")}
            >
              <ModeIcon className={cn("h-4 w-4", mode.color)} />
              <div className="flex-1">
                <p className={cn("text-sm font-medium", value === mode.id && "text-emerald-700")}>{mode.label}</p>
                <p className="text-[10px] text-zinc-500">{mode.description}</p>
              </div>
              {value === mode.id && <Check className="h-3.5 w-3.5 text-emerald-600" />}
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
  onRegenerate,
}: {
  message: UIMessage
  isUser: boolean
  isLast?: boolean
  onRegenerate?: () => void
}) {
  const { text, tools, sources } = normalizeMessage(message)
  const [copied, setCopied] = useState(false)

  const handleCopyMessage = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    toast.success("Copied to clipboard")
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn("flex gap-4", isUser ? "justify-end" : "justify-start")}
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
                <ToolChip key={tool.toolCallId} invocation={tool} />
              ))}
            </div>
          )}

          {/* Message content */}
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{text}</p>
          ) : (
            <div className="prose prose-sm max-w-none prose-p:my-2 prose-p:leading-relaxed prose-headings:my-3 prose-headings:font-semibold prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-code:text-emerald-700 prose-code:bg-emerald-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-strong:font-semibold">
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
            </div>
          )}

          {/* Source citations */}
          {!isUser && sources.length > 0 && <SourceCitations sources={sources} />}
        </div>

        {/* Message actions */}
        {!isUser && (
          <div className="flex items-center gap-1 mt-2 ml-1 opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity">
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

export default function AssistantPage() {
  const { user } = useAuth()
  const [input, setInput] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const activeConversationIdRef = useRef<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [activeConversationId, setActiveConversationId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null
    return localStorage.getItem(CONVERSATION_ID_KEY)
  })

  // Intelligence mode state
  const [mode, setMode] = useState<IntelligenceMode>(() => {
    if (typeof window === "undefined") return "standard"
    return (localStorage.getItem(MODE_KEY) as IntelligenceMode) || "standard"
  })

  // Save mode to localStorage
  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode)
  }, [mode])

  // Resolve org from membership before first chat request (replaces stale demo org in storage).
  useEffect(() => {
    if (user) void ensureSelectedOrg(true)
  }, [user])

  // Fetch conversations list
  const { data: conversationsData, mutate: mutateConversations } = useSWR(
    user ? "conversations" : null,
    () => conversationsApi.list(),
    { fallbackData: { conversations: [] as Conversation[] }, revalidateOnFocus: false }
  )
  const conversations = conversationsData?.conversations ?? []

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

  // Transport configuration
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
          }
        },
        body: () => ({
          ...buildChatOrgPayload(),
          mode,
          conversation_id: activeConversationId,
          tools: ["knowledge_base", "agent_status", "connector_status"],
        }),
      }),
    [mode, activeConversationId],
  )

  const { messages, sendMessage, status, setMessages, stop } = useChat({
    transport,
    messages: initialMessages,
    onError: (error) => {
      console.error("[v0] Chat error:", error)
      toast.error(parseChatError(error))
    },
    onFinish: () => {
      void mutateConversations()
    },
  })

  const isLoading = status === "submitted" || status === "streaming"
  const isStreaming = status === "streaming"
  const hasSentMessage = messages.some((m) => m.role === "user")
  const currentModeConfig = intelligenceModes.find((m) => m.id === mode) || intelligenceModes[1]

  // Keep ref in sync for transport body closure.
  useEffect(() => {
    activeConversationIdRef.current = activeConversationId
  }, [activeConversationId])

  // Hydrate active conversation messages from API when restoring last session.
  useEffect(() => {
    if (!user || !activeConversationId || messages.length > 0) return
    let cancelled = false
    void conversationsApi.getMessages(activeConversationId).then(({ messages: stored }) => {
      if (cancelled || stored.length === 0) return
      setMessages(stored.map(conversationMessageToUI))
    }).catch(() => {
      // Ignore — user can start a fresh thread.
    })
    return () => {
      cancelled = true
    }
  }, [user, activeConversationId, messages.length, setMessages])

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
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(CONVERSATION_ID_KEY)
    inputRef.current?.focus()
    void mutateConversations()
  }, [setMessages, mutateConversations])

  // Handle selecting a conversation from sidebar
  const handleSelectConversation = useCallback(async (id: string) => {
    setActiveConversationId(id)
    activeConversationIdRef.current = id
    localStorage.setItem(CONVERSATION_ID_KEY, id)
    localStorage.removeItem(STORAGE_KEY)
    try {
      const { messages: stored } = await conversationsApi.getMessages(id)
      setMessages(stored.map(conversationMessageToUI))
    } catch (error) {
      console.error("[v0] Load conversation failed:", error)
      setMessages([])
      toast.error("Failed to load conversation")
    }
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

  const submitText = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isLoading) return

    const orgId = await ensureSelectedOrg(true)
    if (!orgId) {
      toast.error("Organization required — complete onboarding or contact your admin")
      return
    }

    if (!activeConversationIdRef.current) {
      try {
        const created = await conversationsApi.create({ title: trimmed.slice(0, 80) })
        activeConversationIdRef.current = created.id
        setActiveConversationId(created.id)
        localStorage.setItem(CONVERSATION_ID_KEY, created.id)
        await mutateConversations()
      } catch (error) {
        console.error("[v0] Create conversation failed:", error)
        toast.error(
          parseChatError(error instanceof Error ? error : new Error("Could not start a new conversation"))
        )
        return
      }
    }

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
    <AppShell title="Assistant">
      <div className="flex h-full bg-zinc-50">
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
                <h1 className="text-sm font-semibold text-zinc-900">Gravitre Assistant</h1>
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
                    How can I help you today?
                  </h2>
                  <p className="text-sm text-zinc-500 mb-10 max-w-md">
                    I can help manage agents, troubleshoot workflows, check connector status, and answer questions about your automation platform.
                  </p>

                  {/* Sample prompts grid */}
                  {!hasSentMessage && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
                      {samplePrompts.map((prompt, i) => {
                        const PromptIcon = prompt.icon
                        return (
                          <motion.button
                            key={i}
                            initial={{ opacity: 0, y: 10 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.1 }}
                            onClick={() => submitText(prompt.label)}
                            className="group flex items-start gap-3 p-4 rounded-xl border border-zinc-200 bg-white text-left hover:border-emerald-300 hover:shadow-md hover:shadow-emerald-500/10 transition-all"
                          >
                            <div className="h-8 w-8 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0 group-hover:bg-emerald-100 transition-colors">
                              <PromptIcon className="h-4 w-4 text-emerald-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-emerald-600 mb-1">{prompt.category}</p>
                              <p className="text-sm text-zinc-700 group-hover:text-zinc-900">{prompt.label}</p>
                            </div>
                          </motion.button>
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

                  {isLoading && !isStreaming && <TypingIndicator />}

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
                <ModeSelector value={mode} onChange={setMode} />

                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={user ? currentModeConfig.placeholder : "Sign in to chat"}
                  disabled={!user || isLoading}
                  rows={1}
                  className="flex-1 bg-transparent text-zinc-900 placeholder:text-zinc-400 focus:outline-none text-sm resize-none min-h-[24px] max-h-[120px] py-1.5"
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
                    className="h-8 px-3 gap-1.5 border-red-200 text-red-600 hover:bg-red-50"
                  >
                    <Square className="h-3 w-3 fill-current" />
                    Stop
                  </Button>
                ) : (
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!user || !input.trim() || isLoading}
                    className="h-8 w-8 p-0 bg-emerald-500 hover:bg-emerald-600 disabled:opacity-50"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <ArrowUp className="h-4 w-4" />
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
