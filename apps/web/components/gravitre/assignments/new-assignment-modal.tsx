"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { motion, AnimatePresence, useReducedMotion } from "framer-motion"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Icon } from "@/lib/icons"
import { agentsApi, marketplaceApi } from "@/lib/api"
import { cn } from "@/lib/utils"
import { hoverLift, pressScale } from "@/lib/animations"
import {
  avatarGradient,
  createAssignment,
  type AssignmentPriority,
} from "@/lib/assignments"
import type { DemoAssignment } from "@/lib/demo-assignments"
import {
  collectInstalledAgentIds,
  resolveDefaultAgentId,
} from "@/lib/resolve-default-agent"

const MODAL_STEPS = [
  { id: 1, title: "Agent", description: "Optional — change who will run this task" },
  { id: 2, title: "Describe the task", description: "Tell your agent what to do" },
  { id: 3, title: "Confirm", description: "Review and assign" },
] as const

const PRIORITIES: Array<{ id: AssignmentPriority; label: string }> = [
  { id: "low", label: "Low" },
  { id: "normal", label: "Normal" },
  { id: "high", label: "High" },
  { id: "urgent", label: "Urgent" },
]

interface AssignableAgent {
  id: string
  name: string
  role: string
  gradient: string
  successRate: number
}

const stepVariants = {
  enter: (direction: number) => ({ opacity: 0, x: direction >= 0 ? 20 : -20 }),
  center: { opacity: 1, x: 0 },
  exit: (direction: number) => ({ opacity: 0, x: direction >= 0 ? -20 : 20 }),
}

function ModalStepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div className="flex items-center gap-2">
      {MODAL_STEPS.map((step) => {
        const isActive = step.id === currentStep
        const isComplete = step.id < currentStep
        return (
          <div key={step.id} className="flex items-center gap-2">
            <div
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                isActive && "bg-emerald-500 text-white",
                isComplete && "bg-emerald-500/20 text-emerald-400",
                !isActive && !isComplete && "bg-secondary text-muted-foreground",
              )}
            >
              {isComplete ? <Icon name="check" size="xs" /> : step.id}
            </div>
            <span
              className={cn(
                "hidden text-xs font-medium sm:inline",
                isActive ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {step.title}
            </span>
            {step.id < MODAL_STEPS.length ? (
              <div className="hidden h-px w-6 bg-border sm:block" aria-hidden />
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export function NewAssignmentModal({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onCreated: (assignment: DemoAssignment) => void
}) {
  const reduced = useReducedMotion()
  const [step, setStep] = useState(2)
  const [direction, setDirection] = useState(1)
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [agentAutoResolved, setAgentAutoResolved] = useState(false)
  const [taskBrief, setTaskBrief] = useState("")
  const [priority, setPriority] = useState<AssignmentPriority>("normal")
  const [dueDate, setDueDate] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const autoResolvedRef = useRef(false)

  const { data: agentsResponse, isLoading: agentsLoading, error: agentsError, mutate } = useSWR(
    open ? "new-assignment-agents" : null,
    () => agentsApi.list(),
    { revalidateOnFocus: false },
  )
  const { data: installsResponse } = useSWR(
    open ? "new-assignment-installs" : null,
    () => marketplaceApi.listInstalls({ status: "active", limit: 100 }),
    { revalidateOnFocus: false },
  )

  const agents: AssignableAgent[] = useMemo(() => {
    return (agentsResponse?.agents ?? []).map((item) => {
      const successRate = item.stats?.successRate ?? 0
      return {
        id: item.id,
        name: item.name,
        role: item.role || item.description || "Agent",
        gradient: avatarGradient(item.personality?.color ?? ""),
        successRate: Number.isFinite(successRate) ? Math.round(successRate) : 0,
      }
    })
  }, [agentsResponse?.agents])

  const installedAgentIds = useMemo(
    () => collectInstalledAgentIds(installsResponse?.installs ?? []),
    [installsResponse?.installs],
  )

  const selectedAgent = agents.find((agent) => agent.id === selectedAgentId)

  useEffect(() => {
    if (!open || autoResolvedRef.current || agentsLoading || agents.length === 0) return
    const resolved = resolveDefaultAgentId({
      agents: agentsResponse?.agents ?? [],
      installedAgentIds,
    })
    if (!resolved) return
    autoResolvedRef.current = true
    setSelectedAgentId(resolved)
    setAgentAutoResolved(true)
    setStep(2)
  }, [open, agentsLoading, agents.length, agentsResponse?.agents, installedAgentIds])

  const resetForm = () => {
    setStep(2)
    setDirection(1)
    setSelectedAgentId(null)
    setAgentAutoResolved(false)
    autoResolvedRef.current = false
    setTaskBrief("")
    setPriority("normal")
    setDueDate("")
  }

  const canContinue = () => {
    if (step === 1) return selectedAgentId !== null
    if (step === 2) return selectedAgentId !== null && taskBrief.trim().length >= 10
    return true
  }

  const goNext = () => {
    if (step >= 3 || !canContinue()) return
    setDirection(1)
    setStep((current) => current + 1)
  }

  const goBack = () => {
    if (step === 1) {
      if (!selectedAgentId) return
      setDirection(1)
      setStep(2)
      return
    }
    if (step <= 1) return
    setDirection(-1)
    setStep((current) => current - 1)
  }

  const handleAssign = async () => {
    if (!selectedAgent || taskBrief.trim().length < 10) {
      toast.error("Select an agent and enter a task description")
      return
    }

    setIsSubmitting(true)
    try {
      const { assignment } = await createAssignment({
        agentId: selectedAgent.id,
        agentName: selectedAgent.name,
        agentRole: selectedAgent.role,
        agentGradient: selectedAgent.gradient,
        task: taskBrief.trim(),
        priority,
        dueDate: dueDate || undefined,
      })
      onCreated(assignment)
      toast.success("Assignment queued — your agent will start soon")
      onOpenChange(false)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create assignment")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (isSubmitting) return
        if (!next) resetForm()
        onOpenChange(next)
      }}
    >
      <DialogContent className="flex max-h-[90vh] max-w-2xl flex-col gap-0 overflow-hidden p-0">
        <DialogHeader className="space-y-4 border-b border-border px-6 py-5 text-left">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <DialogTitle className="text-lg">New Assignment</DialogTitle>
              <DialogDescription>{MODAL_STEPS[step - 1].description}</DialogDescription>
            </div>
            <ModalStepIndicator currentStep={step} />
          </div>
        </DialogHeader>

        <div className="min-h-[340px] flex-1 overflow-y-auto px-6 py-5">
          <AnimatePresence mode="wait" custom={direction}>
            {step === 1 ? (
              <motion.div
                key="step-1"
                custom={direction}
                variants={stepVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }}
                className="space-y-4"
              >
                {agentsLoading ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <Skeleton key={index} className="h-24 rounded-xl" />
                    ))}
                  </div>
                ) : agentsError ? (
                  <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-5 text-center">
                    <Icon name="warning" size="md" className="mx-auto mb-2 text-red-400" />
                    <p className="text-sm text-foreground">Could not load agents</p>
                    <p className="mt-1 text-xs text-muted-foreground">Check your connection and try again.</p>
                    <Button variant="outline" size="sm" className="mt-4" onClick={() => void mutate()}>
                      Try again
                    </Button>
                  </div>
                ) : agents.length === 0 ? (
                  <div className="rounded-xl border border-border bg-secondary/30 p-8 text-center">
                    <p className="text-sm text-muted-foreground">No active agents available.</p>
                    <Button asChild variant="outline" size="sm" className="mt-4">
                      <Link href="/agents/new">Create an agent</Link>
                    </Button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {agents.map((agent, index) => (
                      <motion.button
                        key={agent.id}
                        type="button"
                        initial={reduced ? false : { opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={reduced ? { duration: 0 } : { delay: index * 0.04 }}
                        whileHover={reduced ? undefined : hoverLift}
                        whileTap={reduced ? undefined : pressScale}
                        onClick={() => {
                          setSelectedAgentId(agent.id)
                          setAgentAutoResolved(false)
                        }}
                        className={cn(
                          "relative flex items-center gap-3 rounded-xl border p-4 text-left transition-colors",
                          selectedAgentId === agent.id
                            ? "border-emerald-500/50 bg-emerald-500/5"
                            : "border-border bg-card hover:border-muted-foreground/30 hover:bg-secondary/30",
                        )}
                      >
                        {selectedAgentId === agent.id ? (
                          <motion.span
                            layoutId="new-assignment-agent-ring"
                            className="pointer-events-none absolute inset-0 rounded-xl ring-1 ring-emerald-500/40"
                            transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 34 }}
                          />
                        ) : null}
                        <div
                          className={cn(
                            "flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br text-white",
                            agent.gradient,
                          )}
                        >
                          <Icon name="ai" size="md" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-semibold text-foreground">{agent.name}</p>
                          <p className="truncate text-xs text-muted-foreground">{agent.role}</p>
                          <p className="mt-1 text-[11px] text-emerald-400">{agent.successRate}% success</p>
                        </div>
                        {selectedAgentId === agent.id ? (
                          <div className="relative flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500">
                            <Icon name="check" size="xs" className="text-white" />
                          </div>
                        ) : null}
                      </motion.button>
                    ))}
                  </div>
                )}
              </motion.div>
            ) : null}

            {step === 2 ? (
              <motion.div
                key="step-2"
                custom={direction}
                variants={stepVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }}
                className="mx-auto max-w-xl space-y-5"
              >
                {agentsLoading ? (
                  <Skeleton className="h-14 w-full rounded-xl" />
                ) : selectedAgent ? (
                  <div className="flex items-center justify-between gap-3 rounded-xl border border-border bg-secondary/40 px-4 py-3">
                    <div className="min-w-0 flex items-center gap-3">
                      <div
                        className={cn(
                          "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white",
                          selectedAgent.gradient,
                        )}
                      >
                        <Icon name="ai" size="sm" />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-foreground">
                          {agentAutoResolved ? "Auto-selected" : "Assigned to"} {selectedAgent.name}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">{selectedAgent.role}</p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="shrink-0 text-xs text-muted-foreground"
                      onClick={() => {
                        setDirection(-1)
                        setStep(1)
                      }}
                    >
                      Change
                    </Button>
                  </div>
                ) : (
                  <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-sm">
                    <p className="text-foreground">No agent selected yet.</p>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-2"
                      onClick={() => {
                        setDirection(-1)
                        setStep(1)
                      }}
                    >
                      Choose agent
                    </Button>
                  </div>
                )}
                <div>
                  <label htmlFor="assignment-task" className="mb-2 block text-sm font-medium text-foreground">
                    Describe the task for your agent…
                  </label>
                  <textarea
                    id="assignment-task"
                    value={taskBrief}
                    onChange={(event) => setTaskBrief(event.target.value)}
                    placeholder="Describe the task for your agent…"
                    className="min-h-[160px] w-full resize-none rounded-xl border border-border bg-secondary px-4 py-3 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                    autoFocus
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    {taskBrief.trim().length} characters · minimum 10
                  </p>
                </div>

                <div>
                  <p className="mb-2 text-sm font-medium text-foreground">Priority</p>
                  <div className="flex flex-wrap gap-2">
                    {PRIORITIES.map((option) => (
                      <Button
                        key={option.id}
                        type="button"
                        variant={priority === option.id ? "default" : "outline"}
                        size="sm"
                        className={cn(
                          "text-xs",
                          priority === option.id && option.id === "urgent" && "bg-rose-500 hover:bg-rose-600",
                          priority === option.id && option.id === "high" && "bg-amber-500 hover:bg-amber-600",
                          priority === option.id && option.id === "low" && "bg-secondary text-foreground",
                        )}
                        onClick={() => setPriority(option.id)}
                      >
                        {option.label}
                      </Button>
                    ))}
                  </div>
                </div>

                <div>
                  <label htmlFor="assignment-due-date" className="mb-2 block text-sm font-medium text-foreground">
                    Due date <span className="font-normal text-muted-foreground">(optional)</span>
                  </label>
                  <Input
                    id="assignment-due-date"
                    type="date"
                    value={dueDate}
                    min={new Date().toISOString().slice(0, 10)}
                    onChange={(event) => setDueDate(event.target.value)}
                    className="max-w-xs bg-secondary"
                  />
                </div>
              </motion.div>
            ) : null}

            {step === 3 ? (
              <motion.div
                key="step-3"
                custom={direction}
                variants={stepVariants}
                initial="enter"
                animate="center"
                exit="exit"
                transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 360, damping: 32 }}
                className="mx-auto max-w-md space-y-5 text-center"
              >
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ring-1 ring-emerald-500/20">
                  <div
                    className={cn(
                      "flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br text-white",
                      selectedAgent?.gradient,
                    )}
                  >
                    <Icon name="ai" size="lg" />
                  </div>
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Assigning to</p>
                  <p className="mt-1 text-xl font-semibold text-foreground">{selectedAgent?.name}</p>
                  <p className="text-sm text-muted-foreground">{selectedAgent?.role}</p>
                </div>
                <div className="rounded-xl border border-border bg-card/50 p-4 text-left">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Task</p>
                  <p className="mt-2 text-sm leading-relaxed text-foreground">{taskBrief.trim()}</p>
                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full bg-secondary px-2.5 py-1 capitalize text-muted-foreground">
                      {priority} priority
                    </span>
                    {dueDate ? (
                      <span className="rounded-full bg-secondary px-2.5 py-1 text-muted-foreground">
                        Due {dueDate}
                      </span>
                    ) : null}
                  </div>
                </div>
                <p className="text-xs text-muted-foreground">
                  The assignment will appear at the top of your list as <span className="text-amber-400">Queued</span>.
                </p>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <DialogFooter className="flex-col gap-3 border-t border-border px-6 py-4 sm:flex-row sm:justify-between">
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
            <Link href="/assignments/new">Open full wizard</Link>
          </Button>
          <div className="flex w-full flex-col-reverse gap-2 sm:w-auto sm:flex-row">
            {step === 1 ? (
              <Button variant="outline" onClick={goBack} disabled={isSubmitting || !selectedAgentId}>
                Back to task
              </Button>
            ) : step === 3 ? (
              <Button variant="outline" onClick={goBack} disabled={isSubmitting}>
                Back
              </Button>
            ) : (
              <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                Cancel
              </Button>
            )}
            {step < 3 ? (
              <Button onClick={goNext} disabled={!canContinue()} className="gap-2">
                Continue
                <Icon name="chevronRight" size="sm" />
              </Button>
            ) : (
              <Button
                onClick={() => void handleAssign()}
                disabled={isSubmitting}
                className="gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 text-white hover:from-emerald-600 hover:to-teal-600"
              >
                {isSubmitting ? (
                  <>
                    <Icon name="spinner" size="sm" className="animate-spin" />
                    Assigning…
                  </>
                ) : (
                  <>
                    <Icon name="check" size="sm" />
                    Assign Task
                  </>
                )}
              </Button>
            )}
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
