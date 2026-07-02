"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { toast } from "sonner"
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  CheckCircle2,
  Plug,
  Sparkles,
  Store,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { onboardingApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import {
  markWelcomeCompletedLocal,
  WELCOME_CONNECTORS,
  WELCOME_ROLES,
  type WelcomeRoleId,
} from "@/lib/welcome-flow"
import { cn } from "@/lib/utils"

const STEPS = [
  { id: "role", title: "Your role" },
  { id: "connect", title: "Connect tools" },
  { id: "pack", title: "Install a pack" },
  { id: "chat", title: "First conversation" },
  { id: "done", title: "All set" },
] as const

export default function WelcomePage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [stepIndex, setStepIndex] = useState(0)
  const [role, setRole] = useState<WelcomeRoleId | null>(null)
  const [skippedConnect, setSkippedConnect] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const selectedRole = useMemo(
    () => WELCOME_ROLES.find((entry) => entry.id === role) ?? null,
    [role],
  )

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (!user) {
    router.replace("/login?intent=login")
    return null
  }

  async function finishWelcome(skippedOptional: boolean) {
    if (!role) return
    setSubmitting(true)
    try {
      await onboardingApi.welcomeComplete(role, skippedOptional)
      markWelcomeCompletedLocal()
      toast.success("Welcome aboard — your workspace is ready.")
      router.replace(APP_ROUTES.home)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save welcome progress")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-background via-background to-emerald-500/5 px-4 py-10">
      <div className="mb-8 flex w-full max-w-2xl items-center gap-2">
        {STEPS.map((step, index) => (
          <div key={step.id} className="flex flex-1 flex-col gap-1">
            <div
              className={cn(
                "h-1 rounded-full transition-colors",
                index <= stepIndex ? "bg-emerald-500" : "bg-muted",
              )}
            />
            <span className="hidden text-[10px] text-muted-foreground sm:block">{step.title}</span>
          </div>
        ))}
      </div>

      <motion.div
        layout
        className="w-full max-w-2xl rounded-2xl border border-border/70 bg-card/80 p-6 shadow-xl backdrop-blur sm:p-8"
      >
        <AnimatePresence mode="wait">
          {stepIndex === 0 && (
            <StepShell
              key="role"
              icon={Sparkles}
              title="What brings you to Gravitre?"
              description="We'll tailor your home dashboard, marketplace recommendations, and first suggested prompt."
            >
              <div className="grid gap-2 sm:grid-cols-2">
                {WELCOME_ROLES.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setRole(entry.id)}
                    className={cn(
                      "rounded-xl border p-3 text-left transition-colors",
                      role === entry.id
                        ? "border-emerald-500/40 bg-emerald-500/10"
                        : "border-border hover:bg-muted/40",
                    )}
                  >
                    <p className="text-sm font-medium text-foreground">{entry.label}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{entry.description}</p>
                  </button>
                ))}
              </div>
            </StepShell>
          )}

          {stepIndex === 1 && (
            <StepShell
              key="connect"
              icon={Plug}
              title="Connect your stack"
              description="Gravitre reads and acts in the tools you already use. Start with one — you can add more anytime."
            >
              <div className="grid gap-2 sm:grid-cols-2">
                {WELCOME_CONNECTORS.map((connector) => (
                  <Link
                    key={connector.type}
                    href={connector.href}
                    className="rounded-lg border border-border bg-background/60 px-3 py-2.5 text-sm font-medium hover:bg-muted/40"
                  >
                    {connector.label}
                  </Link>
                ))}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="mt-3 text-muted-foreground"
                onClick={() => {
                  setSkippedConnect(true)
                  setStepIndex(2)
                }}
              >
                Skip for now
              </Button>
            </StepShell>
          )}

          {stepIndex === 2 && (
            <StepShell
              key="pack"
              icon={Store}
              title="Install a department pack"
              description="Pre-built agents, workflows, and knowledge — configured for your team in minutes."
            >
              {selectedRole?.packSlug ? (
                <Link
                  href={`/marketplace/assets/${encodeURIComponent(selectedRole.packSlug)}`}
                  className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-700 dark:text-emerald-300"
                >
                  Preview recommended pack
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : null}
              <Link
                href={APP_ROUTES.marketplace}
                className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
              >
                Browse all marketplace templates
              </Link>
            </StepShell>
          )}

          {stepIndex === 3 && (
            <StepShell
              key="chat"
              icon={Bot}
              title="Start your first AI conversation"
              description="Gravitre routes your request to the right engine — execute tracked work, chat, or search records."
            >
              <div className="rounded-xl border border-dashed border-border bg-muted/20 p-4 text-sm text-muted-foreground">
                Suggested prompt:{" "}
                <span className="font-medium text-foreground">
                  {selectedRole?.suggestedPrompt ?? "What should Gravitre help me with first?"}
                </span>
              </div>
              <Link
                href={`${APP_ROUTES.gravitreAi}?prompt=${encodeURIComponent(selectedRole?.suggestedPrompt ?? "")}`}
                className="mt-4 inline-flex"
              >
                <Button>Open Gravitre AI</Button>
              </Link>
            </StepShell>
          )}

          {stepIndex === 4 && (
            <StepShell
              key="done"
              icon={CheckCircle2}
              title="You're ready to go"
              description="Over the next 7 days Gravitre will learn from your connectors, conversations, and workflow runs to improve recommendations."
            >
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>• Connect more tools to unlock department agents and ML models</li>
                <li>• Visit Intelligence Center to see confidence and outcomes</li>
                <li>• Resume setup anytime from Getting Started in the sidebar</li>
              </ul>
            </StepShell>
          )}
        </AnimatePresence>

        <div className="mt-8 flex items-center justify-between gap-3 border-t border-border pt-6">
          <Button
            variant="ghost"
            size="sm"
            disabled={stepIndex === 0 || submitting}
            onClick={() => setStepIndex((value) => Math.max(0, value - 1))}
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back
          </Button>

          <div className="flex gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={submitting}
              onClick={() => void finishWelcome(true)}
            >
              Skip setup
            </Button>
            {stepIndex < STEPS.length - 1 ? (
              <Button
                size="sm"
                disabled={(stepIndex === 0 && !role) || submitting}
                onClick={() => setStepIndex((value) => Math.min(STEPS.length - 1, value + 1))}
              >
                Continue
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            ) : (
              <Button size="sm" disabled={!role || submitting} onClick={() => void finishWelcome(skippedConnect)}>
                Go to home
              </Button>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  )
}

function StepShell({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className="space-y-4"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10">
          <Icon className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </motion.div>
  )
}
