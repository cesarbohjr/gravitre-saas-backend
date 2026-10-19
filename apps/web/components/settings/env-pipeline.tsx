"use client"

/**
 * Environments (design p20). Rendered by app/(app)/environments/page.tsx inside
 * SettingsShell (Governance / Infrastructure). Stat tiles, the animated
 * Development → Staging → Production pipeline, and a detail card for the
 * selected stage. Everything comes from GET /api/environments; create, turn
 * on/off and delete call the real endpoints and are admin only.
 */
import { useMemo, useState } from "react"
import useSWR from "swr"
import {
  Activity,
  Bot,
  Check,
  Copy,
  Database,
  GitBranch,
  Info,
  Layers,
  MoreHorizontal,
  Plug,
  Plus,
  Power,
  Server,
  ShieldCheck,
  Trash2,
} from "lucide-react"
import { toast } from "sonner"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import {
  ENVIRONMENTS_KEY,
  buildStages,
  countOrNull,
  environmentsSettingsApi,
  normalizeEnvironments,
  sumResource,
  type EnvironmentsPayload,
  type StageId,
  type StageView,
} from "@/lib/settings-api/environments"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { SettingsShell } from "./settings-shell"
import { SetError, SetIco, SetNote, SetPill, SetSkeleton, SetStat, formatDay } from "./settings-kit"
import "./env-pipeline.css"

const AFTER_DEPLOY = "Shows after the first deploy"

function stateLabel(stage: StageView): string {
  if (!stage.env) return "Not set up"
  return stage.env.isActive ? "Active" : "Turned off"
}

function StageDot({ stage }: { stage: StageView }) {
  const tone = !stage.env ? "ghost" : stage.env.isActive ? "green gs-live" : "amber"
  return <span className={`gs-dot ${tone}`} aria-hidden />
}

function StagePill({ stage }: { stage: StageView }) {
  const tone = !stage.env ? "neutral" : stage.env.isActive ? "green" : "amber"
  return (
    <SetPill tone={tone}>
      <StageDot stage={stage} />
      {stateLabel(stage)}
    </SetPill>
  )
}

/** Flowing dashed arrow between two stages (design gv-flow2), green when the next stage is live. */
export function StageConnector({ live }: { live: boolean }) {
  const color = live ? "var(--gs-green-bright)" : "var(--gs-off)"
  return (
    <svg className="env-arrow" width="80" height="20" viewBox="0 0 80 20" aria-hidden focusable="false">
      <path d="M4 10 H 76" stroke={color} strokeWidth="2" strokeDasharray="5 5" className="gs-flow2" fill="none" />
      <path d="M70 5 l6 5 -6 5" stroke={color} strokeWidth="2" fill="none" />
    </svg>
  )
}

