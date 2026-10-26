"use client"

/**
 * "Share this finding": send a finding to a person or channel in an app the
 * team already uses. Only apps the organization has connected appear (Slack
 * channels and people, and email to people in the organization). The message
 * always links back to the finding in Gravitre, and every share is audited.
 */
import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { toast } from "@/components/intelligence/overlays/toast"
import { intelligenceFindingsApi, type ShareFindingApp } from "@/lib/api"
import { APP_ROUTES } from "@/lib/app-routes"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

export const SHARE_OPTIONS_KEY = "intelligence/share/options"

export type ShareableFinding = {
  id: string
  title: string
  summary?: string
  /** Page in Gravitre the message links back to. */
  path: string
}

const FIELD =
  "min-h-11 w-full rounded-[var(--g-radius-field)] border border-[color:var(--g-border-default)] bg-background px-3 text-sm outline-none focus:border-[color:var(--g-brand)] disabled:cursor-not-allowed disabled:opacity-60"

function listNames(names: string[]): string {
  if (names.length <= 1) return names.join("")
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`
}

export function ShareFindingDialog({
  finding,
  onOpenChange,
}: {
  finding: ShareableFinding | null
  onOpenChange: (open: boolean) => void
}) {
  const open = finding != null
  const { data, error, isLoading, mutate } = useSWR(open ? SHARE_OPTIONS_KEY : null, () => intelligenceFindingsApi.shareOptions(), {
    revalidateOnFocus: false,
  })
  const apps = useMemo(() => data?.apps ?? [], [data])
  const [appId, setAppId] = useState<ShareFindingApp["id"] | "">("")
  const [to, setTo] = useState("")
  const [note, setNote] = useState("")
  const [sending, setSending] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  const lock = useRef(false)

  useEffect(() => {
    if (!open) return
    setTo("")
    setNote("")
    setFailure(null)
  }, [open, finding?.id])

  useEffect(() => {
    if (apps.length && !apps.some((a) => a.id === appId)) setAppId(apps[0].id)
  }, [apps, appId])

  const app = apps.find((a) => a.id === appId) ?? null
  const [kind, targetId] = to.split(":") as ["c" | "p" | "", string | undefined]
  const toLabel =
    kind === "c"
      ? app?.channels.find((c) => c.id === targetId)?.name
      : kind === "p"
        ? app?.people.find((p) => p.id === targetId)?.name
        : undefined
  const canSend = Boolean(app && toLabel && !sending)
  const unavailable = data?.unavailable ?? []

  async function send() {
    if (lock.current || !finding || !app || !targetId || !toLabel) return
    lock.current = true
    setSending(true)
    setFailure(null)
    const pending = toast.info(`Sharing finding to ${toLabel}`, {
      eyebrow: "SHARING",
      duration: Infinity,
      description: app.id === "slack" ? "Posting in Slack as Gravitre." : "Sending by email from Gravitre.",
    })
    try {
      const result = await intelligenceFindingsApi.share({
        app: app.id,
        channelId: kind === "c" ? targetId : null,
        personId: kind === "p" ? targetId : null,
        title: finding.title,
        summary: finding.summary ?? "",
        note: note.trim(),
        path: finding.path,
        findingId: finding.id,
      })
      toast.success(`Shared with ${toLabel} in ${app.name}`, {
        id: pending,
        eyebrow: "SHARED",
        duration: 6000,
        description: "The message links back to this finding in Gravitre.",
        ...(result.url ? { action: { label: "Open in Slack", onClick: () => window.open(result.url!, "_blank", "noopener") } } : {}),
      })
      onOpenChange(false)
    } catch (err) {
      toast.dismiss(pending)
      setFailure(err instanceof Error ? err.message : "The finding was not shared. Try again.")
    } finally {
      lock.current = false
      setSending(false)
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (lock.current) return
        onOpenChange(next)
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Share this finding</DialogTitle>
          <DialogDescription>Send it to a person or channel in an app your team already uses.</DialogDescription>
        </DialogHeader>
        {error ? (
          <div className="space-y-2">
            <p role="alert" className={TYPE.bodyMuted}>
              Gravitre couldn&apos;t load where you can share. Try again in a moment.
            </p>
            <Button size="sm" variant="outline" onClick={() => void mutate()}>
              Try again
            </Button>
          </div>
        ) : isLoading && !data ? (
          <p className={TYPE.bodyMuted}>Loading the apps your team uses…</p>
        ) : apps.length === 0 ? (
          <div className="space-y-2">
            <p className={TYPE.bodyMuted}>
              Connect Slack, or turn on email delivery, to share findings with your team.
            </p>
            <Button asChild size="sm" variant="outline">
              <Link href={APP_ROUTES.connectors}>Open connectors</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {finding ? (
              <div className="rounded-[var(--np-radius-md)] bg-[color:var(--g-surface-2)] px-3 py-2.5">
                <p className="text-sm font-semibold text-[color:var(--g-text-primary)]">{finding.title}</p>
                {finding.summary ? <p className={cn(TYPE.meta, "mt-0.5 line-clamp-2")}>{finding.summary}</p> : null}
              </div>
            ) : null}
            <label className="block space-y-1">
              <span className={TYPE.meta}>App</span>
              <select
                className={FIELD}
                value={appId}
                disabled={sending}
                onChange={(e) => {
                  setAppId(e.target.value as ShareFindingApp["id"])
                  setTo("")
                }}
              >
                {apps.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block space-y-1">
              <span className={TYPE.meta}>Send to</span>
              <select className={FIELD} value={to} disabled={sending || !app} onChange={(e) => setTo(e.target.value)}>
                <option value="">Choose a {app?.id === "slack" ? "channel or person" : "person"}</option>
                {app && app.channels.length > 0 ? (
                  <optgroup label="Channels">
                    {app.channels.map((c) => (
                      <option key={c.id} value={`c:${c.id}`}>
                        {c.name}
                        {c.private ? " (private)" : ""}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
                {app && app.people.length > 0 ? (
                  <optgroup label="People">
                    {app.people.map((p) => (
                      <option key={p.id} value={`p:${p.id}`}>
                        {p.name}
                      </option>
                    ))}
                  </optgroup>
                ) : null}
              </select>
            </label>
            <label className="block space-y-1">
              <span className={TYPE.meta}>Note</span>
              <textarea
                className={cn(FIELD, "min-h-[84px] py-2")}
                rows={3}
                maxLength={1000}
                value={note}
                disabled={sending}
                placeholder="Add a note for whoever picks this up (optional)"
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            {unavailable.length > 0 ? (
              <p className={TYPE.meta}>
                {listNames(unavailable)} {unavailable.length > 1 ? "aren't" : "isn't"} available, so{" "}
                {unavailable.length > 1 ? "they're" : "it's"} not shown.{" "}
                <Link href={APP_ROUTES.connectors} className="underline underline-offset-2">
                  Connect apps in Connectors
                </Link>
                .
              </p>
            ) : null}
            {failure ? (
              <p role="alert" className={cn(TYPE.meta, "text-[color:var(--g-danger,#a3333d)]")}>
                {failure}
              </p>
            ) : null}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" disabled={sending} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="default" disabled={!canSend} onClick={() => void send()}>
            {sending ? "Sharing…" : "Share"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
