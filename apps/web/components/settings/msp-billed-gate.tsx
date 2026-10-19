"use client"

/**
 * Settings › Billing for a workspace a partner (MSP) pays for: show who bills
 * it and hide self-checkout. The backend also refuses checkout for these
 * workspaces, so this is clarity, not the guard. Any error falls back to the
 * normal billing page.
 */
import type { ReactNode } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Building2 } from "lucide-react"
import { SetNote, SetPill } from "@/components/settings/settings-kit"
import { mspProgramApi } from "@/lib/msp-program"

const STATUS_COPY: Record<string, { tone: "green" | "amber" | "red"; label: string }> = {
  active: { tone: "green", label: "Active" },
  trialing: { tone: "amber", label: "Trial" },
  past_due: { tone: "red", label: "Payment issue at your partner" },
  cancelled: { tone: "red", label: "Cancelled" },
  canceled: { tone: "red", label: "Cancelled" },
}

export function MspBilledGate({ children }: { children: ReactNode }) {
  const { data } = useSWR("msp:program:billed-by", () => mspProgramApi.billedBy(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  })
  const billedBy = data?.billed_by
  if (!billedBy) return <>{children}</>
  const status = STATUS_COPY[billedBy.billing_status ?? ""] ?? { tone: "amber" as const, label: billedBy.billing_status ?? "Unknown" }
  return (
    <div style={{ display: "grid", gap: 16 }} data-review-surface="billing-msp-billed">
      <section className="gs-card" style={{ padding: 20, display: "grid", gap: 12 }}>
        <div className="gs-card-title" style={{ justifyContent: "space-between", flexWrap: "wrap" }}>
          <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Building2 size={18} aria-hidden />
            <h3>Billed through {billedBy.msp_name}</h3>
          </span>
          <SetPill tone={status.tone} dot>
            {status.label}
          </SetPill>
        </div>
        <div className="gs-kv">
          <div>
            <span>Plan</span>
            <strong>{billedBy.plan_name}</strong>
          </div>
          <div>
            <span>Who bills you</span>
            <strong>{billedBy.msp_name}</strong>
          </div>
        </div>
        <p className="gs-sub" style={{ margin: 0 }}>
          {billedBy.msp_name} pays Gravitre for this workspace and invoices you directly, so there are no Gravitre
          invoices or cards to manage here. To change your plan or ask about an invoice, contact {billedBy.msp_name}.
        </p>
        {billedBy.billing_status === "past_due" ? (
          <SetNote tone="red">
            {billedBy.msp_name}&apos;s payment to Gravitre didn&apos;t go through, so this workspace is paused. Let them
            know; access comes back as soon as they pay.
          </SetNote>
        ) : null}
      </section>
      <p className="gs-sub" style={{ margin: 0 }}>
        Want to pay Gravitre directly instead? The workspace owner can detach from {billedBy.msp_name} in{" "}
        <Link href="/settings/organizations" className="gs-link">
          Settings › Organizations
        </Link>
        .
      </p>
    </div>
  )
}
