"use client"

// Knowledge Search - Terminal-style Query Interface
import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
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
} from "lucide-react"
import { cn } from "@/lib/utils"
import Link from "next/link"

interface RAGResult {
  id: string
  score: number
  sourceId: string
  sourceName: string
  documentName?: string
  chunkIndex: number
  chunkText: string
  highlightedText?: string
}

const sampleQueries = [
  "How does customer sync work?",
  "What happens when a workflow fails?",
  "Explain the retry logic for connectors",
  "How are approvals routed?",
]

const fallbackResults: RAGResult[] = [
  {
    id: "1",
    score: 0.94,
    sourceId: "src-salesforce",
    sourceName: "salesforce-api",
    documentName: "Customer Sync Guide",
    chunkIndex: 12,
    chunkText: "The customer synchronization process runs every 15 minutes and pulls updated records from Salesforce. Failed syncs are automatically retried up to 3 times with exponential backoff.",
  },
  {
    id: "2",
    score: 0.87,
    sourceId: "src-postgres",
    sourceName: "postgres-replica",
    documentName: "Data Pipeline Architecture",
    chunkIndex: 8,
    chunkText: "Data transformations are applied in stages: extraction, normalization, enrichment, and loading. Each stage produces intermediate artifacts that can be inspected for debugging.",
  },
  {
    id: "3",
    score: 0.82,
    sourceId: "src-salesforce",
    sourceName: "salesforce-api",
    chunkIndex: 45,
    chunkText: "Error handling for API rate limits follows a circuit breaker pattern. When rate limits are exceeded, the connector enters a cooldown period and queues subsequent requests.",
  },
]

// Terminal Input with typing effect
function TerminalInput({ 
  value, 
  onChange, 
  onSubmit, 
  isProcessing,
  placeholder,
}: { 
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  isProcessing: boolean
  placeholder: string
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isFocused, setIsFocused] = useState(false)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  return (
    <div 
      className={cn(
        "flex items-center gap-3 rounded-lg border bg-card p-4 transition-all cursor-text",
        isFocused ? "border-blue-500/50 ring-2 ring-blue-500/20" : "border-border hover:border-foreground/20"
      )}
      onClick={() => inputRef.current?.focus()}
    >
      <div className="flex items-center gap-2 text-muted-foreground">
        <Terminal className="h-4 w-4" />
        <ChevronRight className="h-3 w-3" />
      </div>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !isProcessing) {
            onSubmit()
          }
        }}
        placeholder={placeholder}
        disabled={isProcessing}
        className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/50 focus:outline-none font-mono text-sm"
      />
      <div className="flex items-center gap-2">
        {isProcessing ? (
          <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
        ) : (
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <CornerDownLeft className="h-3 w-3" />
            <span>Enter</span>
          </div>
        )}
      </div>
    </div>
  )
}

// Typewriter effect for AI responses
function TypewriterText({ text, onComplete }: { text: string; onComplete?: () => void }) {
  const [displayedText, setDisplayedText] = useState("")
  const [isComplete, setIsComplete] = useState(false)

  useEffect(() => {
    let index = 0
    const interval = setInterval(() => {
      if (index < text.length) {
        setDisplayedText(text.slice(0, index + 1))
        index++
      } else {
        clearInterval(interval)
        setIsComplete(true)
        onComplete?.()
      }
    }, 15)
    return () => clearInterval(interval)
  }, [text, onComplete])

  return (
    <span>
      {displayedText}
      {!isComplete && <span className="animate-pulse">|</span>}
    </span>
  )
}

