"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Button } from "@/components/ui/button"
import { agentsApi, connectorsApi, marketplaceApi } from "@/lib/api"
import {
  collectInstalledAgentIds,
  resolveDefaultAgentId,
} from "@/lib/resolve-default-agent"
import { useAsyncJob } from "@/hooks/use-async-job"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

const steps = [
  "Agent",
  "Task brief",
  "Context",
  "Outputs",
  "Destination",
  "Review",
]
const outputs = ["Emails", "Social Posts", "Segments", "Workflows", "Reports"]
const briefStarters: Record<string, string> = {
  Campaign:
    "Create a campaign for [audience] to achieve [goal]. Use [sources] and include [deliverables].",
  Report:
    "Prepare a report on [topic] for [audience]. Cover [period], cite the sources, and highlight decisions to make.",
  Analysis:
    "Analyze [question] using [sources]. Explain the evidence, limitations, and recommended next steps.",
  Content:
    "Draft [content format] for [audience] about [topic]. Follow [voice and constraints] and include [call to action].",
}

export function NewAssignmentPageContent() {
  const router = useRouter()
  const preselectedAgent = useSearchParams().get("agent")
  const agentRequest = useSWR("assignment-agents", () => agentsApi.list(), {
    revalidateOnFocus: false,
  })
  const installRequest = useSWR(
    "assignment-installs",
    () => marketplaceApi.listInstalls({ status: "active", limit: 100 }),
    { revalidateOnFocus: false },
  )
  const connectorRequest = useSWR(
    "assignment-connectors",
    () => connectorsApi.list(),
    { revalidateOnFocus: false },
  )
  const agents = useMemo(
    () => agentRequest.data?.agents ?? [],
    [agentRequest.data?.agents],
  )
  const connectors = connectorRequest.data?.connectors ?? []
  const connected = connectors.filter((c) =>
    ["connected", "healthy", "active", "syncing"].includes(
      String(c.status).toLowerCase(),
    ),
  )
  const [step, setStep] = useState(1)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(
    preselectedAgent,
  )
  const autoResolved = useRef(false)
  const [brief, setBrief] = useState("")
  const [priority, setPriority] = useState("normal")
  const [sources, setSources] = useState<string[]>([])
  const [selectedOutputs, setOutputs] = useState<string[]>([])
  const [destinations, setDestinations] = useState<string[]>([])
  const [useTrainingKnowledge, setUseTrainingKnowledge] = useState(true)
  const [requireApproval, setRequireApproval] = useState(true)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const submitting = useRef(false)
  const { submitJob, isWorking } = useAsyncJob()
  const agent = agents.find((a) => a.id === selectedAgent)
  const validBrief = brief.trim().length >= 10
  const availableDestinations = [
    ...connected.map((c) => ({ id: c.id, name: c.name })),
    { id: "assignment", name: "Keep in assignment" },
  ]
  const validDestinations = availableDestinations.filter((c) =>
    destinations.includes(c.id),
  )
  const valid = Boolean(
    agent && validBrief && selectedOutputs.length && validDestinations.length,
  )
  const toggle = (values: string[], id: string) =>
    values.includes(id) ? values.filter((v) => v !== id) : [...values, id]

  useEffect(() => {
    if (
      autoResolved.current ||
      agentRequest.isLoading ||
      installRequest.isLoading ||
      !agents.length
    )
      return
    const id = resolveDefaultAgentId({
      agents,
      preferredAgentId: preselectedAgent,
      installedAgentIds: collectInstalledAgentIds(
        installRequest.data?.installs ?? [],
      ),
    })
    if (id) {
      autoResolved.current = true
      setSelectedAgent(id)
      setStep(2)
    }
  }, [
    agents,
    agentRequest.isLoading,
    installRequest.isLoading,
    installRequest.data,
    preselectedAgent,
  ])

  const canContinue =
    step === 1
      ? Boolean(agent)
      : step === 2
        ? Boolean(agent && validBrief)
        : step === 4
          ? selectedOutputs.length > 0
          : step === 5
            ? validDestinations.length > 0
            : true
  async function run() {
    if (!valid || isWorking || submitting.current) return
    submitting.current = true
    setSubmitError(null)
    try {
      const job = await submitJob(brief.trim(), {
        agentId: agent!.id,
        context: {
          priority,
          useTrainingKnowledge,
          requireApproval,
          dataSources: connected
            .filter((c) => sources.includes(c.id))
            .map((c) => c.name),
          outputs: selectedOutputs,
          destinations: availableDestinations
            .filter((c) => destinations.includes(c.id))
            .map((c) => c.name),
        },
      })
      toast.success("Assignment submitted")
      router.push(`/assignments/${job.jobId}`)
    } catch (error) {
      setSubmitError(
        error instanceof Error ? error.message : "Could not submit assignment",
      )
    } finally {
      submitting.current = false
    }
  }

  return (
    <AppShell title="New assignment">
      <div
        className="flex min-h-0 flex-1 flex-col bg-[color:var(--g-canvas)]"
        data-composition="create"
      >
        <GravitrePageHeader
          eyebrow="Work · Create"
          title="New assignment"
          description="Give an agent a clear brief, useful context, and an outcome to work toward."
          actions={
            <Button variant="outline" className="min-h-11" asChild>
              <Link href="/assignments">All assignments</Link>
            </Button>
          }
        />
        <div className="grid min-h-0 flex-1 lg:grid-cols-[240px_minmax(0,1fr)]">
          <nav
            aria-label="Assignment steps"
            className="border-b border-[color:var(--g-border-default)] p-4 lg:border-b-0 lg:border-r lg:p-6"
          >
            <ol className="flex gap-2 overflow-x-auto lg:flex-col">
              {steps.map((name, i) => (
                <li key={name} className="shrink-0">
                  <button
                    type="button"
                    aria-current={step === i + 1 ? "step" : undefined}
                    disabled={isWorking || i + 1 > step}
                    onClick={() => setStep(i + 1)}
                    className={cn(
                      "flex min-h-11 w-full items-center gap-3 rounded-lg px-3 text-left text-sm",
                      step === i + 1
                        ? "bg-[color:var(--g-brand-soft)] font-medium text-[color:var(--g-brand-active)]"
                        : "text-muted-foreground disabled:opacity-50",
                    )}
                  >
                    <span className="tabular-nums">{i + 1}</span>
                    {name}
                  </button>
                </li>
              ))}
            </ol>
            {agent && (
              <div className="mt-6 hidden items-center gap-3 border-t border-[color:var(--g-border-default)] pt-5 lg:flex">
                <AgentIdentityAvatar
                  agent={agent}
                  size="md"
                  showStatusDot={false}
                />
                <div className="min-w-0">
                  <p className="break-words text-sm font-medium">
                    {agent.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Assigned agent
                  </p>
                </div>
              </div>
            )}
          </nav>
          <div className="min-w-0 overflow-y-auto px-4 pb-28 pt-6 sm:px-8 lg:px-12">
            <div className="mx-auto max-w-3xl space-y-6">
              <div>
                <p className="text-xs text-muted-foreground">
                  Step {step} of {steps.length}
                </p>
                <h2 className="mt-2 font-sans text-2xl font-medium">
                  {steps[step - 1]}
                </h2>
              </div>
              {agentRequest.error && (
                <WorkSectionErrorCard
                  title="Could not load agents"
                  error={agentRequest.error}
                  onRetry={() => void agentRequest.mutate()}
                />
              )}
              {step === 1 && (
                <div className="divide-y divide-[color:var(--g-border-subtle)] border-y border-[color:var(--g-border-default)]">
                  {agentRequest.isLoading && (
                    <p className="py-6 text-sm text-muted-foreground">
                      Loading agents…
                    </p>
                  )}
                  {!agentRequest.isLoading &&
                    !agentRequest.error &&
                    !agents.length && (
                      <p className="py-6 text-sm">
                        No agents available.{" "}
                        <Link className="underline" href="/agents/new">
                          Create an agent
                        </Link>
                      </p>
                    )}
                  {agents.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      aria-pressed={selectedAgent === a.id}
                      onClick={() => setSelectedAgent(a.id)}
                      className={cn(
                        "flex min-h-20 w-full items-center gap-4 px-3 py-4 text-left",
                        selectedAgent === a.id &&
                          "bg-[color:var(--g-brand-soft)]",
                      )}
                    >
                      <AgentIdentityAvatar
                        agent={a}
                        size="md"
                        showStatusDot={false}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block break-words font-medium">
                          {a.name}
                        </span>
                        <span className="block text-sm text-muted-foreground">
                          {a.role || a.description || "Agent"}
                        </span>
                      </span>
                      {selectedAgent === a.id && (
                        <span className="text-xs text-[color:var(--g-brand-active)]">
                          Selected
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {step === 2 && (
                <div className="space-y-6">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[color:var(--g-border-default)] pb-4">
                    <p className="text-sm">
                      {agent
                        ? `Assigned to ${agent.name}`
                        : "Choose an agent to continue"}
                    </p>
                    <Button
                      variant="ghost"
                      className="min-h-11"
                      onClick={() => setStep(1)}
                    >
                      Change agent
                    </Button>
                  </div>
                  <label className="block space-y-2">
                    <span className="text-sm font-medium">
                      What do you need done?
                    </span>
                    <textarea
                      value={brief}
                      onChange={(e) => setBrief(e.target.value)}
                      aria-describedby="brief-help"
                      placeholder="Describe the goal, audience, constraints, and evidence the agent should use."
                      className="min-h-56 w-full resize-y rounded-xl border border-[color:var(--g-border-default)] bg-background p-4 text-sm focus-visible:outline-2 focus-visible:outline-[color:var(--g-brand)]"
                    />
                  </label>
                  <p id="brief-help" className="text-xs text-muted-foreground">
                    At least 10 characters. {brief.trim().length} entered.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(briefStarters).map(([name, text]) => (
                      <Button
                        key={name}
                        variant="outline"
                        className="min-h-11"
                        onClick={() =>
                          setBrief((prev) =>
                            prev ? `${prev}\n\n${text}` : text,
                          )
                        }
                      >
                        {name} starter
                      </Button>
                    ))}
                  </div>
                  <fieldset>
                    <legend className="mb-2 text-sm font-medium">
                      Priority
                    </legend>
                    <div className="flex flex-wrap gap-2">
                      {["normal", "high", "urgent"].map((p) => (
                        <Button
                          key={p}
                          aria-pressed={priority === p}
                          variant={priority === p ? "default" : "outline"}
                          className="min-h-11 capitalize"
                          onClick={() => setPriority(p)}
                        >
                          {p}
                        </Button>
                      ))}
                    </div>
                  </fieldset>
                </div>
              )}
              {step === 3 && (
                <div className="space-y-6">
                  <label className="flex min-h-11 items-center gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={useTrainingKnowledge}
                      onChange={(e) =>
                        setUseTrainingKnowledge(e.target.checked)
                      }
                      className="size-5 accent-[var(--g-brand)]"
                    />
                    Request the agent’s training knowledge
                  </label>
                  <div>
                    <h3 className="text-sm font-medium">Connected systems</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Connection status comes from your workspace. Access is
                      checked during execution.
                    </p>
                  </div>
                  {connectorRequest.error && (
                    <WorkSectionErrorCard
                      title="Could not refresh connections"
                      error={connectorRequest.error}
                      onRetry={() => void connectorRequest.mutate()}
                    />
                  )}
                  {connectorRequest.isLoading ? (
                    <p className="text-sm text-muted-foreground">
                      Loading connections…
                    </p>
                  ) : !connectorRequest.error && !connectors.length ? (
                    <p className="text-sm text-muted-foreground">
                      No connections configured. You can continue with the
                      brief.
                    </p>
                  ) : null}
                  <div className="divide-y border-y border-[color:var(--g-border-default)]">
                    {connectors.map((c) => (
                      <label
                        key={c.id}
                        className="flex min-h-16 items-center gap-3 py-3"
                      >
                        <input
                          type="checkbox"
                          checked={sources.includes(c.id)}
                          disabled={!connected.some((item) => item.id === c.id)}
                          onChange={() => setSources(toggle(sources, c.id))}
                          className="size-5 accent-[var(--g-brand)]"
                        />
                        <span className="min-w-0 flex-1 break-words text-sm">
                          {c.name}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {c.status || "Not reported"}
                        </span>
                      </label>
                    ))}
                  </div>
                  <Link
                    className="inline-flex min-h-11 items-center text-sm underline"
                    href="/connectors"
                  >
                    Manage connections
                  </Link>
                </div>
              )}
              {step === 4 && (
                <fieldset className="space-y-3">
                  <legend className="mb-3 text-sm text-muted-foreground">
                    Request the deliverables you need. The assignment result
                    reports what was actually produced.
                  </legend>
                  {outputs.map((name) => (
                    <label
                      key={name}
                      className="flex min-h-14 items-center gap-3 border-b border-[color:var(--g-border-subtle)] py-3"
                    >
                      <input
                        type="checkbox"
                        checked={selectedOutputs.includes(name)}
                        onChange={() =>
                          setOutputs(toggle(selectedOutputs, name))
                        }
                        className="size-5 accent-[var(--g-brand)]"
                      />
                      <span className="text-sm">{name}</span>
                    </label>
                  ))}
                </fieldset>
              )}
              {step === 5 && (
                <div className="space-y-5">
                  <p className="text-sm text-muted-foreground">
                    Destination preferences are included in the brief. Delivery
                    depends on available actions and permissions; selecting a
                    system does not send anything.
                  </p>
                  {connectorRequest.error && (
                    <WorkSectionErrorCard
                      title="Could not refresh destinations"
                      error={connectorRequest.error}
                      onRetry={() => void connectorRequest.mutate()}
                    />
                  )}
                  {availableDestinations.map((c) => (
                    <label
                      key={c.id}
                      className="flex min-h-14 items-center gap-3 border-b border-[color:var(--g-border-subtle)] py-3"
                    >
                      <input
                        type="checkbox"
                        checked={destinations.includes(c.id)}
                        onChange={() =>
                          setDestinations(toggle(destinations, c.id))
                        }
                        className="size-5 accent-[var(--g-brand)]"
                      />
                      <span className="text-sm">{c.name}</span>
                    </label>
                  ))}
                  <label className="flex min-h-11 items-center gap-3 text-sm">
                    <input
                      type="checkbox"
                      checked={requireApproval}
                      onChange={(e) => setRequireApproval(e.target.checked)}
                      className="size-5 accent-[var(--g-brand)]"
                    />
                    Request approval before delivery
                  </label>
                  <p className="text-xs text-muted-foreground">
                    This preference does not override the workspace’s approval
                    and authorization rules.
                  </p>
                </div>
              )}
              {step === 6 && (
                <div className="space-y-5">
                  <dl className="divide-y border-y border-[color:var(--g-border-default)]">
                    {[
                      ["Agent", agent?.name ?? "Choose an agent"],
                      ["Task brief", brief],
                      ["Priority", priority],
                      [
                        "Training knowledge",
                        useTrainingKnowledge ? "Requested" : "Not requested",
                      ],
                      [
                        "Context",
                        connected
                          .filter((c) => sources.includes(c.id))
                          .map((c) => c.name)
                          .join(", ") || "Brief only",
                      ],
                      ["Outputs requested", selectedOutputs.join(", ")],
                      [
                        "Destinations requested",
                        availableDestinations
                          .filter((c) => destinations.includes(c.id))
                          .map((c) => c.name)
                          .join(", ") || "Choose a destination",
                      ],
                      [
                        "Approval preference",
                        requireApproval
                          ? "Requested before delivery"
                          : "Workspace rules apply",
                      ],
                    ].map(([name, value]) => (
                      <div
                        key={name}
                        className="grid gap-2 py-4 sm:grid-cols-[160px_minmax(0,1fr)]"
                      >
                        <dt className="text-sm text-muted-foreground">
                          {name}
                        </dt>
                        <dd className="whitespace-pre-wrap break-words text-sm">
                          {value}
                        </dd>
                      </div>
                    ))}
                  </dl>
                  <p className="text-sm text-muted-foreground">
                    Submit to create an assignment, then follow its execution
                    and review the returned evidence.
                  </p>
                </div>
              )}
              {submitError && (
                <p role="alert" className="text-sm text-destructive">
                  {submitError}
                </p>
              )}
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[color:var(--g-border-default)] pt-5">
                <Button
                  variant="outline"
                  className="min-h-11"
                  disabled={step === 1 || isWorking}
                  onClick={() => setStep(step - 1)}
                >
                  Back
                </Button>
                {step < 6 ? (
                  <Button
                    className="min-h-11"
                    disabled={!canContinue || isWorking}
                    onClick={() => setStep(step + 1)}
                  >
                    Continue
                  </Button>
                ) : (
                  <Button
                    className="min-h-11"
                    disabled={!valid || isWorking}
                    onClick={() => void run()}
                  >
                    {isWorking ? "Submitting…" : "Run task"}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
