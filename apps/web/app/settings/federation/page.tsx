"use client"

import { Suspense, useMemo, useState } from "react"
import useSWR from "swr"
import { motion } from "framer-motion"
import { toast } from "sonner"
import {
  Handshake,
  Plus,
  ArrowLeftRight,
  ShieldCheck,
  Network,
  Clock,
  Inbox,
  Send,
  Lock,
} from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { Button } from "@/components/ui/button"
import { GridPattern, AnimatedCounter } from "@/components/gravitre/premium-effects"
import { federationApi } from "@/lib/api"
import { formatUnknownError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import type {
  FederationPartnership,
  FederationHandoff,
  FederationConnectorGrant,
  FederationDelegatedTask,
} from "@/types/api"
import { PartnerCard, awaitingOurConsent } from "@/components/federation/partner-card"
import { HandoffTimeline } from "@/components/federation/handoff-timeline"
import { FederationGrantList } from "@/components/federation/federation-grant-list"
import { FederationDelegatedTaskList } from "@/components/federation/federation-delegated-task-list"
import { InvitePartnerDialog } from "@/components/federation/invite-partner-dialog"
import { CreateHandoffDialog } from "@/components/federation/create-handoff-dialog"
import { ProposeGrantDialog } from "@/components/federation/propose-grant-dialog"
import { CreateDelegatedTaskDialog } from "@/components/federation/create-delegated-task-dialog"
import { FederationEmptyState } from "@/components/federation/federation-empty-state"
import { TrustBoundaryVisual } from "@/components/federation/trust-boundary-visual"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.06, duration: 0.4, ease: [0.16, 1, 0.3, 1] as const },
  }),
}

export default function FederationPage() {
  return (
    <AppShell title="Settings">
      <Suspense fallback={null}>
        <FederationContent />
      </Suspense>
    </AppShell>
  )
}

