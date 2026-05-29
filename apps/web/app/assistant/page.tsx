"use client"

import { useState, useRef, useEffect } from "react"
import { useChat } from "@ai-sdk/react"
import { motion } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import { Sparkles, Send, Loader2, Square, RotateCcw, Bot, User, Search, Wrench } from "lucide-react"

const SAMPLE_PROMPTS = [
  "Which connectors have sync errors right now?",
  "Summarize what my agents did today",
  "How do my workflows use Salesforce?",
  "What's in our knowledge base about onboarding?",
]

// Friendly labels for tool activity surfaced in the stream.
const TOOL_LABELS: Record<string, { label: string; icon: typeof Search }> = {
  searchKnowledgeBase: { label: "Searching knowledge base", icon: Search },
  getAgentStatus: { label: "Checking agent status", icon: Bot },
  getConnectorStatus: { label: "Checking connectors", icon: Wrench },
}

type MessagePart = {
  type: string
  text?: string
  state?: string
}

function ToolChip({ part }: { part: MessagePart }) {
  const toolName = part.type.replace(/^tool-/, "")
  const meta = TOOL_LABELS[toolName] ?? { label: toolName, icon: Wrench }
  const ToolIcon = meta.icon
  const done = part.state === "output-available"
  return (
    <div className="inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/40 px-2.5 py-1 text-xs text-muted-foreground">
      <ToolIcon className="h-3 w-3 text-emerald-400" />
      <span>{done ? `${meta.label} \u2713` : `${meta.label}\u2026`}</span>
    </div>
  )
}

export default function AssistantPage() {
  const { user } = useAuth()
  const { messages, sendMessage, status, error, stop, regenerate } = useChat()
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)

  const isBusy = status === "submitted" || status === "streaming"

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" })
  }, [messages, status])

  const submit = (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || isBusy) return
    sendMessage({ text: trimmed })
    setInput("")
  }

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    submit(input)
  }

  return (
    <AppShell title="Assistant">
      <div className="flex h-full flex-col">
        {/* Header */}
        <div className="border-b border-border px-4 md:px-6 py-3 md:py-4 bg-gradient-to-r from-card to-secondary/20">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 md:h-10 md:w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 ring-1 ring-emerald-500/20 shrink-0">
              <Sparkles className="h-4 w-4 md:h-5 md:w-5 text-emerald-400" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base md:text-lg font-semibold text-foreground">AI Assistant</h1>
              <p className="text-xs md:text-sm text-muted-foreground truncate">
                Ask about your agents, workflows, connectors, and knowledge base
              </p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-auto p-4 md:p-6">
          <div className="max-w-3xl mx-auto space-y-5">
            {!user ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="h-20 w-20 rounded-full bg-gradient-to-br from-blue-500/20 to-violet-500/20 flex items-center justify-center mb-6">
                  <Bot className="h-8 w-8 text-blue-400" />
                </div>
                <h2 className="text-lg font-semibold text-foreground mb-2">Sign in required</h2>
                <p className="text-sm text-muted-foreground max-w-md">
                  The AI assistant is available after authentication.
                </p>
              </div>
            ) : messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center py-12 text-center"
              >
                <div className="relative mb-6">
                  <div className="h-20 w-20 rounded-full bg-gradient-to-br from-emerald-500/20 to-teal-500/20 flex items-center justify-center">
                    <Sparkles className="h-8 w-8 text-emerald-400" />
                  </div>
                </div>
                <h2 className="text-lg font-semibold text-foreground mb-2">How can I help?</h2>
                <p className="text-sm text-muted-foreground mb-8 max-w-md">
                  I can search your knowledge base and report on agents and connectors.
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {SAMPLE_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => submit(prompt)}
                      disabled={isBusy}
                      className="flex items-center gap-2 px-3 py-2 rounded-lg border border-border bg-card/50 text-sm text-muted-foreground hover:text-foreground hover:border-foreground/20 transition-colors disabled:opacity-50"
                    >
                      <Sparkles className="h-3 w-3" />
                      {prompt}
                    </button>
                  ))}
                </div>
              </motion.div>
            ) : (
              messages.map((message) => {
                const parts = (message.parts ?? []) as MessagePart[]
                const isUser = message.role === "user"
                return (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
                  >
                    {!isUser && (
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 ring-1 ring-emerald-500/20">
                        <Bot className="h-4 w-4 text-emerald-400" />
                      </div>
                    )}
                    <div className={cn("max-w-[80%] space-y-2", isUser && "items-end")}>
                      {/* Tool activity chips */}
                      <div className="flex flex-wrap gap-1.5">
                        {parts
                          .filter((p) => p.type.startsWith("tool-"))
                          .map((p, i) => (
                            <ToolChip key={`${message.id}-tool-${i}`} part={p} />
                          ))}
                      </div>
                      {/* Text */}
                      {parts
                        .filter((p) => p.type === "text" && p.text)
                        .map((p, i) => (
                          <div
                            key={`${message.id}-text-${i}`}
                            className={cn(
                              "rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap leading-relaxed",
                              isUser
                                ? "bg-emerald-500 text-white"
                                : "bg-card border border-border text-foreground",
                            )}
                          >
                            {p.text}
                          </div>
                        ))}
                    </div>
                    {isUser && (
                      <div className="mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                        <User className="h-4 w-4 text-muted-foreground" />
                      </div>
                    )}
                  </motion.div>
                )
              })
            )}

            {/* Streaming indicator */}
            {isBusy && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                {status === "submitted" ? "Thinking..." : "Responding..."}
              </div>
            )}

            {/* Error state */}
            {error && (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3">
                <span className="text-sm text-red-400">
                  Something went wrong generating a response.
                </span>
                <Button variant="outline" size="sm" className="gap-2" onClick={() => regenerate()}>
                  <RotateCcw className="h-3.5 w-3.5" />
                  Retry
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-border p-4 bg-card/50">
          <form onSubmit={onSubmit} className="max-w-3xl mx-auto">
            <div className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 transition-all hover:border-foreground/20 focus-within:border-emerald-500/50 focus-within:ring-2 focus-within:ring-emerald-500/20">
              <input
                type="text"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder={user ? "Ask the assistant..." : "Sign in to chat"}
                disabled={!user || isBusy}
                className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground/50 focus:outline-none text-sm"
              />
              {isBusy ? (
                <Button type="button" size="sm" variant="outline" className="gap-2" onClick={() => stop()}>
                  <Square className="h-3.5 w-3.5" />
                  Stop
                </Button>
              ) : (
                <Button type="submit" size="sm" disabled={!user || !input.trim()} className="gap-2">
                  <Send className="h-4 w-4" />
                </Button>
              )}
            </div>
          </form>
        </div>
      </div>
    </AppShell>
  )
}
