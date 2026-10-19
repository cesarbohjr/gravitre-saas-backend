"use client"

/** Kit-styled federation lists (partners, handoffs, grants, delegated tasks). */
import { useState } from "react"
import { ArrowRight, Building2, Check, CheckCircle2, Clock, ClipboardList, Plug, Send, ShieldOff, X } from "lucide-react"
import type { FederationConnectorGrant, FederationDelegatedTask, FederationHandoff } from "@/types/api"
import {
  GRANT_STATUS,
  HANDOFF_STATUS,
  PARTNERSHIP_STATUS,
  TASK_STATUS,
  awaitsOurConsent,
  canRespondToHandoff,
  canRespondToTask,
  grantPermissions,
  handoffTitle,
  partnerLabel,
  statusOf,
  type FederationPartnershipRow,
} from "@/lib/settings-api/federation"
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
import { SetIco, SetPill, formatAgo, formatDay } from "./settings-kit"

type Busy = string | null

function useBusy() {
  const [busy, setBusy] = useState<Busy>(null)
  const run = async (key: string, fn: () => Promise<void>) => {
    setBusy(key)
    try {
      await fn()
    } finally {
      setBusy(null)
    }
  }
  return { busy, run }
}

export function PartnerList({
  partnerships,
  viewerOrgId,
  isAdmin,
  onAction,
}: {
  partnerships: FederationPartnershipRow[]
  viewerOrgId?: string | null
  isAdmin: boolean
  onAction: (action: "accept" | "reject" | "revoke", p: FederationPartnershipRow) => Promise<void>
}) {
  const { busy, run } = useBusy()
  const [revoking, setRevoking] = useState<FederationPartnershipRow | null>(null)
  return (
    <>
      <ul className="fd-list" aria-label="Partner organizations">
        {partnerships.map((p) => {
          const meta = statusOf(PARTNERSHIP_STATUS, p.status)
          const ours = awaitsOurConsent(p, viewerOrgId)
          const weInvited = p.invitedByOrgId === (p.currentOrgId || viewerOrgId)
          const created = formatDay(p.createdAt)
          return (
            <li key={p.id} className="fd-item gs-rise">
              <div className="fd-item-top">
                <SetIco icon={Building2} tone={p.status === "active" ? "green" : "mute"} size="sm" />
                <div className="who">
                  <b>{partnerLabel(p)}</b>
                  <span>
                    {weInvited ? "You invited this organization" : "Invited your organization"}
                    {created ? ` · ${created}` : ""}
                  </span>
                </div>
                <SetPill tone={meta.tone} dot live={p.status === "active"}>
                  {meta.label}
                </SetPill>
              </div>
              <div className="fd-meta" aria-label="Consent">
                <span className={`gs-chip fd-consent${p.initiatorConsentAt ? " done" : ""}`}>
                  {p.initiatorConsentAt ? <CheckCircle2 size={12} aria-hidden /> : <Clock size={12} aria-hidden />}
                  Initiator
                </span>
                <ArrowRight size={12} aria-hidden />
                <span className={`gs-chip fd-consent${p.partnerConsentAt ? " done" : ""}`}>
                  {p.partnerConsentAt ? <CheckCircle2 size={12} aria-hidden /> : <Clock size={12} aria-hidden />}
                  Partner
                </span>
              </div>
              {isAdmin && (ours || p.status === "active") ? (
                <div className="fd-actions">
                  {ours ? (
                    <>
                      <button
                        type="button"
                        className="gs-btn dark sm"
                        disabled={busy !== null}
                        onClick={() => void run(`${p.id}:accept`, () => onAction("accept", p))}
                      >
                        <Check size={15} aria-hidden />
                        {busy === `${p.id}:accept` ? "Accepting…" : "Accept"}
                      </button>
                      <button
                        type="button"
                        className="gs-btn line sm"
                        disabled={busy !== null}
                        onClick={() => void run(`${p.id}:reject`, () => onAction("reject", p))}
                      >
                        <X size={15} aria-hidden />
                        Decline
                      </button>
                    </>
                  ) : null}
                  {p.status === "active" ? (
                    <button type="button" className="gs-btn danger sm" disabled={busy !== null} onClick={() => setRevoking(p)}>
                      <ShieldOff size={15} aria-hidden />
                      {busy === `${p.id}:revoke` ? "Revoking…" : "Revoke access"}
                    </button>
                  ) : null}
                </div>
              ) : p.status === "pending_partner" && !ours ? (
                <span className="gs-sub">Waiting for the partner to accept your invitation.</span>
              ) : null}
            </li>
          )
        })}
      </ul>
      <AlertDialog open={revoking !== null} onOpenChange={(open) => !open && setRevoking(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke {revoking ? partnerLabel(revoking) : "this partner"}?</AlertDialogTitle>
            <AlertDialogDescription>
              Handoffs, connector grants and delegated tasks with this organization stop. You would need to invite
              them again to work together.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep partner</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const target = revoking
                setRevoking(null)
                if (target) void run(`${target.id}:revoke`, () => onAction("revoke", target))
              }}
            >
              Revoke access
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}

function RespondButtons({
  id,
  busy,
  onAccept,
  onReject,
}: {
  id: string
  busy: Busy
  onAccept: () => void
  onReject: () => void
}) {
  return (
    <div className="fd-actions">
      <button type="button" className="gs-btn line sm" disabled={busy !== null} onClick={onAccept}>
        <Check size={15} aria-hidden />
        {busy === `${id}:accept` ? "Accepting…" : "Accept"}
      </button>
      <button type="button" className="gs-btn text sm" disabled={busy !== null} onClick={onReject}>
        <X size={15} aria-hidden />
        Decline
      </button>
    </div>
  )
}

export function HandoffList({
  handoffs,
  viewerOrgId,
  isAdmin,
  onAction,
}: {
  handoffs: FederationHandoff[]
  viewerOrgId?: string | null
  isAdmin: boolean
  onAction: (action: "accept" | "reject", h: FederationHandoff) => Promise<void>
}) {
  const { busy, run } = useBusy()
  return (
    <ul className="fd-list" aria-label="Handoffs">
      {handoffs.map((h) => {
        const meta = statusOf(HANDOFF_STATUS, h.status)
        const outgoing = Boolean(viewerOrgId) && h.senderOrgId === viewerOrgId
        return (
          <li key={h.id} className="fd-item">
            <div className="fd-item-top">
              <SetIco icon={Send} tone="mute" size="xs" />
              <div className="who">
                <b>{handoffTitle(h)}</b>
                <span>
                  {outgoing ? "Sent to partner" : "Received from partner"}
                  {h.fromAgentId || h.toAgentId
                    ? ` · ${h.fromAgentId ? h.fromAgentId.slice(0, 6) : "org"} to ${h.toAgentId ? h.toAgentId.slice(0, 6) : "partner"}`
                    : ""}
                </span>
              </div>
              <SetPill tone={meta.tone} dot live={h.status === "pending_receiver"}>
                {meta.label}
              </SetPill>
            </div>
            <div className="fd-meta">{formatAgo(h.createdAt) ?? ""}</div>
            {isAdmin && canRespondToHandoff(h, viewerOrgId) ? (
              <RespondButtons
                id={h.id}
                busy={busy}
                onAccept={() => void run(`${h.id}:accept`, () => onAction("accept", h))}
                onReject={() => void run(`${h.id}:reject`, () => onAction("reject", h))}
              />
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

export function GrantList({
  grants,
  viewerOrgId,
  isAdmin,
  onAction,
}: {
  grants: FederationConnectorGrant[]
  viewerOrgId?: string | null
  isAdmin: boolean
  onAction: (action: "accept" | "reject" | "revoke", g: FederationConnectorGrant) => Promise<void>
}) {
  const { busy, run } = useBusy()
  return (
    <ul className="fd-list" aria-label="Connector grants">
      {grants.map((g) => {
        const meta = statusOf(GRANT_STATUS, g.status)
        const perms = grantPermissions(g, viewerOrgId)
        const expires = g.expiresAt ? formatAgo(g.expiresAt) : null
        const expiresFuture = g.expiresAt ? new Date(g.expiresAt).getTime() > Date.now() : false
        return (
          <li key={g.id} className="fd-item">
            <div className="fd-item-top">
              <SetIco icon={Plug} tone="mute" size="xs" />
              <div className="who">
                <b>{g.label || g.connectorId}</b>
                <span className="gs-mono">{g.connectorId}</span>
              </div>
              <SetPill tone={meta.tone}>{meta.label}</SetPill>
            </div>
            <div className="fd-meta">
              {perms.direction === "outgoing" ? "You share" : perms.direction === "incoming" ? "Shared with you" : "Grant"}
              {": "}
              {(g.allowedActions ?? []).slice(0, 4).join(", ") || "no actions"}
              {g.expiresAt
                ? expiresFuture
                  ? ` · expires ${formatDay(g.expiresAt)}`
                  : ` · expired ${expires ?? ""}`
                : ""}
            </div>
            {isAdmin && (perms.canAccept || perms.canRevoke) ? (
              <div className="fd-actions">
                {perms.canAccept ? (
                  <button
                    type="button"
                    className="gs-btn line sm"
                    disabled={busy !== null}
                    onClick={() => void run(`${g.id}:accept`, () => onAction("accept", g))}
                  >
                    <Check size={15} aria-hidden />
                    {busy === `${g.id}:accept` ? "Accepting…" : "Accept"}
                  </button>
                ) : null}
                {perms.canReject ? (
                  <button
                    type="button"
                    className="gs-btn text sm"
                    disabled={busy !== null}
                    onClick={() => void run(`${g.id}:reject`, () => onAction("reject", g))}
                  >
                    <X size={15} aria-hidden />
                    Decline
                  </button>
                ) : null}
                {perms.canRevoke ? (
                  <button
                    type="button"
                    className="gs-btn danger sm"
                    disabled={busy !== null}
                    onClick={() => void run(`${g.id}:revoke`, () => onAction("revoke", g))}
                  >
                    {busy === `${g.id}:revoke` ? "Revoking…" : "Revoke"}
                  </button>
                ) : null}
              </div>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

export function TaskList({
  tasks,
  viewerOrgId,
  isAdmin,
  onAction,
}: {
  tasks: FederationDelegatedTask[]
  viewerOrgId?: string | null
  isAdmin: boolean
  onAction: (action: "accept" | "reject", t: FederationDelegatedTask) => Promise<void>
}) {
  const { busy, run } = useBusy()
  return (
    <ul className="fd-list" aria-label="Delegated tasks">
      {tasks.map((t) => {
        const meta = statusOf(TASK_STATUS, t.status)
        const incoming = Boolean(viewerOrgId) && t.delegateOrgId === viewerOrgId
        return (
          <li key={t.id} className="fd-item">
            <div className="fd-item-top">
              <SetIco icon={ClipboardList} tone="mute" size="xs" />
              <div className="who">
                <b>{t.title}</b>
                <span>{incoming ? "Asked of your agents" : "Delegated to a partner"}</span>
              </div>
              <SetPill tone={meta.tone}>{meta.label}</SetPill>
            </div>
            {t.instructions ? <div className="gs-sub">{t.instructions}</div> : null}
            {t.createdAt ? <div className="fd-meta">{formatAgo(t.createdAt)}</div> : null}
            {isAdmin && canRespondToTask(t, viewerOrgId) ? (
              <RespondButtons
                id={t.id}
                busy={busy}
                onAccept={() => void run(`${t.id}:accept`, () => onAction("accept", t))}
                onReject={() => void run(`${t.id}:reject`, () => onAction("reject", t))}
              />
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}