export function EnvironmentsSettings() {
  const { user } = useAuth()
  const { isAdmin, showAdmin, loading: adminLoading } = useOrgAdmin()
  const { data, error, isLoading, mutate } = useSWR<EnvironmentsPayload>(
    user ? ENVIRONMENTS_KEY : null,
    () => environmentsSettingsApi.list(),
    { revalidateOnFocus: false },
  )
  const envs = useMemo(() => normalizeEnvironments(data), [data])
  const stages = useMemo(() => buildStages(envs), [envs])
  const [picked, setPicked] = useState<StageId | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<StageView | null>(null)
  const [copied, setCopied] = useState(false)

  const selected = stages.find((stage) => stage.id === picked) ?? stages.find((stage) => stage.env?.isDefault) ?? stages[2]
  const missing = stages.filter((stage) => !stage.env)
  const limit = typeof data?.environmentsLimit === "number" ? data.environmentsLimit : null
  const atLimit = limit !== null && envs.length >= limit
  const createBlockedReason = !isAdmin
    ? "Admin role required to create environments."
    : atLimit
      ? `Your plan includes ${limit} environment${limit === 1 ? "" : "s"}. Upgrade to add more.`
      : null

  async function create(stage: StageView) {
    if (createBlockedReason) {
      toast.error(createBlockedReason)
      return
    }
    setBusy(`create:${stage.id}`)
    try {
      await environmentsSettingsApi.create(stage.id)
      toast.success(`${stage.name} created`)
      setPicked(stage.id)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : `Could not create ${stage.name}`)
    } finally {
      setBusy(null)
    }
  }

  async function toggleActive(stage: StageView) {
    if (!stage.env || !isAdmin) return
    const next = !stage.env.isActive
    setBusy(`toggle:${stage.id}`)
    try {
      await environmentsSettingsApi.setActive(stage.env.id, next)
      toast.success(`${stage.name} turned ${next ? "on" : "off"}`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : "Could not update environment")
    } finally {
      setBusy(null)
    }
  }

  async function remove(stage: StageView) {
    if (!stage.env || !isAdmin) return
    setBusy(`delete:${stage.id}`)
    try {
      await environmentsSettingsApi.remove(stage.env.id)
      toast.success(`${stage.name} deleted`)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : "Could not delete environment")
    } finally {
      setBusy(null)
      setConfirmDelete(null)
    }
  }

  const headerAction = (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="gs-btn dark"
          disabled={isLoading || adminLoading || !isAdmin || missing.length === 0 || atLimit}
          title={
            !isAdmin
              ? "Admin role required to create environments"
              : missing.length === 0
                ? "All three stages are set up"
                : createBlockedReason ?? undefined
          }
        >
          <Plus size={16} aria-hidden />
          New environment
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>Create a stage</DropdownMenuLabel>
        {missing.map((stage) => (
          <DropdownMenuItem key={stage.id} className="gap-2" onSelect={() => void create(stage)} disabled={busy !== null}>
            <Server className="h-3.5 w-3.5" aria-hidden />
            {stage.name}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )

  const totals = {
    online: envs.filter((env) => env.isActive).length,
    workflows: countOrNull(sumResource(envs, "workflows")),
    agents: countOrNull(sumResource(envs, "agents")),
    configured: stages.filter((stage) => stage.env).length,
  }

  const firstLoad = isLoading && !data

  return (
    <SettingsShell
      activeSection="environments"
      isAdmin={showAdmin}
      crumb="Governance / Infrastructure"
      actions={user ? headerAction : undefined}
    >
      {!user ? (
        <SetNote>Sign in to view environments.</SetNote>
      ) : firstLoad ? (
        <section className="gs-card">
          <SetSkeleton rows={4} label="Loading environments" />
        </section>
      ) : error && !data ? (
        <section className="gs-card">
          <SetError message="Could not load environments." onRetry={() => void mutate()} />
        </section>
      ) : (
        <>
          {error ? (
            <SetNote tone="red">Could not refresh environments. Showing the last data that loaded.</SetNote>
          ) : null}
          <div className="gs-stats" aria-label="Environment totals">
            <SetStat icon={Activity} tone="green" label="Online" value={totals.online} hint="Environments running" />
            <SetStat
              icon={GitBranch}
              label="Workflows"
              value={totals.workflows}
              hint={totals.workflows === null ? AFTER_DEPLOY : "Across environments"}
            />
            <SetStat
              icon={Bot}
              label="Agents"
              value={totals.agents}
              hint={totals.agents === null ? AFTER_DEPLOY : "Across environments"}
            />
            <SetStat icon={Layers} label="Configured" value={totals.configured} hint={`Of ${stages.length} stages`} />
          </div>

          <section className="gs-card pad" aria-label="Deployment pipeline">
            <div className="env-pipe-head">
              <div>
                <div className="gs-eyebrow">Deployment pipeline</div>
                <div className="gs-strong env-pipe-title">Promote changes stage by stage</div>
              </div>
              {missing.length ? (
                <SetPill tone="amber">
                  <Info size={13} aria-hidden />
                  {missing.length} {missing.length === 1 ? "stage" : "stages"} not set up
                </SetPill>
              ) : (
                <SetPill tone="green">
                  <Check size={13} aria-hidden />
                  All stages set up
                </SetPill>
              )}
            </div>
            <div className="env-pipe" role="group" aria-label="Pipeline stages">
              {stages.map((stage, index) => (
                <div key={stage.id} className="env-pipe-step">
                  {index > 0 ? <StageConnector live={stage.live} /> : null}
                  <button
                    type="button"
                    className={`gs-wcard env-stage${stage.env ? "" : " ghost"}`}
                    aria-pressed={selected?.id === stage.id}
                    onClick={() => setPicked(stage.id)}
                  >
                    <span className="env-stage-top">
                      <SetIco icon={Server} tone={stage.live ? "green" : "mute"} />
                      <StagePill stage={stage} />
                    </span>
                    <span className="gs-strong">{stage.name}</span>
                    <span className="env-stage-hint">{stage.hint}</span>
                  </button>
                </div>
              ))}
            </div>
          </section>

          <SetNote tone="white" icon={ShieldCheck}>
            <strong>Organization wide.</strong> Environment changes apply to everyone in this workspace.
          </SetNote>
          {!adminLoading && !isAdmin ? (
            <SetNote tone="amber">
              <strong>Admin access required.</strong> Ask an organization owner to grant you admin before changing
              environments.
            </SetNote>
          ) : null}

          {selected ? (
            <StageDetail
              stage={selected}
              isAdmin={isAdmin}
              busy={busy}
              createBlockedReason={createBlockedReason}
              copied={copied}
              onCopy={async (url) => {
                try {
                  await navigator.clipboard.writeText(url)
                  setCopied(true)
                  window.setTimeout(() => setCopied(false), 2000)
                } catch {
                  toast.error("Could not copy the endpoint")
                }
              }}
              onCreate={() => void create(selected)}
              onToggle={() => void toggleActive(selected)}
              onDelete={() => setConfirmDelete(selected)}
            />
          ) : null}
        </>
      )}

      <AlertDialog open={confirmDelete !== null} onOpenChange={(open) => (!open ? setConfirmDelete(null) : null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {confirmDelete?.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes the {confirmDelete?.name.toLowerCase()} environment for everyone in this workspace. Workflows
              and agents linked to it are kept but no longer tied to a stage. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault()
                if (confirmDelete) void remove(confirmDelete)
              }}
              disabled={busy !== null}
            >
              {busy?.startsWith("delete:") ? "Deleting…" : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SettingsShell>
  )
}

function StageDetail({
  stage,
  isAdmin,
  busy,
  createBlockedReason,
  copied,
  onCopy,
  onCreate,
  onToggle,
  onDelete,
}: {
  stage: StageView
  isAdmin: boolean
  busy: string | null
  createBlockedReason: string | null
  copied: boolean
  onCopy: (url: string) => void
  onCreate: () => void
  onToggle: () => void
  onDelete: () => void
}) {
  const env = stage.env
  const metrics = env
    ? [
        { label: "Workflows", icon: GitBranch, value: countOrNull(env.resources.workflows) },
        { label: "Agents", icon: Bot, value: countOrNull(env.resources.agents) },
        { label: "Connectors", icon: Plug, value: countOrNull(env.resources.connectors) },
        { label: "Sources", icon: Database, value: countOrNull(env.resources.sources) },
      ]
    : []
  const anyMissing = metrics.some((metric) => metric.value === null)
  const created = env ? formatDay(env.createdAt) : null

  return (
    <section className="gs-card clip" aria-label={`${stage.name} environment`} aria-live="polite">
      <div className="env-detail-head">
        <SetIco icon={Server} size="lg" tone={stage.live ? "green" : "mute"} />
        <div className="env-detail-id">
          <div className="env-detail-name">
            <h3>{stage.name}</h3>
            {env?.isDefault ? <span className="gs-chip">Default</span> : null}
          </div>
          <div className="env-detail-sub">
            <span className="env-state">
              <StageDot stage={stage} />
              {stateLabel(stage)}
            </span>
            <span className="gs-mono">{env?.name ?? stage.id}</span>
            {created ? <span>Created {created}</span> : null}
          </div>
        </div>
        {env ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="gs-iconbtn"
                aria-label={`${stage.name} environment options`}
                disabled={!isAdmin || busy !== null}
                title={!isAdmin ? "Admin role required" : undefined}
              >
                <MoreHorizontal size={18} aria-hidden />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem className="gap-2" onSelect={onToggle}>
                <Power className="h-3.5 w-3.5" aria-hidden />
                {env.isActive ? "Turn off" : "Turn on"}
              </DropdownMenuItem>
              {!env.isDefault ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem className="gap-2 text-destructive focus:text-destructive" onSelect={onDelete}>
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                    Delete
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>

      {env ? (
        <>
          <div className="env-metrics">
            {metrics.map((metric) => (
              <div key={metric.label} className="env-metric">
                <div className="l">{metric.label}</div>
                <div className={`v${metric.value === null ? " none" : ""}`}>
                  {metric.value === null ? "None yet" : metric.value.toLocaleString()}
                </div>
              </div>
            ))}
          </div>
          {anyMissing ? <p className="gs-sub env-metrics-note">Numbers appear after the first deploy.</p> : null}
          <div className="env-endpoint">
            <div className="env-endpoint-label">API endpoint</div>
            <div className="env-endpoint-row">
              <div className={`gs-mono env-endpoint-value${env.apiUrl ? "" : " none"}`}>
                {env.apiUrl ?? "None yet. It appears after the first deploy."}
              </div>
              <button
                type="button"
                className="gs-btn line sm"
                disabled={!env.apiUrl}
                onClick={() => env.apiUrl && onCopy(env.apiUrl)}
                aria-label={copied ? "API endpoint copied" : "Copy API endpoint"}
              >
                {copied ? <Check size={15} aria-hidden /> : <Copy size={15} aria-hidden />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        </>
      ) : (
        <div className="gs-empty">
          <b>{stage.name} is not set up</b>
          <p>{stage.why}</p>
          <button
            type="button"
            className="gs-btn green sm"
            disabled={Boolean(createBlockedReason) || busy !== null}
            onClick={onCreate}
          >
            <Plus size={15} aria-hidden />
            {busy === `create:${stage.id}` ? `Creating ${stage.name}…` : `Create ${stage.name}`}
          </button>
          {createBlockedReason ? <p className="gs-sub">{createBlockedReason}</p> : null}
        </div>
      )}
    </section>
  )
}
