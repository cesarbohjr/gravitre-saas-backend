"use client"

/** Presentational cards for Billing and plan (design p16). Handlers live in the page. */
import { useState, type ReactNode } from "react"
import Link from "next/link"
import { Activity, CreditCard, Crown, Download, Loader2, TrendingUp } from "lucide-react"
import {
  cardExpiry,
  cardTitle,
  usageBarWidth,
  type CardOnFile,
  type InvoiceRow,
  type UsageTile,
} from "@/lib/settings-api/billing"
import { pageSlice } from "@/lib/settings-api/lite"
import { SetArt, SetError, SetIco, SetPager, SetPill, SetSkeleton, SetSwitch } from "./settings-kit"
import "./billing.css"
import { BillingArt } from "@/components/dashboard/art/dashboard-art"

export function BillingPlanCard({
  loading,
  error,
  onRetry,
  title,
  status,
  subline,
  price,
  showAutoRenew,
  autoRenewOn,
  autoRenewText,
  autoRenewDisabled,
  autoRenewHint,
  onAutoRenew,
  canUpgrade,
  onUpgrade,
  canCancel,
  onCancel,
}: {
  loading: boolean
  error: boolean
  onRetry: () => void
  title: string
  status: { label: string; tone: "green" | "blue" | "amber" | "neutral"; live: boolean }
  subline: string | null
  price: { amount: string; period: string | null } | null
  showAutoRenew: boolean
  autoRenewOn: boolean
  autoRenewText: string
  autoRenewDisabled: boolean
  autoRenewHint?: string | null
  onAutoRenew: (next: boolean) => void
  canUpgrade: boolean
  onUpgrade: () => void
  canCancel: boolean
  onCancel: () => void
}) {
  return (
    <section className="gs-card round clip" aria-label="Your plan">
      <div className="bl-hero">
        <div className="bl-hero-main">
          <div className="bl-plan">
            <span className="bl-plan-ico" aria-hidden>
              <Crown size={24} aria-hidden />
            </span>
            <div style={{ minWidth: 0 }}>
              <div className="bl-plan-title">
                <h2>{title}</h2>
                <SetPill tone={status.tone} dot live={status.live}>
                  {status.label}
                </SetPill>
              </div>
              {subline ? <div className="bl-plan-sub">{subline}</div> : null}
            </div>
          </div>
          {error ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
              <span className="gs-sub">Could not load billing status.</span>
              <button type="button" className="gs-btn line sm" onClick={onRetry}>
                Try again
              </button>
            </div>
          ) : showAutoRenew ? (
            <div className="bl-renew">
              <div>
                <b>Auto renew</b>
                <span>{autoRenewText}</span>
                {autoRenewHint ? <span>{autoRenewHint}</span> : null}
              </div>
              <SetSwitch
                checked={autoRenewOn}
                onChange={onAutoRenew}
                label="Auto renew"
                disabled={autoRenewDisabled}
              />
            </div>
          ) : null}
        </div>
        <div className="bl-hero-side">
          <div className="bl-price" aria-live="polite">
            {loading && !price ? (
              <span className="gs-skel" style={{ display: "inline-block", width: 120, height: 40 }} aria-label="Loading price" />
            ) : price ? (
              <>
                <b>{price.amount}</b>
                {price.period ? <span> {price.period}</span> : null}
              </>
            ) : null}
          </div>
          <div className="bl-actions">
            <button type="button" className="gs-btn dark sm" disabled={!canUpgrade} onClick={onUpgrade}>
              <TrendingUp size={15} aria-hidden />
              Upgrade plan
            </button>
            <button type="button" className="gs-btn text sm" disabled={!canCancel} onClick={onCancel}>
              Cancel subscription
            </button>
          </div>
        </div>
      </div>
    </section>
  )
}

export function BillingUsageCard({
  loading,
  error,
  onRetry,
  periodEnd,
  tiles,
  children,
}: {
  loading: boolean
  error: boolean
  onRetry: () => void
  periodEnd: string | null
  tiles: UsageTile[]
  children?: ReactNode
}) {
  return (
    <section className="gs-card clip" aria-label="Current usage">
      <div className="bl-card-head">
        <div className="t">
          <Activity size={18} aria-hidden />
          <h3>Current usage</h3>
        </div>
        <span className="m">{periodEnd ? `Period ends ${periodEnd}` : "Current billing period"}</span>
      </div>
      {loading && tiles.length === 0 ? (
        <SetSkeleton rows={3} label="Loading usage" />
      ) : error && tiles.length === 0 ? (
        <SetError message="Could not load usage for this period." onRetry={onRetry} />
      ) : tiles.length === 0 ? (
        <div className="gs-empty">
          <b>No usage yet</b>
          <p>Usage for this billing period shows here once your plan is confirmed.</p>
        </div>
      ) : (
        <div className="bl-usage">
          {tiles.map((t, i) => (
            <div key={t.key} className="bl-tile">
              <div className="bl-tile-top">
                <span>{t.label}</span>
                <span className={`gs-mono${t.tone === "red" ? " bad" : t.tone === "amber" ? " warn" : ""}`}>
                  {t.pct === null ? "Metered" : `${t.pct}%`}
                </span>
              </div>
              <div className="bl-tile-val">
                <b>{t.used.toLocaleString()}</b>
                <span>{t.limit === null ? ` ${t.unit}` : ` / ${t.limit.toLocaleString()} ${t.unit}`}</span>
              </div>
              <div
                className="gs-track"
                role={t.limit === null ? undefined : "meter"}
                aria-label={t.limit === null ? undefined : `${t.label} used`}
                aria-valuemin={t.limit === null ? undefined : 0}
                aria-valuemax={t.limit ?? undefined}
                aria-valuenow={t.limit === null ? undefined : t.used}
              >
                {t.limit === null ? null : (
                  <span
                    className={t.tone === "red" ? "red" : t.tone === "amber" ? "amber" : undefined}
                    style={{ width: usageBarWidth(t), animationDelay: `${i * 100}ms` }}
                  />
                )}
              </div>
              {t.overage ? <div className="bl-tile-over">{t.overage}</div> : null}
              <div className="bl-tile-note">{t.note}</div>
            </div>
          ))}
        </div>
      )}
      {children}
    </section>
  )
}

