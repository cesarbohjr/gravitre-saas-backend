"use client"

// AI Assistant - Conversational interface with RAG and tool calling
import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { useChat } from "@ai-sdk/react"
import { DefaultChatTransport } from "ai"
import { AppShell } from "@/components/gravitre/app-shell"
import { 
  Search, 
  FileText, 
  Database, 
  Loader2, 
  Terminal,
  ChevronRight,
  ExternalLink,
  Sparkles,
  Clock,
  Zap,
  BookOpen,
  ArrowRight,
  CornerDownLeft,
  Hash,
  Layers,
  Bot,
  User,
  Send,
  RefreshCw,
  Copy,
  Check,
} from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"
import { Button } from "@/components/ui/button"

const sampleQueries = [
  "What's the status of my agents?",
  "How does customer sync work?",
  "Which connectors have errors?",
  "Help me troubleshoot HubSpot",
]

// Message component
function ChatMessage({ message, isLatest }: { message: any; isLatest: boolean }) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === "user"
  
  // Extract text from parts
  const text = message.parts
    ?.filter((p: any) => p.type === "text")
    .map((p: any) => p.text)
    .join("") || ""
  
  // Check for tool calls
  const toolCalls = message.parts?.filter((p: any) => p.type === "tool-invocation") || []
  
  const handleCopy = () => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "flex gap-3 px-4 py-3 rounded-xl",
        isUser 
          ? "bg-blue-500/10 border border-blue-500/20" 
          : "bg-card border border-border"
      )}
    >
      {/* Avatar */}
      <div className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
        isUser 
          ? "bg-blue-500/20 text-blue-400" 
          : "bg-gradient-to-br from-emerald-500/20 to-teal-500/20 text-emerald-400"
      )}>
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-muted-foreground">
            {isUser ? "You" : "Gravitre AI"}
          </span>
          {!isUser && text && (
            <button
              onClick={handleCopy}
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              {copied ? (
                <Check className="h-3.5 w-3.5 text-emerald-400" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>
        
        {/* Text content */}
        {text && (
          <div className="prose prose-sm prose-invert max-w-none">
            <p className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap">
              {text}
              {isLatest && !isUser && <span className="animate-pulse ml-0.5">|</span>}
            </p>
          </div>
        )}
        
        {/* Tool invocations */}
        {toolCalls.length > 0 && (
          <div className="mt-3 space-y-2">
            {toolCalls.map((tool: any, i: number) => (
              <div key={i} className="rounded-lg bg-secondary/50 border border-border/50 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="h-3.5 w-3.5 text-amber-400" />
                  <span className="text-xs font-medium text-amber-400">
                    {tool.toolName}
                  </span>
                  {tool.state === "output-available" && (
                    <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded">
                      Complete
                    </span>
                  )}
                  {(tool.state === "input-streaming" || tool.state === "input-available") && (
                    <Loader2 className="h-3 w-3 text-blue-400 animate-spin" />
                  )}
                </div>
                {tool.output && (
                  <pre className="text-[11px] text-muted-foreground bg-background/50 rounded p-2 overflow-x-auto">
                    {JSON.stringify(tool.output, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

// Command history entry
interface HistoryEntry {
  id: string
  query: string
  timestamp: Date
}

export default function ChatPage() {
  const [input, setInput] = useState("")
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  
  // AI SDK useChat hook
  const { messages, sendMessage, status, setMessages } = useChat({
    transport: new DefaultChatTransport({ api: "/api/chat" }),
  })
  
  const isLoading = status === "streaming" || status === "submitted"

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isLoading) return
    
    // Send message
    sendMessage({ text: input })
    
    // Add to history
    setHistory((prev) => [
      { id: Date.now().toString(), query: input, timestamp: new Date() },
      ...prev.slice(0, 9),
    ])
    
    setInput("")
  }

  const handleSampleQuery = (query: string) => {
    setInput(query)
    inputRef.current?.focus()
  }

  const handleClearChat = () => {
    setMessages([])
  }

  return (
    <AppShell title="AI Assistant">
      <div className="flex h-full flex-col md:flex-row">
        {/* Main Chat Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="border-b border-border px-4 md:px-6 py-3 md:py-4 bg-gradient-to-r from-card to-secondary/20">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 ring-1 ring-emerald-500/20 shrink-0">
                  <Bot className="h-4 w-4 md:h-5 md:w-5 text-emerald-400" />
                </div>
                <div className="min-w-0">
                  <h1 className="text-base md:text-lg font-semibold text-foreground">AI Assistant</h1>
                  <p className="text-xs md:text-sm text-muted-foreground truncate">
                    Ask questions about your data and automations
                  </p>
                </div>
              </div>
              {messages.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearChat}
                  className="gap-2"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Clear
                </Button>
              )}
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-4 md:p-6 overflow-auto">
            <div className="max-w-3xl mx-auto space-y-4">
              {messages.length === 0 ? (
                // Empty state
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <div className="relative mb-6">
                    <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center">
                      <Sparkles className="h-8 w-8 text-emerald-400" />
                    </div>
                    <motion.div
                      className="absolute inset-0 rounded-full border-2 border-emerald-500/30"
                      animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0, 0.5] }}
                      transition={{ duration: 3, repeat: Infinity }}
                    />
                  </div>
                  <h2 className="text-lg font-semibold text-foreground mb-2">
                    How can I help you today?
                  </h2>
                  <p className="text-sm text-muted-foreground mb-8 max-w-md">
                    I can help you understand your automations, troubleshoot issues, and find information in your knowledge base.
                  </p>
                  
                  {/* Sample queries */}
                  <div className="flex flex-wrap justify-center gap-2">
                    {sampleQueries.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => handleSampleQuery(q)}
                        className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card/50 text-sm text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
                      >
                        <ArrowRight className="h-3 w-3" />
                        {q}
                      </button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                // Messages
                <>
                  {messages.map((message, index) => (
                    <ChatMessage 
                      key={message.id} 
                      message={message} 
                      isLatest={index === messages.length - 1 && status === "streaming"}
                    />
                  ))}
                  
                  {/* Streaming indicator */}
                  {status === "submitted" && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex items-center gap-2 px-4 py-3"
                    >
                      <Loader2 className="h-4 w-4 text-emerald-400 animate-spin" />
                      <span className="text-sm text-muted-foreground">Thinking...</span>
                    </motion.div>
                  )}
                </>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input Area */}
          <div className="border-t border-border p-4 bg-card/50">
            <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
              <div className={cn(
                "flex items-center gap-3 rounded-lg border bg-card p-3 transition-all",
                "border-border hover:border-foreground/20 focus-within:border-blue-500/50 focus-within:ring-2 focus-within:ring-blue-500/20"
              )}>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Terminal className="h-4 w-4" />
                  <ChevronRight className="h-3 w-3" />
                </div>
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask me anything..."
                  disabled={isLoading}
                  className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/50 focus:outline-none text-sm"
                />
                <Button
                  type="submit"
                  size="sm"
                  disabled={!input.trim() || isLoading}
                  className="gap-2"
                >
                  {isLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <p className="text-[10px] text-muted-foreground text-center mt-2">
                Press Enter to send or click the send button
              </p>
            </form>
          </div>
        </div>

        {/* Right - History Panel - hidden on mobile */}
        <div className="hidden lg:flex w-72 border-l border-border bg-card/30 flex-col">
          <div className="p-4 border-b border-border">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <h2 className="text-sm font-semibold text-foreground">Recent Queries</h2>
            </div>
          </div>
          
          <div className="flex-1 overflow-auto p-2">
            {history.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                <Terminal className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-xs text-muted-foreground">
                  Your query history will appear here
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                {history.map((entry) => (
                  <button
                    key={entry.id}
                    onClick={() => handleSampleQuery(entry.query)}
                    className="w-full p-3 rounded-lg text-left hover:bg-secondary/50 transition-colors group"
                  >
                    <p className="text-sm text-foreground truncate group-hover:text-blue-400 transition-colors">
                      {entry.query}
                    </p>
                    <span className="text-[10px] text-muted-foreground">
                      {entry.timestamp.toLocaleTimeString()}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
