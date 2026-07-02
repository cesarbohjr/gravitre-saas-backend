"use client"

import { useMemo, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { AppShell } from "@/components/gravitre/app-shell"
import { cn } from "@/lib/utils"
import { useAuth } from "@/lib/auth-context"
import { ensureSelectedOrg } from "@/lib/org-context"
import {
  AI_ENGINE_ROUTES,
  setAiHandoff,
  type AiEngine,
} from "@/lib/ai-surface-handoff"
import { LiveActivityRail } from "./_components/live-activity-rail"
import {
  ArrowUp,
  Sparkle as Sparkles,
  RocketLaunch,
  ChatCircle,
  MagnifyingGlass,
  Lightning,
  type Icon as PhosphorIcon,
} from "@phosphor-icons/react"
import { toast } from "sonner"

type ModeId = "auto" | AiEngine

type ModeMeta = {
  id: ModeId
  label: string
  badge: string
  icon: PhosphorIcon
  blurb: string
  accent: string
  ring: string
}

const MODES: ModeMeta[] = [
  {
    id: "auto",
    label: "Auto",
    badge: "Routes intent",
    icon: Sparkles,
    blurb: "Describe what you need — Gravitre picks the right engine.",
    accent: "text-foreground",
    ring: "border-foreground/30 bg-foreground/5 ring-foreground/15",
  },
  {
    id: "execute",
    label: "Execute",
    badge: "Command Center",
    icon: RocketLaunch,
    blurb: "Delegate tracked work — tasks, execution plans, async jobs.",
    accent: "text-emerald-500",
    ring: "border-emerald-500/40 bg-emerald-500/5 ring-emerald-500/20",
  },
  {
    id: "chat",
    label: "Chat",
    badge: "Workspace Chat",
    icon: ChatCircle,
    blurb: "Ask questions, brainstorm, and get platform help in a thread.",
    accent: "text-blue-500",
    ring: "border-blue-500/40 bg-blue-500/5 ring-blue-500/20",
  },
  {
    id: "find",
    label: "Find",
    badge: "Universal Search",
    icon: MagnifyingGlass,
    blurb: "Locate a workflow, run, agent, connector, or document.",
    accent: "text-amber-500",
    ring: "border-amber-500/40 bg-amber-500/5 ring-amber-500/20",
  },
]

const EXAMPLE_PROMPTS: Array<{ text: string; hint: AiEngine }> = [
  { text: "Investigate why the nightly Salesforce sync failed and fix it", hint: "execute" },
  { text: "What changed in our workflow success rate this week?", hint: "chat" },
  { text: "Find failed runs from the last 24 hours", hint: "find" },
  { text: "Draft an onboarding workflow for new support agents", hint: "execute" },
]

function ModeIconBadge({ mode, className }: { mode: ModeMeta; className?: string }) {
  const Icon = mode.icon
  return <Icon className={cn("h-4 w-4", mode.accent, className)} weight="duotone" aria-hidden />
}

export default function GravitreAiPage() {
  const router = useRouter()
  const { user } = useAuth()
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const [mode, setMode] = useState<ModeId>("auto")
  const [input, setInput] = useState("")
  const [routing, setRouting] = useState(false)
  const [routedTo, setRoutedTo] = useState<AiEngine | null>(null)

  const activeMode = useMemo(() => MODES.find((m) => m.id === mode) ?? MODES[0], [mode])

  const handoffTo = (engine: AiEngine, prompt: string, source: "model" | "heuristic" | "manual") => {
    setAiHandoff(engine, { prompt, autoRun: true, source })
    router.push(AI_ENGINE_ROUTES[engine])
  }

  async function classifyIntent(prompt: string): Promise<{ engine: AiEngine; source: "model" | "heuristic" }> {
    const res = await fetch("/api/ai/route-intent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ prompt }),
    })
    if (!res.ok) throw new Error(`route-intent ${res.status}`)
    const data = (await res.json()) as { mode: AiEngine; source: "model" | "heuristic" }
    return { engine: data.mode, source: data.source }
  }

  const submit = async () => {
    const prompt = input.trim()
    if (!prompt || routing) return
    if (!user) {
      toast.error("Sign in to use Gravitre AI")
      return
    }
    void ensureSelectedOrg()

    // Manual mode → route directly to the chosen engine.
    if (mode !== "auto") {
      handoffTo(mode, prompt, "manual")
      return
    }

    // Auto mode → classify intent, then hand off.
    setRouting(true)
    try {
      const { engine, source } = await classifyIntent(prompt)
      setRoutedTo(engine)
      // Brief pause so the user sees where they're being routed.
      await new Promise((r) => setTimeout(r, 550))
      handoffTo(engine, prompt, source)
    } catch (err) {
      console.log("[v0] intent routing failed:", err)
      // Fall back to Workspace Chat — the most forgiving destination.
      handoffTo("chat", prompt, "heuristic")
    } finally {
      setRouting(false)
    }
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey) return
    // Respect IME composition (CJK) and Safari's unreliable final event.
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    void submit()
  }

  const routedMode = routedTo ? MODES.find((m) => m.id === routedTo) : null

  return (
    <AppShell title="Gravitre AI">
      <div className="flex h-full">
        <div className="relative flex-1 overflow-y-auto">
          {/* Ambient background */}
          <div className="pointer-events-none absolute inset-0 z-0">
            <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-secondary/20" />
            <div className="absolute -top-32 left-1/2 h-[420px] w-[560px] -translate-x-1/2 rounded-full bg-primary/[0.04] blur-3xl" />
          </div>

          <div className="relative z-10 mx-auto flex min-h-full w-full max-w-3xl flex-col px-4 py-10 md:px-6 md:py-16">
            {/* Hero */}
            <div className="text-center">
              <div className="mx-auto mb-4 inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs font-medium text-muted-foreground">
                <Lightning className="h-3.5 w-3.5 text-emerald-500" weight="fill" aria-hidden />
                One surface, three modes
              </div>
              <h1 className="text-balance text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
                What do you want to get done?
              </h1>
              <p className="mx-auto mt-3 max-w-xl text-pretty text-sm leading-relaxed text-muted-foreground md:text-base">
                Ask a question, delegate a task, or search your workspace. In Auto mode, Gravitre routes
                your intent to the right engine automatically.
              </p>
            </div>

            {/* Mode chips */}
            <div className="mt-8 flex flex-wrap justify-center gap-2">
              {MODES.map((m) => {
                const isActive = m.id === mode
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setMode(m.id)}
                    aria-pressed={isActive}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-sm font-medium transition-all",
                      isActive
                        ? cn("ring-1", m.ring, "text-foreground")
                        : "border-border bg-card/50 text-muted-foreground hover:border-foreground/20 hover:text-foreground",
                    )}
                  >
                    <ModeIconBadge mode={m} />
                    {m.label}
                    <span className="hidden rounded bg-muted/80 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground sm:inline">
                      {m.badge}
                    </span>
                  </button>
                )
              })}
            </div>

            {/* Smart input */}
            <div className="mt-4">
              <div
                className={cn(
                  "rounded-2xl border bg-card p-2 shadow-sm transition-all focus-within:ring-2",
                  activeMode.id === "auto" && "focus-within:border-foreground/30 focus-within:ring-foreground/15",
                  activeMode.id === "execute" && "focus-within:border-emerald-500/50 focus-within:ring-emerald-500/20",
                  activeMode.id === "chat" && "focus-within:border-blue-500/50 focus-within:ring-blue-500/20",
                  activeMode.id === "find" && "focus-within:border-amber-500/50 focus-within:ring-amber-500/20",
                  "border-border",
                )}
              >
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={onKeyDown}
                  rows={3}
                  disabled={routing}
                  placeholder={
                    activeMode.id === "find"
                      ? "Find a run, workflow, agent, connector, or document…"
                      : activeMode.id === "execute"
                        ? "Describe the work to delegate — Gravitre will plan and run it…"
                        : activeMode.id === "chat"
                          ? "Ask a question or start a conversation…"
                          : "Describe what you need — Gravitre will route it to the right engine…"
                  }
                  className="w-full resize-none bg-transparent px-3 py-2 text-sm text-foreground outline-none placeholder:text-muted-foreground/70 disabled:opacity-60"
                />
                <div className="flex items-center justify-between gap-3 px-2 pb-1">
                  <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <ModeIconBadge mode={activeMode} className="h-3.5 w-3.5" />
                    <span className="truncate">{activeMode.blurb}</span>
                  </p>
                  <button
                    type="button"
                    onClick={() => void submit()}
                    disabled={!input.trim() || routing}
                    className={cn(
                      "inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-primary-foreground transition-colors disabled:cursor-not-allowed disabled:opacity-40",
                      "bg-primary hover:bg-primary/90",
                    )}
                    aria-label="Submit"
                  >
                    {routing ? (
                      <Sparkles className="h-4 w-4 animate-pulse" weight="fill" aria-hidden />
                    ) : (
                      <ArrowUp className="h-4 w-4" weight="bold" aria-hidden />
                    )}
                  </button>
                </div>
              </div>

              {/* Routing indicator */}
              <AnimatePresence>
                {routing ? (
                  <motion.div
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    className="mt-3 flex items-center justify-center gap-2 text-sm text-muted-foreground"
                  >
                    <Sparkles className="h-4 w-4 animate-pulse text-emerald-500" weight="fill" aria-hidden />
                    {routedMode ? (
                      <span>
                        Routing to <span className={cn("font-medium", routedMode.accent)}>{routedMode.badge}</span>…
                      </span>
                    ) : (
                      <span>Reading your intent…</span>
                    )}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            </div>

            {/* Example prompts */}
            {!routing ? (
              <div className="mt-6">
                <p className="mb-2 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Try
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {EXAMPLE_PROMPTS.map((example) => {
                    const hintMode = MODES.find((m) => m.id === example.hint)
                    return (
                      <button
                        key={example.text}
                        type="button"
                        onClick={() => {
                          setInput(example.text)
                          inputRef.current?.focus()
                        }}
                        className="group inline-flex items-center gap-2 rounded-lg border border-border bg-card/50 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
                      >
                        {hintMode ? <ModeIconBadge mode={hintMode} className="h-3.5 w-3.5" /> : null}
                        <span className="max-w-[15rem] truncate">{example.text}</span>
                      </button>
                    )
                  })}
                </div>
              </div>
            ) : null}

            {/* Three-mode explainer */}
            <div className="mt-auto pt-10">
              <div className="grid gap-3 md:grid-cols-3">
                {MODES.filter((m) => m.id !== "auto").map((m) => (
                  <div key={m.id} className="rounded-xl border border-border bg-card/40 p-3.5">
                    <div className="flex items-center gap-2">
                      <ModeIconBadge mode={m} />
                      <span className="text-sm font-medium text-foreground">{m.badge}</span>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground text-pretty">{m.blurb}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <LiveActivityRail />
      </div>
    </AppShell>
  )
}
