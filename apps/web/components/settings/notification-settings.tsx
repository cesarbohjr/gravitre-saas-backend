"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Bell, Mail, MessageSquare, Moon, RotateCcw, TriangleAlert, Check } from "lucide-react"
import { connectorsApi } from "@/lib/api"
import {
  CHANNELS,
  CONNECTORS_KEY,
  DEFAULT_QUIET,
  FALLBACK_DEFAULTS,
  HOURS,
  NOTIFICATION_GROUPS,
  PREFERENCES_KEY,
  browserTimeZone,
  notificationPrefsApi,
  pickMatrix,
  sameMatrix,
  sameQuiet,
  slackConnected,
  timeZoneLabel,
  type Channel,
  type Matrix,
  type QuietHours,
} from "@/lib/settings-api/notifications"
import { SetError, SetHeader, SetIco, SetSkeleton, SetSwitch } from "./settings-kit"
import { SettingsSaveBar } from "./settings-save-bar"
import "./notifications-settings.css"


const CHANNEL_ICONS = { email_enabled: Mail, slack_enabled: MessageSquare, bell_enabled: Bell } as const

/** Hour options plus the saved value when it is not on the hour. */
function hourOptions(value: string): string[] {
  return HOURS.includes(value) ? HOURS : [...HOURS, value].sort()
}

/**
 * Settings > Workspace > Notifications (design p11): where each kind of
 * update reaches you, and quiet hours. Saved per person through
 * /api/notifications/preferences; Slack arrives as a direct message from the
 * workspace's Slack app, matched by email, so Slack switches wait for a
 * connected Slack app.
 */
