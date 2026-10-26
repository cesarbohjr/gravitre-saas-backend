"use client"

import Link from "next/link"
import { useState } from "react"
import useSWR from "swr"
import { mlAdminApi, type TrainingPermission } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { getQuickOrgId } from "@/lib/org-context"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"

/** Only real backend detections can open a prompt. No training begins on close. */
export function TrainingPermissionDialog({ showList = true }: { showList?: boolean } = {}) {
  const { isAdmin } = useOrgAdmin()
  const orgId = typeof window === "undefined" ? null : getQuickOrgId()
  const { data, error, mutate } = useSWR(
    isAdmin && orgId ? ["ml/training-permissions", orgId] : null,
    () => mlAdminApi.trainingPermissions(),
    { refreshInterval: 60000, revalidateOnFocus: false },
  )
  const [dismissed, setDismissed] = useState<string[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const models = isAdmin ? (data?.models ?? []).filter((model) => model.permission_visible !== false) : []
  const detected = models.find((model) => model.candidate_data_detected && model.consent_state === "pending"
    && !dismissed.includes(`${orgId}:${model.model_name}:${model.scope_digest}`))
  const current = selected ? models.find((model) => model.model_name === selected) : detected

  function close() {
    if (current) setDismissed((items) => [...items, `${orgId}:${current.model_name}:${current.scope_digest}`])
    setSelected(null)
    setSaveError(null)
  }

  async function update(model: TrainingPermission, state: "approved" | "paused" | "revoked" | "deferred") {
    if (!isAdmin || pending || getQuickOrgId() !== orgId) return
    setPending(true)
    setSaveError(null)
    try {
      await mlAdminApi.updateTrainingPermission(model.model_name, state, model.scope_digest)
      setDismissed((items) => [...items, `${orgId}:${model.model_name}:${model.scope_digest}`])
      setSelected(null)
      await mutate()
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Permission was not saved. Training remains subject to its last saved permission.")
    } finally { setPending(false) }
  }

  if (!isAdmin) return null
  const dialog = (
      <Dialog open={Boolean(current)} onOpenChange={(open) => { if (!open && !pending) close() }}>
        <DialogContent className="sm:max-w-xl max-h-[85dvh] overflow-y-auto" showCloseButton={!pending}>
          {current ? <>
            <DialogHeader>
              <DialogTitle>{current.processing_kind && current.processing_kind !== "training" ? "Provider and privacy permission" : current.consent_state === "pending" ? "Data detected for learning" : "Training permission"}</DialogTitle>
              <DialogDescription>
                {current.processing_kind && current.processing_kind !== "training"
                  ? `Review permission to ${current.what.toLowerCase()}. This permission does not start execution or grant permission to publish or send anything.`
                  : current.candidate_data_detected
                    ? `Gravitre has detected data for training the ${current.what} model. Training will begin after your approval, if data validation passes.`
                    : `Review permission for the ${current.what} model. Training stays dormant until eligible data is available.`}
              </DialogDescription>
            </DialogHeader>
            <dl className="space-y-3 text-sm">
              {[["What", current.what], ["Why", current.why], ["Data", current.data], ["When", current.when],
                ["Where", current.where], ["Security", current.security], ["Controls", current.controls]].map(([label, value]) => (
                <div key={label}><dt className="font-medium">{label}</dt><dd className="mt-1 text-muted-foreground">{value}</dd></div>
              ))}
            </dl>
            <p className="text-xs text-muted-foreground">{current.eligibility_note} Approval does not guarantee promotion or improved results.</p>
            <p className="text-xs">{current.sharing_scope === "cross_tenant_private_updates" ? "Security scope: explicit privacy-protected cross-tenant updates under the displayed audited program." : "Security scope: this organization only, including external provider processing only where disclosed above."} Changing access or retention requires your organization’s existing security settings.</p>
            {saveError ? <p role="alert" className="text-sm text-destructive">{saveError}</p> : null}
            <Link href="/trust-safety?tab=security" className="text-sm underline">Open organization security settings</Link>
            <div className="flex flex-wrap gap-2">
              <Button disabled={pending || current.consent_state === "approved"} onClick={() => update(current, "approved")}>{current.processing_kind && current.processing_kind !== "training" ? current.consent_state === "paused" ? "Resume permission" : "Approve stated purpose" : current.consent_state === "paused" ? "Resume automatic training" : "Approve automatic training"}</Button>
              {current.consent_state === "approved" ? <Button variant="outline" disabled={pending} onClick={() => update(current, "paused")}>Pause</Button> : null}
              {current.consent_state !== "pending" && current.consent_state !== "revoked" ? <Button variant="outline" disabled={pending} onClick={() => update(current, "revoked")}>Revoke permission</Button> : null}
              {current.consent_state === "pending" ? <Button variant="ghost" disabled={pending} onClick={() => update(current, "deferred")}>Not now</Button> : <Button variant="ghost" disabled={pending} onClick={close}>Close</Button>}
            </div>
          </> : null}
        </DialogContent>
      </Dialog>
  )
  // The prompt opens on any Intelligence page when data is detected; the list
  // of permissions lives on Models, under "Show technical details".
  if (!showList) return dialog
  return (
    <section aria-label="Training permissions" className="rounded-[var(--g-radius-panel)] border border-[color:var(--g-border-subtle)] bg-[color:var(--g-surface-1)] p-4">
      <details>
        <summary className="cursor-pointer text-sm font-medium">Training permissions</summary>
        <p className="mt-2 text-sm text-muted-foreground">Review detected data, approve automatic training, or pause and revoke permission. Provider processing and federation require their own explicit purpose-specific permissions.</p>
        {error ? <p role="alert">Unable to verify training permissions. No new permission has been granted.</p> : null}
        <div className="mt-3 space-y-2">
          {models.map((model) => (
            <div key={model.model_name} className="flex items-center justify-between gap-3 text-sm">
              <span className="capitalize">{model.what} · {model.consent_state}</span>
              <Button variant="outline" size="sm" onClick={() => { setSaveError(null); setSelected(model.model_name) }}>Review</Button>
            </div>
          ))}
        </div>
      </details>
      {dialog}
    </section>
  )
}
