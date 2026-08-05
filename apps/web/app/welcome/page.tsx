"use client"

import { useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { toast } from "sonner"
import {
  ArrowLeft,
  ArrowRight,
  Bot,
  CheckCircle2,
  ExternalLink,
  Plug,
  Sparkles,
  Store,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/lib/auth-context"
import { authApi, onboardingApi } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import {
  clearWelcomeDraft,
  departmentFromWelcomeRole,
  markWelcomeCompletedLocal,
  readWelcomeDraft,
  WELCOME_CONNECTORS,
  WELCOME_ROLES,
  writeWelcomeDraft,
  type WelcomeRoleId,
} from "@/lib/welcome-flow"
import { cn } from "@/lib/utils"
import { GlowOrb, GridPattern, ParticleField } from "@/components/gravitre/premium-effects"
import { cardVariants, useMotionPrefs } from "@/lib/animations"

const STEPS = [
  { id: "role", title: "Your role" },
  { id: "connect", title: "Connect tools" },
  { id: "pack", title: "Install a pack" },
  { id: "chat", title: "First conversation" },
  { id: "done", title: "All set" },
] as const

const DEFAULT_SKIP_ROLE: WelcomeRoleId = "ops"

export default function WelcomePage() {
  const { user, loading } = useAuth()
  const router = useRouter()
  const [hydrated, setHydrated] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [role, setRole] = useState<WelcomeRoleId | null>(null)
  const [jobTitle, setJobTitle] = useState("")
  const [department, setDepartment] = useState("")
  const [skippedConnect, setSkippedConnect] = useState(false)
  const [selectedConnector, setSelectedConnector] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { reduced } = useMotionPrefs()

  useEffect(() => {
    const draft = readWelcomeDraft()
    if (draft) {
      setStepIndex(draft.stepIndex)
      setRole(draft.role)
      setJobTitle(draft.jobTitle ?? "")
      setDepartment(draft.department ?? "")
      setSkippedConnect(draft.skippedConnect)
      setSelectedConnector(draft.selectedConnector)
    }
    setHydrated(true)
  }, [])

  useEffect(() => {
    if (!hydrated) return
    writeWelcomeDraft({
      stepIndex,
      role,
      skippedConnect,
      selectedConnector,
      jobTitle,
      department,
    })
  }, [hydrated, stepIndex, role, skippedConnect, selectedConnector, jobTitle, department])

  useEffect(() => {
    if (loading || user) return
    router.replace("/login?intent=login")
  }, [loading, user, router])

  const selectedRole = useMemo(
    () => WELCOME_ROLES.find((entry) => entry.id === role) ?? null,
    [role],
  )

  const selectedConnectorMeta = useMemo(
    () => WELCOME_CONNECTORS.find((entry) => entry.type === selectedConnector) ?? null,
    [selectedConnector],
  )

  async function persistProfileIdentity() {
    const title = jobTitle.trim()
    const dept = department.trim() || departmentFromWelcomeRole(role)
    if (!title && !dept) return
    await authApi.updateProfile({
      job_title: title || undefined,
      department: dept || undefined,
    })
  }

  async function skipEntireWelcome() {
    setSubmitting(true)
    try {
      const roleToSave = role ?? DEFAULT_SKIP_ROLE
      await persistProfileIdentity()
      await onboardingApi.welcomeComplete(roleToSave, true)
      clearWelcomeDraft()
      markWelcomeCompletedLocal()
      toast.success("Setup skipped — you can finish anytime from Getting Started.")
      router.replace(APP_ROUTES.home)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not skip setup")
    } finally {
      setSubmitting(false)
    }
  }

  async function finishWelcome(skippedOptional: boolean) {
    const roleToSave = role ?? DEFAULT_SKIP_ROLE
    setSubmitting(true)
    try {
      await persistProfileIdentity()
      await onboardingApi.welcomeComplete(roleToSave, skippedOptional)
      clearWelcomeDraft()
      markWelcomeCompletedLocal()
      toast.success("Welcome aboard — your workspace is ready.")
      router.replace(APP_ROUTES.home)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save welcome progress")
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || !hydrated) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-sm text-muted-foreground">Redirecting to sign in…</p>
      </div>
    )
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-gradient-to-b from-background via-background to-emerald-500/5 px-4 py-10">
      <GridPattern color="emerald" className="opacity-[0.25]" />
      <ParticleField count={28} color="emerald" className="opacity-50" />
      <GlowOrb color="emerald" size={280} className="-left-20 top-10 opacity-30" />
      <GlowOrb color="violet" size={200} className="-right-10 bottom-20 opacity-25" />

      <motion.div
        initial={reduced ? false : { opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 mb-8 flex w-full max-w-2xl items-center gap-2"
      >
        {STEPS.map((step, index) => (
          <div key={step.id} className="flex flex-1 flex-col gap-1">
            <motion.div
              className={cn(
                "h-1 rounded-full",
                index <= stepIndex ? "bg-emerald-500" : "bg-muted",
              )}
              initial={false}
              animate={
                index === stepIndex && !reduced
                  ? { scaleX: [0.85, 1], opacity: [0.7, 1] }
                  : { scaleX: 1, opacity: 1 }
              }
              transition={{ duration: 0.4 }}
            />
            <span className="hidden text-[10px] text-muted-foreground sm:block">{step.title}</span>
          </div>
        ))}
      </motion.div>

      <motion.div
        layout
        variants={cardVariants}
        initial="initial"
        animate="animate"
        className="relative z-10 w-full max-w-2xl rounded-2xl border border-border/70 bg-card/80 p-6 shadow-xl shadow-emerald-500/5 backdrop-blur sm:p-8"
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
                    onClick={() => {
                      setRole(entry.id)
                      if (!department.trim()) setDepartment(entry.label)
                    }}
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
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <label className="space-y-1.5 text-left">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    Job title
                  </span>
                  <input
                    type="text"
                    value={jobTitle}
                    onChange={(event) => setJobTitle(event.target.value)}
                    placeholder="e.g. Operations Manager"
                    className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-emerald-500/50"
                  />
                </label>
                <label className="space-y-1.5 text-left">
                  <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    Department
                  </span>
                  <input
                    type="text"
                    value={department}
                    onChange={(event) => setDepartment(event.target.value)}
                    placeholder="e.g. Operations"
                    className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground outline-none focus:border-emerald-500/50"
                  />
                </label>
              </div>
            </StepShell>
          )}

          {stepIndex === 1 && (
            <StepShell
              key="connect"
              icon={Plug}
              title="Connect your stack"
              description="Gravitre reads and acts in the tools you already use. Pick one to connect — you stay in setup and can add more later."
            >
              <div className="grid gap-2 sm:grid-cols-2">
                {WELCOME_CONNECTORS.map((connector) => (
                  <button
                    key={connector.type}
                    type="button"
                    onClick={() => {
                      setSelectedConnector(connector.type)
                      setSkippedConnect(false)
                    }}
                    className={cn(
                      "rounded-lg border px-3 py-2.5 text-left text-sm font-medium transition-colors",
                      selectedConnector === connector.type
                        ? "border-emerald-500/40 bg-emerald-500/10 text-foreground"
                        : "border-border bg-background/60 text-foreground hover:bg-muted/40",
                    )}
                  >
                    {connector.label}
                  </button>
                ))}
              </div>
              {selectedConnectorMeta ? (
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => {
                      window.open(selectedConnectorMeta.href, "_blank", "noopener,noreferrer")
                    }}
                  >
                    Connect {selectedConnectorMeta.label}
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Opens in a new tab — this setup screen stays right here.
                  </p>
                </div>
              ) : null}
              <Button
                variant="ghost"
                size="sm"
                className="mt-3 text-muted-foreground"
                onClick={() => {
                  setSkippedConnect(true)
                  setSelectedConnector(null)
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
                  href={`/marketplace/assets/${encodeURIComponent(selectedRole.packSlug)}?returnTo=${encodeURIComponent(APP_ROUTES.welcome)}`}
                  className="inline-flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm font-medium text-emerald-700 dark:text-emerald-300"
                >
                  Preview recommended pack
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : null}
              <Link
                href={`${APP_ROUTES.marketplace}?returnTo=${encodeURIComponent(APP_ROUTES.welcome)}`}
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
              <div className="rounded-xl border border-dashed border-emerald-500/30 bg-gradient-to-br from-emerald-500/5 to-violet-500/5 p-4 text-sm text-muted-foreground">
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
                <li>• Visit {SURFACE_COPY.insights.title} to see confidence and outcomes</li>
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
              onClick={() => void skipEntireWelcome()}
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
              <Button
                size="sm"
                disabled={submitting}
                onClick={() => void finishWelcome(skippedConnect)}
              >
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
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500/20 to-violet-500/10 ring-1 ring-emerald-500/20">
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
