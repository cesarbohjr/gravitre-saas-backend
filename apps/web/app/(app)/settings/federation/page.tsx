"use client"

/**
 * Federation and B2B (design p17): partner organizations under mutual
 * consent, plus handoffs, connector grants and delegated tasks with them.
 * Every list and count comes from /api/federation.
 */
import { Suspense, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { toast } from "@/components/agents/overlays/toast"
import {
  ArrowLeftRight,
  Handshake,
  Inbox,
  Lock,
  Network,
  Plug,
  Plus,
  Send,
  ClipboardList,
  Users,
} from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { SettingsShell } from "@/components/settings/settings-shell"
import { SetError, SetIco, SetNote, SetSkeleton, SetStat, SetTabs } from "@/components/settings/settings-kit"
import { FederationConsentDiagram } from "@/components/settings/federation-diagram"
import { GrantList, HandoffList, PartnerList, TaskList } from "@/components/settings/federation-lists"
import "@/components/settings/federation.css"
import { federationApi } from "@/lib/api"
import { formatUnknownError } from "@/lib/fetcher"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { useSettingsSectionNav } from "@/lib/settings-nav"
import { getSelectedOrgFromStorage } from "@/lib/org-context"
import type { FederationConnectorGrant, FederationDelegatedTask, FederationHandoff } from "@/types/api"
import {
  FEDERATION_TABS,
  awaitsOurConsent,
  federationStats,
  type FederationPartnershipRow,
  type FederationTab,
} from "@/lib/settings-api/federation"
import { InvitePartnerDialog } from "@/components/federation/invite-partner-dialog"
import { CreateHandoffDialog } from "@/components/federation/create-handoff-dialog"
import { ProposeGrantDialog } from "@/components/federation/propose-grant-dialog"
import { CreateDelegatedTaskDialog } from "@/components/federation/create-delegated-task-dialog"

const TAB_ICONS: Record<FederationTab, typeof Send> = {
  handoffs: ArrowLeftRight,
  grants: Plug,
  tasks: ClipboardList,
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
  const { loading: authLoading } = useAuth()
  const { isAdmin, showAdmin } = useOrgAdmin()
  const onSectionChange = useSettingsSectionNav("federation")
  const currentOrgId = getSelectedOrgFromStorage()?.id
  const [inviteOpen, setInviteOpen] = useState(false)
  const [handoffOpen, setHandoffOpen] = useState(false)
  const [grantOpen, setGrantOpen] = useState(false)
  const [taskOpen, setTaskOpen] = useState(false)
  const [activity, setActivity] = useState<FederationTab>("handoffs")

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
    () => (partnershipsData?.partnerships ?? []) as FederationPartnershipRow[],
    [partnershipsData],
  )
  const handoffs = useMemo(() => handoffsData?.handoffs ?? [], [handoffsData])
  const grants = useMemo(() => grantsData?.grants ?? [], [grantsData])
  const delegatedTasks = useMemo(() => tasksData?.tasks ?? [], [tasksData])
  const stats = useMemo(() => federationStats(partnerships, handoffs), [partnerships, handoffs])
  const pendingInvites = useMemo(
    () => partnerships.filter((p) => awaitsOurConsent(p, currentOrgId)),
    [partnerships, currentOrgId],
  )
  const activePartnerships = useMemo(() => partnerships.filter((p) => p.status === "active"), [partnerships])
  const hasPartner = activePartnerships.length > 0
  const statsLoading = (loadingPartners && !partnershipsData) || (loadingHandoffs && !handoffsData)

  async function refreshAll() {
    await Promise.all([mutatePartners(), mutateHandoffs(), mutateGrants(), mutateTasks()])
  }

  async function handlePartnerAction(action: "accept" | "reject" | "revoke", partnership: FederationPartnershipRow) {
    try {
      if (action === "accept") await federationApi.acceptPartnership(partnership.id)
      if (action === "reject") await federationApi.rejectPartnership(partnership.id)
      if (action === "revoke") await federationApi.revokePartnership(partnership.id)
      toast.success(
        action === "accept" ? "Partnership activated" : action === "reject" ? "Invitation declined" : "Partnership revoked",
      )
      await refreshAll()
    } catch (err) {
      toast.error("Action failed", { description: err instanceof Error ? err.message : "Please try again." })
    }
  }

  async function handleHandoffAction(action: "accept" | "reject", handoff: FederationHandoff) {
    try {
      if (action === "accept") await federationApi.acceptHandoff(handoff.id)
      if (action === "reject") await federationApi.rejectHandoff(handoff.id)
      toast.success(action === "accept" ? "Handoff accepted" : "Handoff declined")
      await mutateHandoffs()
    } catch (err) {
      toast.error("Action failed", { description: err instanceof Error ? err.message : "Please try again." })
    }
  }

  async function handleGrantAction(action: "accept" | "reject" | "revoke", grant: FederationConnectorGrant) {
    try {
      if (action === "accept") await federationApi.acceptConnectorGrant(grant.id)
      if (action === "reject") await federationApi.rejectConnectorGrant(grant.id)
      if (action === "revoke") await federationApi.revokeConnectorGrant(grant.id)
      toast.success(action === "accept" ? "Grant accepted" : action === "reject" ? "Grant declined" : "Grant revoked")
      await mutateGrants()
    } catch (err) {
      toast.error("Grant action failed", { description: err instanceof Error ? err.message : "Please try again." })
    }
  }

  async function handleDelegatedTaskAction(action: "accept" | "reject", task: FederationDelegatedTask) {
    try {
      if (action === "accept") await federationApi.acceptDelegatedTask(task.id)
      if (action === "reject") await federationApi.rejectDelegatedTask(task.id)
      toast.success(action === "accept" ? "Task accepted" : "Task declined")
      await mutateTasks()
    } catch (err) {
      toast.error("Task action failed", { description: err instanceof Error ? err.message : "Please try again." })
    }
  }

  const openCreate = (tab: FederationTab) => {
    if (tab === "handoffs") setHandoffOpen(true)
    if (tab === "grants") setGrantOpen(true)
    if (tab === "tasks") setTaskOpen(true)
  }

  const tab = FEDERATION_TABS.find((t) => t.id === activity) ?? FEDERATION_TABS[0]
  const tabState = {
    handoffs: { loading: loadingHandoffs && !handoffsData, error: handoffsError, count: handoffs.length, retry: mutateHandoffs },
    grants: { loading: loadingGrants && !grantsData, error: grantsError, count: grants.length, retry: mutateGrants },
    tasks: { loading: loadingTasks && !tasksData, error: tasksError, count: delegatedTasks.length, retry: mutateTasks },
  }[activity]
  const createLabel = activity === "handoffs" ? "Send handoff" : activity === "grants" ? "Propose grant" : "Delegate task"

  const headerAction = isAdmin ? (
    <button type="button" className="gs-btn dark" onClick={() => setInviteOpen(true)}>
      <Plus size={16} aria-hidden />
      Invite partner
    </button>
  ) : !authLoading ? (
    <span className="gs-sub" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <Lock size={14} aria-hidden />
      Admin access required to invite partners
    </span>
  ) : null

  return (
    <SettingsShell activeSection="federation" isAdmin={showAdmin} onSectionChange={onSectionChange} actions={headerAction}>
      <SetNote tone="white">
        Federation is for working with another company as equals. Each side keeps its own plan and billing. If you
        resell Gravitre to clients and bill them yourself, use <Link href="/settings/clients">Clients</Link> instead.
      </SetNote>
      <div className="gs-stats">
        <SetStat icon={Handshake} tone="green" label="Active partners" value={statsLoading ? "…" : stats.active} hint="Consented" />
        <SetStat icon={Inbox} label="Pending invites" value={statsLoading ? "…" : stats.pending} hint="Awaiting consent" />
        <SetStat icon={Send} label="Open handoffs" value={statsLoading ? "…" : stats.openHandoffs} hint="In flight" />
        <SetStat icon={Users} label="Partnerships" value={statsLoading ? "…" : stats.total} hint="All time" />
      </div>

      {pendingInvites.length > 0 ? (
        <SetNote tone="amber" icon={Inbox}>
          <strong>{pendingInvites.length}</strong> partner{" "}
          {pendingInvites.length === 1 ? "invitation needs" : "invitations need"} your consent.
        </SetNote>
      ) : null}

      <div className="fd-row">
        <section className="gs-card fd-partners" aria-label="Partner organizations">
          {loadingPartners && !partnershipsData ? (
            <>
              <div style={{ padding: "16px 20px 0" }}>
                <PartnersTitle />
              </div>
              <SetSkeleton rows={3} label="Loading partners" />
            </>
          ) : partnershipsError && !partnershipsData ? (
            <>
              <div style={{ padding: "16px 20px 0" }}>
                <PartnersTitle />
              </div>
              <SetError
                message={formatUnknownError(partnershipsError, "Federation data failed to load.")}
                onRetry={() => void refreshAll()}
              />
            </>
          ) : partnerships.length === 0 ? (
            <div className="fd-partners-empty">
              <PartnersTitle />
              <FederationConsentDiagram />
              <div>
                <h4>No partner organizations yet</h4>
                <p>
                  Invite a partner to exchange agent handoffs, connector grants and delegated tasks. Nothing moves until
                  both sides agree.
                </p>
              </div>
              {isAdmin ? (
                <button type="button" className="gs-btn green sm" onClick={() => setInviteOpen(true)}>
                  Invite your first partner
                </button>
              ) : null}
            </div>
          ) : (
            <>
              <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--gs-line)" }}>
                <PartnersTitle />
              </div>
              <PartnerList
                partnerships={partnerships}
                viewerOrgId={currentOrgId}
                isAdmin={isAdmin}
                onAction={handlePartnerAction}
              />
            </>
          )}
        </section>

        <section className="gs-card clip fd-activity" aria-label="Federation activity">
          <div className="fd-tabbar">
            <SetTabs<FederationTab>
              mode="tabs"
              label="Exchange type"
              value={activity}
              onChange={setActivity}
              options={FEDERATION_TABS.map((t) => ({ id: t.id, label: t.label }))}
            />
          </div>
          <div role="tabpanel" aria-label={tab.label} style={{ display: "flex", flexDirection: "column", flex: 1 }}>
            {tabState.loading ? (
              <SetSkeleton rows={3} label={`Loading ${tab.label.toLowerCase()}`} />
            ) : tabState.error && tabState.count === 0 ? (
              <SetError
                message={formatUnknownError(tabState.error, `Could not load ${tab.label.toLowerCase()}.`)}
                onRetry={() => void tabState.retry()}
              />
            ) : tabState.count === 0 ? (
              <div className="fd-tab-empty">
                <SetIco icon={TAB_ICONS[activity]} tone="mute" size="lg" />
                <div style={{ fontWeight: 600 }}>{tab.emptyTitle}</div>
                <div className="d">{tab.emptyText}</div>
                <button
                  type="button"
                  className="gs-btn line sm"
                  disabled={!isAdmin || !hasPartner}
                  title={!hasPartner ? "Add a partner first" : !isAdmin ? "Admin access required" : undefined}
                  onClick={() => openCreate(activity)}
                >
                  {tab.cta}
                </button>
                {!hasPartner ? <span className="gs-sub">Add a partner first</span> : null}
              </div>
            ) : (
              <>
                <div className="fd-tab-head">
                  <span>
                    {tabState.count} {tab.label.toLowerCase()}
                  </span>
                  {isAdmin ? (
                    <button
                      type="button"
                      className="gs-btn line sm"
                      disabled={!hasPartner}
                      title={!hasPartner ? "Add a partner first" : undefined}
                      onClick={() => openCreate(activity)}
                    >
                      <Plus size={15} aria-hidden />
                      {createLabel}
                    </button>
                  ) : null}
                </div>
                {activity === "handoffs" ? (
                  <HandoffList handoffs={handoffs} viewerOrgId={currentOrgId} isAdmin={isAdmin} onAction={handleHandoffAction} />
                ) : activity === "grants" ? (
                  <GrantList grants={grants} viewerOrgId={currentOrgId} isAdmin={isAdmin} onAction={handleGrantAction} />
                ) : (
                  <TaskList
                    tasks={delegatedTasks}
                    viewerOrgId={currentOrgId}
                    isAdmin={isAdmin}
                    onAction={handleDelegatedTaskAction}
                  />
                )}
              </>
            )}
          </div>
        </section>
      </div>

      <InvitePartnerDialog open={inviteOpen} onOpenChange={setInviteOpen} disabled={!isAdmin} onInvited={() => refreshAll()} />
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
    </SettingsShell>
  )
}

function PartnersTitle() {
  return (
    <div className="fd-card-title">
      <Network size={18} aria-hidden />
      <h3>Partner organizations</h3>
    </div>
  )
}