const INVOICE_PAGE_SIZE = 10

export function BillingInvoicesCard({
  loading,
  error,
  onRetry,
  rows,
  onDownload,
  onDownloadAll,
}: {
  loading: boolean
  error: boolean
  onRetry: () => void
  rows: InvoiceRow[]
  onDownload: (row: InvoiceRow) => void
  onDownloadAll: () => void
}) {
  const [page, setPage] = useState(1)
  // Ten invoices per page; pageSlice clamps the page if the list shrinks.
  const slice = pageSlice(rows, page, INVOICE_PAGE_SIZE)
  return (
    <section className="gs-card clip bl-invoices" aria-label="Invoices">
      <div className="bl-card-head">
        <h3>Invoices</h3>
        <button type="button" className="gs-btn text sm" onClick={onDownloadAll} disabled={rows.length === 0}>
          <Download size={15} aria-hidden />
          Download all
        </button>
      </div>
      {loading && rows.length === 0 ? (
        <SetSkeleton rows={3} label="Loading invoices" />
      ) : error && rows.length === 0 ? (
        <SetError message="Could not load invoices." onRetry={onRetry} />
      ) : rows.length === 0 ? (
        <div className="gs-empty">
          <b>No invoices yet</b>
          <p>Your billing history shows here after your first payment.</p>
        </div>
      ) : (
        <div className="gs-tbl stack" style={{ ["--cols" as string]: "minmax(0,1fr) 110px 110px 60px" }}>
          {slice.rows.map((v) => (
            <div key={v.id} className="gs-row">
              <div className="gs-td">
                <div style={{ fontWeight: 500 }}>{v.label}</div>
                <div className="gs-mono s" style={{ fontSize: 12, color: "var(--gs-muted)" }}>
                  {v.number}
                </div>
              </div>
              <div className="gs-td gs-mono">{v.amount}</div>
              <div className="gs-td">
                <SetPill tone={v.tone}>{v.status}</SetPill>
              </div>
              <div className="gs-td">
                <button type="button" className="gs-pg" aria-label={`Download ${v.number}`} onClick={() => onDownload(v)}>
                  <Download size={16} aria-hidden />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      {rows.length > 0 ? (
        <SetPager
          page={slice.page}
          pageCount={slice.pageCount}
          from={slice.from}
          to={slice.to}
          total={slice.total}
          onPage={setPage}
          noun="invoices"
        />
      ) : null}
      <p className="bl-foot-note">
        Need older invoices? <Link href="/support">Contact support</Link>
      </p>
    </section>
  )
}

export function BillingPaymentCard({
  loading,
  error,
  card,
  canManage,
  busy,
  onUpdate,
  onEditAddress,
}: {
  loading: boolean
  error: boolean
  card: CardOnFile | null
  canManage: boolean
  busy: boolean
  onUpdate: () => void
  onEditAddress: () => void
}) {
  const expiry = card ? cardExpiry(card) : null
  return (
    <section className="gs-card clip bl-pay" aria-label="Payment method">
      <SetArt ratio="320 / 170"><BillingArt /></SetArt>
      <div className="bl-pay-body">
        <h3>Payment method</h3>
        {loading && !card ? (
          <span className="gs-skel" style={{ height: 58 }} aria-label="Loading payment method" />
        ) : (
          <div className="bl-cardline">
            <SetIco icon={CreditCard} tone="mute" />
            <div>
              <b>{card ? cardTitle(card) : error ? "Payment method unavailable" : "No payment method on file"}</b>
              <span>
                {card
                  ? expiry ?? "Managed securely by our payment provider"
                  : error
                    ? "Could not reach the billing service. Try again shortly."
                    : "Add one in the secure billing portal"}
              </span>
            </div>
          </div>
        )}
        <div className="bl-pay-actions">
          <button type="button" className="gs-btn line sm" disabled={!canManage || busy} onClick={onUpdate}>
            {busy ? <Loader2 size={15} className="animate-spin" aria-hidden /> : null}
            Update payment method
          </button>
          <button type="button" className="gs-btn text sm" disabled={!canManage || busy} onClick={onEditAddress}>
            Edit billing address
          </button>
        </div>
        {!canManage ? <span className="gs-sub">Admin access is required to change payment details.</span> : null}
      </div>
    </section>
  )
}
