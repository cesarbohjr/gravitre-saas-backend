"use client"

import { useState } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { useAuth } from "@/lib/auth-context"
import { ensureSelectedOrg } from "@/lib/org-context"
import type { AiEngine } from "@/lib/ai-surface-handoff"
import { toast } from "sonner"
import { AiLanding } from "./_components/ai-landing"
import { AiWorkspace } from "./_components/ai-workspace"
import { LiveActivityRail } from "./_components/live-activity-rail"
import type { ModeId } from "./_components/ai-mode-config"

type ActiveSession = {
  mode: ModeId
  prompt: string
}

export default function GravitreAiPage() {
  const { user } = useAuth()
  const [mode, setMode] = useState<ModeId>("auto")
  const [input, setInput] = useState("")
  const [routing, setRouting] = useState(false)
  const [routedTo, setRoutedTo] = useState<AiEngine | null>(null)
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null)

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

  const beginSession = async () => {
    const prompt = input.trim()
    if (!prompt || routing) return
    if (!user) {
      toast.error("Sign in to use Gravitre AI")
      return
    }
    void ensureSelectedOrg()

    if (mode !== "auto") {
      setActiveSession({ mode, prompt })
      setInput("")
      return
    }

    setRouting(true)
    try {
      const { engine } = await classifyIntent(prompt)
      setRoutedTo(engine)
      await new Promise((resolve) => window.setTimeout(resolve, 450))
      setActiveSession({ mode: engine, prompt })
      setInput("")
    } catch {
      setActiveSession({ mode: "chat", prompt })
      setInput("")
    } finally {
      setRouting(false)
      setRoutedTo(null)
    }
  }

  return (
    <AppShell title="Gravitre AI">
      <div className="flex h-full">
        <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
          {!activeSession ? (
            <div className="relative flex-1 overflow-y-auto">
              <div className="pointer-events-none absolute inset-0 z-0">
                <div className="absolute inset-0 bg-gradient-to-b from-background via-background to-secondary/20" />
                <div className="absolute -top-32 left-1/2 h-[420px] w-[560px] -translate-x-1/2 rounded-full bg-primary/[0.04] blur-3xl" />
              </div>
              <AiLanding
                mode={mode}
                onModeChange={setMode}
                input={input}
                onInputChange={setInput}
                routing={routing}
                routedTo={routedTo}
                onSubmit={() => void beginSession()}
              />
            </div>
          ) : (
            <AiWorkspace
              initialMode={activeSession.mode}
              initialPrompt={activeSession.prompt}
              onNewSession={() => {
                setActiveSession(null)
                setInput("")
              }}
            />
          )}
        </div>
        <LiveActivityRail />
      </div>
    </AppShell>
  )
}