// Result Card with source highlighting
function ResultCard({ result, index }: { result: RAGResult; index: number }) {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="group rounded-lg border border-border bg-card/50 overflow-hidden hover:border-foreground/20 transition-colors"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-secondary/30 border-b border-border/50">
        <div className="flex items-center gap-3">
          {/* Score badge */}
          <div className={cn(
            "flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold",
            result.score >= 0.9 ? "bg-emerald-500/10 text-emerald-400" :
            result.score >= 0.8 ? "bg-blue-500/10 text-blue-400" :
            "bg-amber-500/10 text-amber-400"
          )}>
            <Zap className="h-2.5 w-2.5" />
            {Math.round(result.score * 100)}%
          </div>
          
          {/* Source */}
          <div className="flex items-center gap-2">
            <Database className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs font-mono text-muted-foreground">{result.sourceName}</span>
          </div>
          
          {result.documentName && (
            <>
              <span className="text-muted-foreground/30">/</span>
              <div className="flex items-center gap-2">
                <FileText className="h-3 w-3 text-muted-foreground" />
                <span className="text-xs font-mono text-muted-foreground">{result.documentName}</span>
              </div>
            </>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-muted-foreground/50 font-mono">
            <Hash className="h-2.5 w-2.5 inline" />{result.chunkIndex}
          </span>
          <Link
            href={`/sources/${result.sourceId}`}
            className="opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <ExternalLink className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        <p className={cn(
          "text-sm text-foreground/90 leading-relaxed font-mono",
          !isExpanded && "line-clamp-3"
        )}>
          {result.chunkText}
        </p>
        {result.chunkText.length > 200 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="mt-2 text-xs text-blue-400 hover:text-blue-300"
          >
            {isExpanded ? "Show less" : "Show more"}
          </button>
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
  resultCount: number
}

export default function ChatPage() {
  const [query, setQuery] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [results, setResults] = useState<RAGResult[]>([])
  const [showResults, setShowResults] = useState(false)
  const [aiSummary, setAiSummary] = useState("")
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [placeholderIndex, setPlaceholderIndex] = useState(0)

  // Rotate placeholder
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((i) => (i + 1) % sampleQueries.length)
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  const handleSearch = async () => {
    if (!query.trim()) return

    setIsProcessing(true)
    setShowResults(false)
    setAiSummary("")
    setResults([])

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 1500))

    setResults(fallbackResults)
    setShowResults(true)

    // Add to history
    setHistory((prev) => [
      { id: Date.now().toString(), query, timestamp: new Date(), resultCount: fallbackResults.length },
      ...prev.slice(0, 9),
    ])

    // Generate AI summary
    setAiSummary(
      "Based on the retrieved documents, customer synchronization runs on a 15-minute interval with automatic retry logic. The system uses a circuit breaker pattern for rate limiting and applies data transformations in four stages: extraction, normalization, enrichment, and loading."
    )

    setIsProcessing(false)
  }

  return (
    <AppShell title="Knowledge Search">
      <div className="flex h-full flex-col md:flex-row">
        {/* Main Query Area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Header */}
          <div className="border-b border-border px-4 md:px-6 py-3 md:py-4 bg-gradient-to-r from-card to-secondary/20">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 ring-1 ring-emerald-500/20 shrink-0">
                <BookOpen className="h-4 w-4 md:h-5 md:w-5 text-emerald-400" />
              </div>
              <div className="min-w-0">
                <h1 className="text-base md:text-lg font-semibold text-foreground">Knowledge Search</h1>
                <p className="text-xs md:text-sm text-muted-foreground truncate">Query your connected data sources</p>
              </div>
            </div>
          </div>

          {/* Query Interface */}
          <div className="flex-1 p-4 md:p-6 overflow-auto">
            <div className="max-w-3xl mx-auto">
              {/* Terminal Input */}
              <div className="mb-6">
                <TerminalInput
                  value={query}
                  onChange={setQuery}
                  onSubmit={handleSearch}
                  isProcessing={isProcessing}
                  placeholder={sampleQueries[placeholderIndex]}
                />
              </div>

              {/* Sample Queries */}
              {!showResults && !isProcessing && (
                <motion.div 
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="mb-8"
                >
                  <p className="text-xs text-muted-foreground mb-3">Try asking:</p>
                  <div className="flex flex-wrap gap-2">
                    {sampleQueries.map((q, i) => (
                      <button
                        key={i}
                        onClick={() => setQuery(q)}
                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-card/50 text-sm text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors"
                      >
                        <ArrowRight className="h-3 w-3" />
                        {q}
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}

              {/* Processing State */}
              {isProcessing && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex flex-col items-center justify-center py-16"
                >
                  <div className="relative">
                    <div className="h-16 w-16 rounded-full border-2 border-blue-500/30 flex items-center justify-center">
                      <Sparkles className="h-6 w-6 text-blue-400" />
                    </div>
                    <motion.div
                      className="absolute inset-0 rounded-full border-2 border-blue-500 border-t-transparent"
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                    />
                  </div>
                  <p className="mt-4 text-sm text-muted-foreground font-mono">
                    Searching knowledge base...
                  </p>
                </motion.div>
              )}

              {/* Results */}
              <AnimatePresence>
                {showResults && (
                  <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="space-y-6"
                  >
                    {/* AI Summary */}
                    {aiSummary && (
                      <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
                        <div className="flex items-center gap-2 mb-2">
                          <Sparkles className="h-4 w-4 text-emerald-400" />
                          <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                            AI Summary
                          </span>
                        </div>
                        <p className="text-sm text-foreground/90 leading-relaxed">
                          <TypewriterText text={aiSummary} />
                        </p>
                      </div>
                    )}

                    {/* Results Header */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Layers className="h-4 w-4 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">
                          Found <span className="text-foreground font-medium">{results.length}</span> relevant chunks
                        </span>
                      </div>
                    </div>

                    {/* Result Cards */}
                    <div className="space-y-3">
                      {results.map((result, index) => (
                        <ResultCard key={result.id} result={result} index={index} />
                      ))}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
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
                    onClick={() => setQuery(entry.query)}
                    className="w-full p-3 rounded-lg text-left hover:bg-secondary/50 transition-colors group"
                  >
                    <p className="text-sm text-foreground truncate group-hover:text-blue-400 transition-colors">
                      {entry.query}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-muted-foreground">
                        {entry.timestamp.toLocaleTimeString()}
                      </span>
                      <span className="text-[10px] text-muted-foreground/50">|</span>
                      <span className="text-[10px] text-muted-foreground">
                        {entry.resultCount} results
                      </span>
                    </div>
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
