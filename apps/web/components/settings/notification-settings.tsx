"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { notificationsApi, type NotificationChannelPreference } from "@/lib/api"
import { SettingsSaveBar } from "./settings-save-bar"

/** The four events and three channels from the v5 Settings design. */
export const NOTIFICATION_EVENTS: { id: string; label: string }[] = [
  { id: "approval_needed", label: "A request is waiting on you" },
  { id: "run_failed", label: "A run failed" },
  { id: "source_attention", label: "A source needs attention" },
  { id: "weekly_summary", label: "Weekly summary" },
]

const CHANNELS: { key: keyof NotificationChannelPreference; label: string }[] = [
  { key: "email_enabled", label: "Email" },
  { key: "slack_enabled", label: "Slack" },
  { key: "bell_enabled", label: "In app" },
]

type Matrix = Record<string, NotificationChannelPreference>

function pick(source: Matrix | undefined): Matrix {
  const out: Matrix = {}
  for (const event of NOTIFICATION_EVENTS) {
    const row = source?.[event.id]
    out[event.id] = {
      bell_enabled: Boolean(row?.bell_enabled),
      email_enabled: Boolean(row?.email_enabled),
      slack_enabled: Boolean(row?.slack_enabled),
    }
  }
  return out
}

const same = (a: Matrix, b: Matrix) =>
  NOTIFICATION_EVENTS.every((event) => CHANNELS.every(({ key }) => a[event.id]?.[key] === b[event.id]?.[key]))

/**
 * Settings > Workspace > Notifications (v5): where each kind of update reaches
 * you. Saved per person; Slack arrives as a direct message from the
 * workspace's Slack app, matched by email.
 */
export function NotificationSettings(_props: { isAdmin?: boolean }) {
  const { data, error, isLoading, mutate } = useSWR("notification-event-preferences", () => notificationsApi.getPreferences(), {
    revalidateOnFocus: false,
  })
  const baseline = useMemo(() => pick(data?.preferences), [data?.preferences])
  const [draft, setDraft] = useState<Matrix>(baseline)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => setDraft(baseline), [baseline])
  const dirty = !same(draft, baseline)

  if (isLoading && !data) {
    return (
      <section aria-label="Notification matrix" className="st-card" aria-busy="true">
        <p role="status" className="sr-only">
          Loading notification preferences
        </p>
        {[1, 2, 3].map((k) => (
          <div key={k} className="st-row">
            <div className="st-what">
              <span className="st-skel-a" />
              <span className="st-skel-b" />
            </div>
            <div className="st-control">
              <span className="st-skel-c" />
            </div>
          </div>
        ))}
      </section>
    )
  }
  if (error || !data?.preferences) {
    return (
      <div role="alert" className="st-card st-row">
        <div className="st-what">
          <b>Could not load your notification settings</b>
          <span>Try again before making changes.</span>
        </div>
        <button type="button" className="st-btn" onClick={() => void mutate()}>
          Retry
        </button>
      </div>
    )
  }

  const flip = (eventId: string, key: keyof NotificationChannelPreference) => {
    setDraft((previous) => ({ ...previous, [eventId]: { ...previous[eventId], [key]: !previous[eventId]?.[key] } }))
    setSaveError(null)
  }

  async function save() {
    setSaving(true)
    setSaveError(null)
    try {
      const result = await notificationsApi.updatePreferences(draft)
      await mutate(result.preferences ? { preferences: result.preferences } : undefined, {
        revalidate: !result.preferences,
      })
      setSavedAt(Date.now())
    } catch (failure) {
      setSaveError(failure instanceof Error ? failure.message : "Could not save your notification settings")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <section aria-label="Notification matrix" className="st-card">
        <div className="st-matrix-row head">
          <span>Event</span>
          {CHANNELS.map((channel) => (
            <span key={channel.key} className="c">
              {channel.label}
            </span>
          ))}
        </div>
        {NOTIFICATION_EVENTS.map((event) => (
          <div key={event.id} className="st-matrix-row">
            <span>{event.label}</span>
            {CHANNELS.map((channel) => (
              <span key={channel.key} className="c">
                <input
                  type="checkbox"
                  aria-label={`${event.label} by ${channel.label}`}
                  checked={Boolean(draft[event.id]?.[channel.key])}
                  onChange={() => flip(event.id, channel.key)}
                />
              </span>
            ))}
          </div>
        ))}
      </section>
      <p className="st-note">
        Slack messages come from your workspace&apos;s Slack app. <Link href="/connectors">Manage the Slack connection</Link>
      </p>
      {saveError ? (
        <p role="alert" className="st-error">
          {saveError}
        </p>
      ) : null}
      <SettingsSaveBar
        dirty={dirty}
        saving={saving}
        savedAt={savedAt}
        onDiscard={() => setDraft(baseline)}
        onSave={() => void save()}
      />
    </>
  )
}