export function NotificationSettings(_props: { isAdmin?: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(PREFERENCES_KEY, () => notificationPrefsApi.get(), {
    revalidateOnFocus: false,
  })
  const connectors = useSWR(CONNECTORS_KEY, () => connectorsApi.list(), { revalidateOnFocus: false })
  const zone = useMemo(() => browserTimeZone(), [])

  const baseline = useMemo(() => pickMatrix(data?.preferences), [data?.preferences])
  const baselineQuiet = useMemo<QuietHours>(
    () => ({ ...DEFAULT_QUIET, ...(data?.quietHours ?? {}), timezone: zone }),
    [data?.quietHours, zone],
  )
  const defaults = useMemo(() => pickMatrix(data?.defaults ?? FALLBACK_DEFAULTS), [data?.defaults])

  const [draft, setDraft] = useState<Matrix>(baseline)
  const [quiet, setQuiet] = useState<QuietHours>(baselineQuiet)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => setDraft(baseline), [baseline])
  useEffect(() => setQuiet(baselineQuiet), [baselineQuiet])

  const dirty = !sameMatrix(draft, baseline) || !sameQuiet(quiet, baselineQuiet)
  const slackKnown = !connectors.isLoading && !connectors.error && Boolean(connectors.data)
  const slackOn = slackKnown && slackConnected(connectors.data?.connectors)
  // Hold Slack switches only when we know Slack is not connected.
  const slackHeld = connectors.isLoading || (slackKnown && !slackOn)

  const header = (
    <SetHeader
      crumb="Settings / Workspace"
      title="Notifications"
      description="Choose where each kind of update reaches you. Urgent things default to more places, digests to fewer."
      actions={
        <button
          type="button"
          className="gs-btn line sm"
          disabled={!data?.preferences || sameMatrix(draft, defaults)}
          onClick={() => {
            setDraft(defaults)
            setSaveError(null)
          }}
        >
          <RotateCcw size={15} aria-hidden />
          Reset to defaults
        </button>
      }
    />
  )

  if (isLoading && !data) {
    return (
      <>
        {header}
        <section aria-label="Notification matrix" className="gs-card" aria-busy="true">
          <SetSkeleton rows={5} label="Loading notification preferences" />
        </section>
      </>
    )
  }
  if (error || !data?.preferences) {
    return (
      <>
        {header}
        <section className="gs-card">
          <SetError message="Could not load your notification settings. Try again before making changes." onRetry={() => void mutate()} />
        </section>
      </>
    )
  }

  const flip = (eventId: string, key: Channel) => {
    setDraft((previous) => ({ ...previous, [eventId]: { ...previous[eventId], [key]: !previous[eventId]?.[key] } }))
    setSaveError(null)
  }

  async function save() {
    setSaving(true)
    setSaveError(null)
    try {
      const result = await notificationPrefsApi.save(draft, { ...quiet, timezone: zone })
      await mutate(
        result.preferences ? { ...data!, preferences: result.preferences, quietHours: result.quietHours ?? quiet } : undefined,
        { revalidate: !result.preferences },
      )
      setSavedAt(Date.now())
    } catch (failure) {
      setSaveError(failure instanceof Error ? failure.message : "Could not save your notification settings")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      {header}
      <section aria-label="Notification matrix" className="gs-card clip">
        <div className="notifications-scroll">
          <div className="notifications-matrix" role="table" aria-label="Where each update reaches you">
            <div className="gs-tr head" role="row">
              <div className="gs-th" role="columnheader">
                Event
              </div>
              {CHANNELS.map((channel) => {
                const Icon = CHANNEL_ICONS[channel.key]
                return (
                  <div key={channel.key} className="gs-th c" role="columnheader">
                    <Icon size={14} aria-hidden />
                    {channel.label}
                  </div>
                )
              })}
            </div>
            {NOTIFICATION_GROUPS.map((group) => (
              <div key={group.label} role="rowgroup" aria-label={group.label}>
                <div className="notifications-group gs-mono" role="presentation">
                  {group.label}
                </div>
                {group.rows.map((event) => (
                  <div key={event.id} className="gs-tr notifications-row" role="row">
                    <div className="notifications-event" role="rowheader">
                      <span className={`gs-dot ${event.dot}`} aria-hidden />
                      <div style={{ minWidth: 0 }}>
                        <b>{event.label}</b>
                        <span className="h">{event.hint}</span>
                      </div>
                    </div>
                    {CHANNELS.map((channel) => (
                      <div key={channel.key} className="notifications-cell" role="cell">
                        <SetSwitch
                          label={`${event.label} ${channel.aria}`}
                          checked={Boolean(draft[event.id]?.[channel.key])}
                          disabled={saving || (channel.key === "slack_enabled" && slackHeld)}
                          onChange={() => flip(event.id, channel.key)}
                        />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="notifications-cards">
        <section className="gs-card notifications-card" aria-label="Quiet hours">
          <div className="top">
            <SetIco icon={Moon} tone="mute" />
            <div>
              <b>Quiet hours</b>
              <span>Hold email and Slack, except urgent approvals. The inbox keeps everything.</span>
            </div>
            <SetSwitch
              label="Quiet hours"
              checked={quiet.enabled}
              disabled={saving}
              onChange={(next) => setQuiet((q) => ({ ...q, enabled: next }))}
            />
          </div>
          {quiet.enabled ? (
            <div className="notifications-quiet">
              From
              <select
                className="gs-select"
                aria-label="Quiet from"
                value={quiet.from}
                disabled={saving}
                onChange={(event) => setQuiet((q) => ({ ...q, from: event.target.value }))}
              >
                {hourOptions(quiet.from).map((hour) => (
                  <option key={hour} value={hour}>
                    {hour}
                  </option>
                ))}
              </select>
              to
              <select
                className="gs-select"
                aria-label="Quiet to"
                value={quiet.to}
                disabled={saving}
                onChange={(event) => setQuiet((q) => ({ ...q, to: event.target.value }))}
              >
                {hourOptions(quiet.to).map((hour) => (
                  <option key={hour} value={hour}>
                    {hour}
                  </option>
                ))}
              </select>
              <span title={zone}>{timeZoneLabel(zone)}</span>
            </div>
          ) : null}
        </section>

        <section className="gs-card notifications-card" aria-label="Slack connection" aria-live="polite">
          {connectors.isLoading ? (
            <SetSkeleton rows={2} label="Checking the Slack connection" />
          ) : connectors.error ? (
            <SetError message="Could not check the Slack connection." onRetry={() => void connectors.mutate()} />
          ) : slackOn ? (
            <>
              <div className="top">
                <SetIco icon={Check} />
                <div>
                  <b>Slack is connected</b>
                  <span>Slack updates arrive as direct messages from your workspace&apos;s Slack app.</span>
                </div>
              </div>
              <Link href="/connectors" className="gs-btn line sm">
                Manage connection
              </Link>
            </>
          ) : (
            <>
              <div className="top">
                <SetIco icon={TriangleAlert} tone="warn" />
                <div>
                  <b>Slack is not connected</b>
                  <span>Slack switches stay on hold until it is</span>
                </div>
              </div>
              <Link href="/connectors" className="gs-btn line sm">
                Connect to Slack
              </Link>
            </>
          )}
        </section>
      </div>

      {saveError ? (
        <p role="alert" className="gs-note red">
          {saveError}
        </p>
      ) : null}
      <SettingsSaveBar
        dirty={dirty}
        saving={saving}
        savedAt={savedAt}
        onDiscard={() => {
          setDraft(baseline)
          setQuiet(baselineQuiet)
          setSaveError(null)
        }}
        onSave={() => void save()}
      />
    </>
  )
}
