"use client"

import { useState, useEffect, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
  Sparkles, 
  Send, 
  User, 
  Bot,
  Loader2,
  Lightbulb,
  ArrowRight
} from "lucide-react"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  isTyping?: boolean
  actions?: { label: string; type: string }[]
}

const SUGGESTED_PROMPTS = [
  "Show me failed workflows from today",
  "What leads haven't been contacted?",
  "Create a report of sync errors",
]

const DEMO_RESPONSES: Record<string, { response: string; actions?: { label: string; type: string }[] }> = {
  "Show me failed workflows from today": {
    response: "I found 3 failed workflows today:\n\n1. **Lead Sync** - Failed at 2:34 PM (Salesforce timeout)\n2. **Email Campaign** - Failed at 11:15 AM (Rate limit)\n3. **Data Backup** - Failed at 8:00 AM (Auth expired)\n\nWould you like me to retry any of these or show more details?",
    actions: [
      { label: "Retry All", type: "action" },
      { label: "View Details", type: "navigate" },
    ],
  },
  "What leads haven't been contacted?": {
    response:
      "In your workspace I’d pull uncontacted leads from connected CRM tools, prioritize by your signals, and offer a follow-up workflow or export.\n\n**This demo does not invent lead counts** — live totals come from your connectors.",
    actions: [
      { label: "Create Workflow", type: "action" },
      { label: "Export List", type: "action" },
    ],
  },
  "Create a report of sync errors": {
    response:
      "In your workspace I’d summarize sync attempts from connector audit events — successes, failures, and top error types — with operational counts from your org.\n\n**This demo does not invent a success percentage.** Open Connectors or Runs for live telemetry.",
    actions: [
      { label: "Download Report", type: "action" },
      { label: "Fix Issues", type: "action" },
    ],
  },
}

export function OperatorDemo() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messageIdRef = useRef(0)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const nextMessageId = (prefix: string) => {
    messageIdRef.current += 1
    return `${prefix}-${messageIdRef.current}`
  }

  const simulateTyping = (text: string, actions?: { label: string; type: string }[]) => {
    setIsTyping(true)
    
    // Add typing indicator
    const typingId = nextMessageId("typing")
    setMessages((prev) => [
      ...prev,
      { id: typingId, role: "assistant", content: "", isTyping: true },
    ])

    // Simulate AI response
    setTimeout(() => {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId
            ? { ...m, content: text, isTyping: false, actions }
            : m
        )
      )
      setIsTyping(false)
    }, 1500)
  }

  const handleSend = (prompt?: string) => {
    const text = prompt || input
    if (!text.trim()) return

    const userMessage: Message = {
      id: nextMessageId("user"),
      role: "user",
      content: text,
    }
    setMessages((prev) => [...prev, userMessage])
    setInput("")

    const demoResponse = DEMO_RESPONSES[text] || {
      response: `I understand you want to "${text}". Let me analyze your data and workflows to help with that.\n\nBased on your current configuration, I can:\n- Query your connected integrations\n- Analyze workflow execution history\n- Generate insights and recommendations\n\nWhat would you like me to focus on?`,
      actions: [
        { label: "Show Insights", type: "action" },
        { label: "Run Analysis", type: "action" },
      ],
    }

    simulateTyping(demoResponse.response, demoResponse.actions)
  }

  const handleActionClick = (action: { label: string; type: string }) => {
    const actionMessage: Message = {
      id: nextMessageId("action"),
      role: "user",
      content: `[Action: ${action.label}]`,
    }
    setMessages((prev) => [...prev, actionMessage])
    
    simulateTyping(
      `Executing "${action.label}"...\n\nDone! The action has been completed successfully. Is there anything else you'd like me to help with?`
    )
  }

  const handleReset = () => {
    setMessages([])
    setInput("")
  }

  return (
    <div className="relative rounded-xl border border-border bg-background overflow-hidden flex flex-col h-[400px]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30 shrink-0">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <span className="font-medium text-sm text-foreground">Gravitre AI</span>
            <span className="text-xs text-primary ml-2">Online</span>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleReset}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            Clear chat
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Lightbulb className="h-8 w-8 text-amber-500 mb-3" />
            <h3 className="font-medium text-foreground mb-1">Ask me anything</h3>
            <p className="text-sm text-muted-foreground mb-4">
              I can help with workflows, data, and insights
            </p>
            <div className="space-y-2 w-full max-w-xs">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => handleSend(prompt)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-lg border border-border text-sm text-muted-foreground hover:border-primary/50 hover:bg-primary/10/30 hover:text-foreground transition-all group"
                >
                  <span className="truncate">{prompt}</span>
                  <ArrowRight className="h-3.5 w-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex gap-3 ${message.role === "user" ? "justify-end" : ""}`}
              >
                {message.role === "assistant" && (
                  <div className="h-7 w-7 rounded-full bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center shrink-0">
                    <Bot className="h-3.5 w-3.5 text-white" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-lg px-3 py-2 ${
                    message.role === "user"
                      ? "bg-primary text-white"
                      : "bg-muted"
                  }`}
                >
                  {message.isTyping ? (
                    <div className="flex items-center gap-1 py-1">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">Thinking...</span>
                    </div>
                  ) : (
                    <>
                      <div className="text-sm whitespace-pre-wrap">{message.content}</div>
                      {message.actions && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          {message.actions.map((action) => (
                            <button
                              key={action.label}
                              onClick={() => handleActionClick(action)}
                              className="px-2.5 py-1 rounded-md bg-background border border-border text-xs font-medium hover:bg-muted transition-colors"
                            >
                              {action.label}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
                {message.role === "user" && (
                  <div className="h-7 w-7 rounded-full bg-muted flex items-center justify-center shrink-0">
                    <User className="h-3.5 w-3.5 text-muted-foreground" />
                  </div>
                )}
              </motion.div>
            ))}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input */}
      <div className="p-3 border-t border-border bg-muted/20 shrink-0">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder="Ask Gravitre AI..."
            disabled={isTyping}
            className="flex-1 px-3 py-2 rounded-lg border border-border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary disabled:opacity-50"
          />
          <button
            onClick={() => handleSend()}
            disabled={!input.trim() || isTyping}
            className="p-2 rounded-lg bg-primary text-white hover:bg-primary/100 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
