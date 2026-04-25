"use client"

import { useState, useEffect, useRef, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  AlertCircle,
  TrendingUp,
  Zap,
  Bug,
  Gauge,
  RefreshCw,
  Command,
  ArrowRight,
  Sparkles,
  Loader2,
  ChevronRight,
  History,
  Lightbulb,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { UserAvatar } from "./chat-avatars"

interface SlashCommand {
  command: string
  label: string
  description: string
  icon: React.ElementType
  color: string
}

interface SuggestedAction {
  label: string
  icon: React.ElementType
  prompt: string
}

interface AICommandInputProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  isProcessing?: boolean
  disabled?: boolean
  contextLabel?: string
}

const slashCommands: SlashCommand[] = [
  { command: "/analyze", label: "Analyze", description: "Deep analysis of systems and data", icon: Search, color: "text-blue-400" },
  { command: "/debug", label: "Debug", description: "Find and diagnose issues", icon: Bug, color: "text-red-400" },
  { command: "/optimize", label: "Optimize", description: "Improve performance and efficiency", icon: Gauge, color: "text-emerald-400" },
  { command: "/investigate", label: "Investigate", description: "Root cause analysis", icon: AlertCircle, color: "text-amber-400" },
  { command: "/compare", label: "Compare", description: "Compare metrics and patterns", icon: TrendingUp, color: "text-purple-400" },
  { command: "/automate", label: "Automate", description: "Create automation workflows", icon: Zap, color: "text-cyan-400" },
]

const suggestedActions: SuggestedAction[] = [
  { label: "Why did the last sync fail?", icon: AlertCircle, prompt: "Investigate why the last sync failed and suggest fixes" },
  { label: "Analyze latency trends", icon: TrendingUp, prompt: "/analyze latency patterns over the past 24 hours" },
  { label: "Debug pipeline errors", icon: Bug, prompt: "/debug Find errors in the data pipeline" },
  { label: "Optimize query performance", icon: Gauge, prompt: "/optimize Suggest query performance improvements" },
]

const rotatingPlaceholders = [
  "Investigate pipeline failure...",
  "Analyze system performance...",
  "Find root cause of sync issue...",
  "Debug why the automation failed...",
  "Optimize query response times...",
  "Compare metrics from last week...",
]

