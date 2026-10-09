"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { settingsApi, type ApprovalRules } from "@/lib/api"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { SettingsSaveBar } from "./settings-save-bar"

type RuleKey = "customerEmailApproval" | "twoApprovalsHighRisk" | "autoApproveReadOnly" | "escalatePastDue"
type Draft = Pick<ApprovalRules, RuleKey | "sla">

export const APPROVAL_RULES: { key: RuleKey; label: string; help: string }[] = [
  {
    key: "customerEmailApproval",
    label: "Customer email waits for approval",
    help: "Agents draft messages but a person sends them.",
  },
  {
    key: "twoApprovalsHighRisk",
    label: "Two approvals for high risk actions",
    help: "Money, deletes and bulk changes need a second person.",
  },
  {
    key: "autoApproveReadOnly",
    label: "Auto approve read only lookups",
    help: "Searches and reports run without waiting.",
  },
  {
    key: "escalatePastDue",
    label: "Escalate past due requests",
    help: "Notify the next approver when the SLA runs out.",
  },
]

const SLA_OPTIONS: { id: ApprovalRules["sla"]; label: string }[] = [
  { id: "4h", label: "4 hours" },
  { id: "1h", label: "1 hour" },
  { id: "1bd", label: "1 business day" },
]

const pickDraft = (rules: ApprovalRules | undefined): Draft => ({
  customerEmailApproval: rules?.customerEmailApproval ?? true,
  twoApprovalsHighRisk: rules?.twoApprovalsHighRisk ?? false,
  autoApproveReadOnly: rules?.autoApproveReadOnly ?? false,
  escalatePastDue: rules?.escalatePastDue ?? false,
  sla: rules?.sla ?? "4h",
})

/** Settings > Admin > Human in the loop (v5): org-wide approval rules and the decision SLA. */
export function ApprovalRulesSettings() {
  const { data, error, isLoading, mutate } = useSWR<{ rules: ApprovalRules }>("/api/settings/approval-rules", apiFetcher, {
    revalidateOnFocus: false,
  })
  const baseline = useMemo(() => pickDraft(data?.rules), [data?.rules])
  const [draft, setDraft] = useState<Draft>(baseline)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  useEffect(() => setDraft(baseline), [baseline])
  const dirty = (Object.keys(baseline) as (keyof Draft)[]).some((key) => draft[key] !== baseline[key])

  if (isLoading && !data) {
    return (
      <section aria-label="Approval rules" className="st-card" aria-busy="true">
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
  if (error || !data?.rules) {
    return (
      <div role="alert" className="st-card st-row">
        <div className="st-what">
          <b>Could not load the approval rules</b>
          <span>Try again before making changes.</span>
        </div>
        <button type="button" className="st-btn" onClick={() => void mutate()}>
          Retry
        </button>
      </div>
    )
  }

  async function save() {
    setSaving(true)
    setSaveError(null)
    try {
      const result = await settingsApi.updateApprovalRules(draft)
      await mutate(result, { revalidate: false })
      setSavedAt(Date.now())
    } catch (failure) {
      setSaveError(failure instanceof Error ? failure.message : "Could not save the approval rules")
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <section aria-label="Approval rules" className="st-card">
        {APPROVAL_RULES.map((rule) => {
          const on = draft[rule.key]
          return (
            <div key={rule.key} className="st-row tight">
              <div className="st-what">
                <b>{rule.label}</b>
                <span>{rule.help}</span>
              </div>
              <button
                type="button"
                role="switch"
                className="st-switch"
                aria-checked={on}
                aria-label={rule.label}
                onClick={() => setDraft((previous) => ({ ...previous, [rule.key]: !previous[rule.key] }))}
              >
                <span />
              </button>
            </div>
          )
        })}
        <div className="st-row">
          <div className="st-what">
            <label htmlFor="decision-sla">Decision SLA</label>
            <span>After this, the request escalates to the next approver.</span>
          </div>
          <div className="st-control">
            <select
              id="decision-sla"
              className="st-select"
              value={draft.sla}
              onChange={(event) => setDraft((previous) => ({ ...previous, sla: event.target.value as Draft["sla"] }))}
            >
              {SLA_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>
      {saveError ? (
        <p role="alert" className="st-error">
          {saveError}
        </p>
      ) : null}
      <Link href="/approvals" className="st-link">
        Open the Decision queue
      </Link>
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