function FederationContent() {
  const { user, loading: authLoading } = useAuth()
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const currentOrgId = getSelectedOrgFromStorage()?.id
  const [inviteOpen, setInviteOpen] = useState(false)
  const [handoffOpen, setHandoffOpen] = useState(false)
  const [grantOpen, setGrantOpen] = useState(false)
  const [taskOpen, setTaskOpen] = useState(false)

  const {
    data: partnershipsData,
    error: partnershipsError,
    isLoading: loadingPartners,
    mutate: mutatePartners,
  } = useSWR("federation/partnerships", () => federationApi.listPartnerships())

  const {
    data: handoffsData,
    error: handoffsError,
    isLoading: loadingHandoffs,
    mutate: mutateHandoffs,
  } = useSWR("federation/handoffs", () => federationApi.listHandoffs({ direction: "all" }))

  const {
    data: grantsData,
    error: grantsError,
    isLoading: loadingGrants,
    mutate: mutateGrants,
  } = useSWR("federation/grants", () => federationApi.listConnectorGrants())

  const {
    data: tasksData,
    error: tasksError,
    isLoading: loadingTasks,
    mutate: mutateTasks,
  } = useSWR("federation/delegated-tasks", () => federationApi.listDelegatedTasks({ direction: "all" }))

  const partnerships = useMemo(
    () => partnershipsData?.partnerships ?? [],
    [partnershipsData],
  )
  const handoffs = useMemo(() => handoffsData?.handoffs ?? [], [handoffsData])
  const grants = useMemo(() => grantsData?.grants ?? [], [grantsData])
  const delegatedTasks = useMemo(() => tasksData?.tasks ?? [], [tasksData])

  const stats = useMemo(() => {
    const active = partnerships.filter((p) => p.status === "active").length
    const pending = partnerships.filter((p) => p.status === "pending_partner").length
    const openHandoffs = handoffs.filter(
      (h) => h.status === "pending_receiver" || h.status === "accepted",
    ).length
    return { active, pending, openHandoffs, total: partnerships.length }
  }, [partnerships, handoffs])

  const pendingInvites = useMemo(
    () => partnerships.filter((p) => awaitingOurConsent(p)),
    [partnerships],
  )

  const activePartnerships = useMemo(
    () => partnerships.filter((p) => p.status === "active"),
    [partnerships],
  )

  const loadError = partnershipsError || handoffsError || grantsError || tasksError

  async function refreshAll() {
    await Promise.all([mutatePartners(), mutateHandoffs(), mutateGrants(), mutateTasks()])
  }

  async function handlePartnerAction(
    action: "accept" | "reject" | "revoke",
    partnership: FederationPartnership,
  ) {
    try {
      if (action === "accept") await federationApi.acceptPartnership(partnership.id)
      if (action === "reject") await federationApi.rejectPartnership(partnership.id)
      if (action === "revoke") await federationApi.revokePartnership(partnership.id)
      toast.success(
        action === "accept"
          ? "Partnership activated"
          : action === "reject"
            ? "Invitation declined"
            : "Partnership revoked",
      )
      await refreshAll()
    } catch (err) {
      toast.error("Action failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    }
  }

  async function handleHandoffAction(action: "accept" | "reject", handoff: FederationHandoff) {
    try {
      if (action === "accept") await federationApi.acceptHandoff(handoff.id)
      if (action === "reject") await federationApi.rejectHandoff(handoff.id)
      toast.success(action === "accept" ? "Handoff accepted" : "Handoff declined")
      await mutateHandoffs()
    } catch (err) {
      toast.error("Action failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    }
  }

  async function handleGrantAction(
    action: "accept" | "reject" | "revoke",
    grant: FederationConnectorGrant,
  ) {
    try {
      if (action === "accept") await federationApi.acceptConnectorGrant(grant.id)
      if (action === "reject") await federationApi.rejectConnectorGrant(grant.id)
      if (action === "revoke") await federationApi.revokeConnectorGrant(grant.id)
      toast.success(
        action === "accept" ? "Grant accepted" : action === "reject" ? "Grant declined" : "Grant revoked",
      )
      await mutateGrants()
    } catch (err) {
      toast.error("Grant action failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    }
  }

  async function handleDelegatedTaskAction(action: "accept" | "reject", task: FederationDelegatedTask) {
    try {
      if (action === "accept") await federationApi.acceptDelegatedTask(task.id)
      if (action === "reject") await federationApi.rejectDelegatedTask(task.id)
      toast.success(action === "accept" ? "Task accepted" : "Task declined")
      await mutateTasks()
    } catch (err) {
      toast.error("Task action failed", {
        description: err instanceof Error ? err.message : "Please try again.",
      })
    }
  }

  const statCards = [
    { label: "Active partners", value: stats.active, icon: Network, accent: "text-chart-1" },
    { label: "Pending invites", value: stats.pending, icon: Clock, accent: "text-chart-3" },
    { label: "Open handoffs", value: stats.openHandoffs, icon: ArrowLeftRight, accent: "text-chart-2" },
    { label: "Total partnerships", value: stats.total, icon: ShieldCheck, accent: "text-chart-4" },
  ]

  return (
    <SettingsShell activeSection="federation" isAdmin={isAdmin} hideHeader>
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      {/* Hero */}
      <div className="relative mb-8 overflow-hidden rounded-2xl border border-border bg-card">
        <GridPattern className="absolute inset-0 opacity-40" />
        <div className="absolute inset-0 bg-gradient-to-br from-primary/8 via-transparent to-transparent" />
        <div className="relative flex flex-col gap-6 p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
                <Handshake className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-balance text-2xl font-semibold tracking-tight">
                  Federation &amp; B2B
                </h1>
                <p className="mt-1 max-w-xl text-pretty text-sm leading-relaxed text-muted-foreground">
                  Securely connect with partner organizations. Both sides must consent before any
                  agent handoff, connector grant, or delegated task can flow across org boundaries.
                </p>
              </div>
            </div>
            {isAdmin ? (
              <Button onClick={() => setInviteOpen(true)} className="gap-2">
                <Plus className="h-4 w-4" />
                Invite partner
              </Button>
            ) : !authLoading ? (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Lock className="h-3.5 w-3.5" />
                Admin access required to invite partners
              </p>
            ) : null}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {statCards.map((s, i) => (
              <motion.div
                key={s.label}
                custom={i}
                initial="hidden"
                animate="show"
                variants={fadeUp}
                className="rounded-xl border border-border/60 bg-background/60 p-4 backdrop-blur-sm"
              >
                <div className="flex items-center gap-2">
                  <s.icon className={cn("h-4 w-4", s.accent)} />
                  <span className="text-xs font-medium text-muted-foreground">{s.label}</span>
                </div>
                <div className="mt-2 text-2xl font-semibold tabular-nums">
                  <AnimatedCounter value={s.value} />
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {loadError ? (
        <div className="mb-6">
          <WorkSectionErrorCard
            title="Federation data failed to load"
            message={formatUnknownError(loadError, "Check backend connectivity and migrations.")}
            error={loadError}
            onRetry={() => refreshAll()}
          />
        </div>
      ) : null}

      {/* Pending invites callout */}
      {pendingInvites.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex items-center gap-3 rounded-xl border border-chart-3/30 bg-chart-3/5 p-4"
        >
          <Inbox className="h-5 w-5 shrink-0 text-chart-3" />
          <p className="text-sm">
            <span className="font-medium">{pendingInvites.length}</span> partner{" "}
            {pendingInvites.length === 1 ? "invitation needs" : "invitations need"} your consent.
          </p>
        </motion.div>
      )}

      <div className="grid gap-8 lg:grid-cols-5">
        {/* Partners */}
        <section className="lg:col-span-3">
          <div className="mb-4 flex items-center gap-2">
            <Network className="h-4 w-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Partner organizations
            </h2>
          </div>

          <PageHeaderlessSection
            loading={loadingPartners}
            empty={partnerships.length === 0}
            emptyState={
              <FederationEmptyState
                icon={Handshake}
                visual={<TrustBoundaryVisual className="mb-3" />}
                title="No partner organizations yet"
                description="Invite a partner organization to start exchanging agent handoffs, connector grants, and delegated tasks under mutual consent."
                action={
                  isAdmin ? (
                    <Button onClick={() => setInviteOpen(true)} className="gap-2">
                      <Plus className="h-4 w-4" />
                      Invite your first partner
                    </Button>
                  ) : undefined
                }
              />
            }
          >
            <div className="grid gap-4">
              {partnerships.map((p, i) => (
                <motion.div key={p.id} custom={i} initial="hidden" animate="show" variants={fadeUp}>
                  <PartnerCard partnership={p} onAction={handlePartnerAction} />
                </motion.div>
              ))}
            </div>
          </PageHeaderlessSection>
        </section>

        {/* B2B activity tabs */}
        <section className="lg:col-span-2">
          <Tabs defaultValue="handoffs" className="space-y-4">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="handoffs">Handoffs</TabsTrigger>
              <TabsTrigger value="grants">Connector grants</TabsTrigger>
              <TabsTrigger value="tasks">Delegated tasks</TabsTrigger>
            </TabsList>

            <TabsContent value="handoffs" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Send className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Cross-org handoffs
                  </h2>
                </div>
                {isAdmin ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5"
                    onClick={() => setHandoffOpen(true)}
                    disabled={activePartnerships.length === 0}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Send handoff
                  </Button>
                ) : null}
              </div>
              <PageHeaderlessSection
                loading={loadingHandoffs}
                empty={handoffs.length === 0}
                emptyState={
                  <FederationEmptyState
                    icon={ArrowLeftRight}
                    title="No handoffs yet"
                    description="When agents pass work to a partner org, the exchange appears here as a consent-gated timeline."
                    action={
                      isAdmin && activePartnerships.length > 0 ? (
                        <Button onClick={() => setHandoffOpen(true)} className="gap-2">
                          <Plus className="h-4 w-4" />
                          Send your first handoff
                        </Button>
                      ) : undefined
                    }
                  />
                }
              >
                <HandoffTimeline
                  handoffs={handoffs}
                  currentOrgId={currentOrgId}
                  onAction={handleHandoffAction}
                />
              </PageHeaderlessSection>
            </TabsContent>

            <TabsContent value="grants" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Connector grants
                  </h2>
                </div>
                {isAdmin ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5"
                    onClick={() => setGrantOpen(true)}
                    disabled={activePartnerships.length === 0}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Propose grant
                  </Button>
                ) : null}
              </div>
              {loadingGrants ? (
                <LoadingPlaceholder />
              ) : (
                <FederationGrantList
                  grants={grants}
                  currentOrgId={currentOrgId}
                  onAction={handleGrantAction}
                  onPropose={isAdmin ? () => setGrantOpen(true) : undefined}
                  canPropose={isAdmin && activePartnerships.length > 0}
                />
              )}
            </TabsContent>

            <TabsContent value="tasks" className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Inbox className="h-4 w-4 text-muted-foreground" />
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Delegated tasks
                  </h2>
                </div>
                {isAdmin ? (
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-8 gap-1.5"
                    onClick={() => setTaskOpen(true)}
                    disabled={activePartnerships.length === 0}
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Delegate task
                  </Button>
                ) : null}
              </div>
              {loadingTasks ? (
                <LoadingPlaceholder />
              ) : (
                <FederationDelegatedTaskList
                  tasks={delegatedTasks}
                  currentOrgId={currentOrgId}
                  onAction={handleDelegatedTaskAction}
                  onCreate={isAdmin ? () => setTaskOpen(true) : undefined}
                  canCreate={isAdmin && activePartnerships.length > 0}
                />
              )}
            </TabsContent>
          </Tabs>
        </section>
      </div>

      <InvitePartnerDialog
        open={inviteOpen}
        onOpenChange={setInviteOpen}
        disabled={!isAdmin}
        onInvited={() => refreshAll()}
      />
      <CreateHandoffDialog
        open={handoffOpen}
        onOpenChange={setHandoffOpen}
        disabled={!isAdmin}
        activePartnerships={activePartnerships}
        onCreated={() => refreshAll()}
      />
      <ProposeGrantDialog
        open={grantOpen}
        onOpenChange={setGrantOpen}
        disabled={!isAdmin}
        activePartnerships={activePartnerships}
        onCreated={() => refreshAll()}
      />
      <CreateDelegatedTaskDialog
        open={taskOpen}
        onOpenChange={setTaskOpen}
        disabled={!isAdmin}
        activePartnerships={activePartnerships}
        onCreated={() => refreshAll()}
      />
    </div>
    </SettingsShell>
  )
}

function LoadingPlaceholder() {
  return (
    <div className="grid gap-4">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-24 animate-pulse rounded-xl border border-border/60 bg-muted/40" />
      ))}
    </div>
  )
}

function PageHeaderlessSection({
  loading,
  empty,
  emptyState,
  children,
}: {
  loading: boolean
  empty: boolean
  emptyState: React.ReactNode
  children: React.ReactNode
}) {
  if (loading) {
    return (
      <div className="grid gap-4">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-28 animate-pulse rounded-xl border border-border/60 bg-muted/40"
          />
        ))}
      </div>
    )
  }
  if (empty) return <>{emptyState}</>
  return <>{children}</>
}