export function AICommandInput({
  value,
  onChange,
  onSubmit,
  isProcessing = false,
  disabled = false,
  contextLabel,
}: AICommandInputProps) {
  const [isFocused, setIsFocused] = useState(false)
  const [showCommands, setShowCommands] = useState(false)
  const [filteredCommands, setFilteredCommands] = useState<SlashCommand[]>([])
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0)
  const [placeholderIndex, setPlaceholderIndex] = useState(0)
  const [recentPrompts] = useState<string[]>([
    "Investigate sync-customers-1234 failure",
    "Analyze API response times",
  ])
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const commandsRef = useRef<HTMLDivElement>(null)

  // Rotate placeholders
  useEffect(() => {
    const interval = setInterval(() => {
      setPlaceholderIndex((prev) => (prev + 1) % rotatingPlaceholders.length)
    }, 3000)
    return () => clearInterval(interval)
  }, [])

  // Handle slash command detection
  useEffect(() => {
    if (value.startsWith("/")) {
      const query = value.slice(1).toLowerCase()
      const filtered = slashCommands.filter(
        (cmd) =>
          cmd.command.slice(1).toLowerCase().includes(query) ||
          cmd.label.toLowerCase().includes(query)
      )
      setFilteredCommands(filtered)
      setShowCommands(filtered.length > 0)
      setSelectedCommandIndex(0)
    } else {
      setShowCommands(false)
    }
  }, [value])

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (showCommands) {
        if (e.key === "ArrowDown") {
          e.preventDefault()
          setSelectedCommandIndex((prev) =>
            prev < filteredCommands.length - 1 ? prev + 1 : 0
          )
        } else if (e.key === "ArrowUp") {
          e.preventDefault()
          setSelectedCommandIndex((prev) =>
            prev > 0 ? prev - 1 : filteredCommands.length - 1
          )
        } else if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault()
          const selected = filteredCommands[selectedCommandIndex]
          if (selected) {
            onChange(selected.command + " ")
            setShowCommands(false)
          }
        } else if (e.key === "Escape") {
          setShowCommands(false)
        }
      } else if (e.key === "Enter" && !e.shiftKey && value.trim()) {
        e.preventDefault()
        onSubmit()
      }
    },
    [showCommands, filteredCommands, selectedCommandIndex, onChange, onSubmit, value]
  )

  // Global keyboard shortcut
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener("keydown", handleGlobalKeyDown)
    return () => window.removeEventListener("keydown", handleGlobalKeyDown)
  }, [])

  const handleCommandSelect = (command: SlashCommand) => {
    onChange(command.command + " ")
    setShowCommands(false)
    inputRef.current?.focus()
  }

  const handleSuggestedAction = (action: SuggestedAction) => {
    onChange(action.prompt)
    inputRef.current?.focus()
  }

  return (
    <div className="space-y-4">
      {/* Main Input Container - Notion AI / Raycast inspired */}
      <div
        className={`
          relative rounded-2xl border transition-all duration-300 overflow-hidden
          ${isFocused
            ? "border-blue-500/40 bg-gradient-to-b from-card to-card/80 shadow-[0_0_0_1px_rgba(59,130,246,0.1),0_8px_40px_-12px_rgba(59,130,246,0.2)]"
            : "border-border/60 bg-card hover:border-border hover:shadow-md"
          }
          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        `}
      >
        {/* Subtle gradient overlay when focused */}
        {isFocused && (
          <>
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/[0.03] via-transparent to-violet-500/[0.03] pointer-events-none" />
            {/* Animated border glow */}
            <div className="absolute inset-0 rounded-2xl pointer-events-none overflow-hidden">
              <div className="absolute inset-[-2px] bg-gradient-to-r from-blue-500/0 via-blue-500/30 to-blue-500/0 animate-shimmer" />
            </div>
          </>
        )}

        {/* Keyboard Shortcut Hint */}
        <div className="absolute right-4 top-4 flex items-center gap-1.5">
          <kbd className="flex items-center gap-1 rounded-md bg-secondary/80 backdrop-blur-sm px-2 py-1 font-mono text-[10px] text-muted-foreground border border-border/50 shadow-sm">
            <Command className="h-3 w-3" />
            <span>K</span>
          </kbd>
        </div>

        {/* Input Area */}
        <div className="p-5 pb-4">
          <div className="flex items-start gap-4">
            {/* User Avatar */}
            <div className="mt-1 shrink-0">
              <UserAvatar name="Sarah Chen" size="md" className="shadow-sm" />
            </div>
            {/* AI Icon with glow effect */}
            <motion.div 
              className={`
                relative mt-1 rounded-xl p-2.5 transition-all duration-300 shrink-0
                ${isFocused 
                  ? "bg-gradient-to-br from-blue-500/20 to-blue-600/10" 
                  : "bg-secondary/80"
                }
              `}
              animate={isFocused ? {
                boxShadow: [
                  "0 0 20px rgba(59,130,246,0.1)",
                  "0 0 30px rgba(59,130,246,0.2)",
                  "0 0 20px rgba(59,130,246,0.1)",
                ],
              } : {}}
              transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
            >
              <motion.div
                animate={isFocused ? { rotate: [0, 5, -5, 0] } : {}}
                transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              >
                <Sparkles className={`h-5 w-5 transition-colors duration-300 ${isFocused ? "text-blue-400" : "text-muted-foreground"}`} />
              </motion.div>
              {isFocused && (
                <>
                  <motion.div 
                    className="absolute inset-0 rounded-xl bg-blue-500/20"
                    animate={{ opacity: [0.3, 0.6, 0.3] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                  <motion.div 
                    className="absolute -inset-1 rounded-xl border border-blue-500/30"
                    animate={{ opacity: [0, 0.5, 0], scale: [0.95, 1.05, 0.95] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  />
                </>
              )}
            </motion.div>
            <div className="flex-1 min-w-0 pt-1">
              {/* Animated Placeholder */}
              <div className="relative">
                <textarea
                  ref={inputRef}
                  value={value}
                  onChange={(e) => onChange(e.target.value)}
                  onFocus={() => setIsFocused(true)}
                  onBlur={() => setTimeout(() => setIsFocused(false), 150)}
                  onKeyDown={handleKeyDown}
                  disabled={disabled || isProcessing}
                  rows={3}
                  className="w-full resize-none bg-transparent text-[15px] leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none disabled:cursor-not-allowed"
                  placeholder={rotatingPlaceholders[placeholderIndex]}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Slash Commands Dropdown - Raycast style */}
        <AnimatePresence>
          {showCommands && (
            <motion.div
              ref={commandsRef}
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              className="absolute left-5 right-5 top-full mt-2 z-50 rounded-xl border border-border/60 bg-popover/95 backdrop-blur-xl p-2 shadow-2xl"
            >
              <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                Commands
              </div>
              <div className="space-y-0.5">
                {filteredCommands.map((cmd, index) => (
                  <motion.button
                    key={cmd.command}
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.03 }}
                    onClick={() => handleCommandSelect(cmd)}
                    className={`
                      flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all duration-150
                      ${index === selectedCommandIndex 
                        ? "bg-blue-500/10 ring-1 ring-blue-500/20" 
                        : "hover:bg-secondary/80"
                      }
                    `}
                  >
                    <div className={`rounded-lg p-2 ${index === selectedCommandIndex ? "bg-blue-500/20" : "bg-secondary"} transition-colors`}>
                      <cmd.icon className={`h-4 w-4 ${cmd.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{cmd.label}</span>
                        <code className="rounded bg-secondary/80 px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono">{cmd.command}</code>
                      </div>
                      <p className="text-xs text-muted-foreground/80 mt-0.5">{cmd.description}</p>
                    </div>
                    <ChevronRight className={`h-4 w-4 transition-colors ${index === selectedCommandIndex ? "text-blue-400" : "text-muted-foreground/50"}`} />
                  </motion.button>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Context & Actions Bar */}
        <div className="flex items-center justify-between border-t border-border/30 bg-secondary/20 px-5 py-3">
          <div className="flex items-center gap-4">
            {contextLabel && (
              <div className="flex items-center gap-2 text-xs">
                <div className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 ring-1 ring-emerald-500/20">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-emerald-400 font-medium">{contextLabel}</span>
                </div>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70">
              <span>Type</span>
              <kbd className="rounded-md bg-secondary/80 border border-border/50 px-1.5 py-0.5 font-mono text-[10px]">/</kbd>
              <span>for commands</span>
            </div>
          </div>
          <Button
            size="sm"
            className="h-9 gap-2 px-5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 shadow-md shadow-blue-500/20 transition-all hover:shadow-lg hover:shadow-blue-500/30"
            disabled={disabled || !value.trim() || isProcessing}
            onClick={onSubmit}
          >
            {isProcessing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="font-medium">Analyzing...</span>
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                <span className="font-medium">Analyze & Plan</span>
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Suggested Actions - Notion AI style chips */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
          <Lightbulb className="h-3.5 w-3.5" />
          Try asking
        </div>
        <div className="flex flex-wrap gap-2">
          {suggestedActions.map((action, i) => (
            <motion.button
              key={i}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05, ease: "easeOut" }}
              onClick={() => handleSuggestedAction(action)}
              disabled={disabled || isProcessing}
              className="group flex items-center gap-2.5 rounded-xl border border-border/60 bg-card/80 backdrop-blur-sm px-4 py-2.5 text-[13px] text-muted-foreground transition-all duration-200 hover:border-blue-500/40 hover:bg-blue-500/5 hover:text-foreground hover:shadow-md hover:shadow-blue-500/5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <action.icon className="h-4 w-4 text-muted-foreground/70 group-hover:text-blue-400 transition-colors" />
              <span>{action.label}</span>
            </motion.button>
          ))}
        </div>
      </div>

      {/* Recent Prompts */}
      {recentPrompts.length > 0 && !value && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/60">
            <History className="h-3.5 w-3.5" />
            Recent
          </div>
          <div className="flex flex-wrap gap-2">
            {recentPrompts.map((prompt, i) => (
              <motion.button
                key={i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: i * 0.05 }}
                onClick={() => onChange(prompt)}
                disabled={disabled || isProcessing}
                className="group flex items-center gap-2 rounded-lg border border-border/40 bg-secondary/40 px-3 py-2 text-xs text-muted-foreground/80 transition-all hover:border-border/60 hover:bg-secondary/60 hover:text-foreground disabled:opacity-50"
              >
                <RefreshCw className="h-3 w-3 group-hover:rotate-180 transition-transform duration-300" />
                <span className="max-w-[220px] truncate">{prompt}</span>
              </motion.button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
