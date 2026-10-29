"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { ArrowLeft, Search } from "lucide-react"
import { AppShell } from "@/components/gravitre/app-shell"
import { VendorTile } from "@/components/connectors/redesign/art"
import { StatusPill } from "@/components/connectors/redesign/hub"
import "@/components/workspace/workspace.css"
import "@/components/connectors/redesign/connectors.css"
import { marketplaceApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import type { MarketplaceFederatedConnectorSummary } from "@/types/api"

type Filter = "all" | "certified" | "free" | "paid"

/** Cover art per kind of work, from the marketplace illustration set. */
const ART_BY_TOPIC: Array<[RegExp, string, string]> = [
  [/market|campaign|seo|\bads?\b|social/i, "market-campaigns", "A megaphone sending out sound waves and a paper plane"],
  [/sales|crm|deal|pipeline|outreach|prospect/i, "market-pipeline", "A sales pipeline narrowing into closed deals"],
  [/financ|account|invoice|billing|payment/i, "market-finance", "A calculator beside stacks of coins and a receipt"],
  [/legal|compliance|policy|audit|health|medical|fhir/i, "market-compliance", "A clipboard checklist with every item ticked and a seal of approval"],
  [/secur|identity|access/i, "market-security", "A padlock in front of a shield"],
  [/hr|people|recruit|onboard|employee/i, "market-onboarding", "An open door with a welcome mat and three step markers leading in"],
  [/support|helpdesk|ticket|service/i, "market-support", "A support headset beside a resolved ticket"],
  [/engineer|devops|site|monitor|uptime/i, "market-site-health", "A browser window with a steady heartbeat line and a green check"],
  [/operation|erp|inventory|supply|product/i, "market-product", "A product box on a conveyor with a checkmark"],
]

const FALLBACK_ART = ["market-leads", "market-revenue", "market-deals", "market-new-customers", "market-prospecting", "market-tickets"]

function artFor(asset: MarketplaceFederatedConnectorSummary): { src: string; alt: string } {
  const topic = [asset.category, asset.department, ...(asset.tags ?? []), asset.title].filter(Boolean).join(" ")
  for (const [re, file, alt] of ART_BY_TOPIC) {
    if (re.test(topic)) return { src: `/illustrations/${file}.svg`, alt }
  }
  let h = 0
  for (const ch of asset.id) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return { src: `/illustrations/${FALLBACK_ART[h % FALLBACK_ART.length]}.svg`, alt: "" }
}

function formatPrice(asset: MarketplaceFederatedConnectorSummary): string {
  if (asset.pricingType === "free") return "Free"
  if (asset.priceCents == null) return "Paid"
  const amount = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: (asset.currency ?? "usd").toUpperCase(),
    maximumFractionDigits: asset.priceCents % 100 === 0 ? 0 : 2,
  }).format(asset.priceCents / 100)
  return asset.pricingType === "subscription" ? `${amount} / mo` : amount
}

function stateOf(asset: MarketplaceFederatedConnectorSummary) {
  const status = String(asset.status ?? "").toLowerCase()
  if (asset.installed) return { status: "connected" as const, label: asset.runState === "running" ? "Installed · running" : "Installed" }
  if (status.includes("review") || status === "pending" || status === "submitted") return { status: "syncing" as const, label: "In review" }
  return { status: "offline" as const, label: "Not installed" }
}

function useDebouncedValue(value: string, delayMs = 300): string {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}

function PartnerCard({ asset }: { asset: MarketplaceFederatedConnectorSummary }) {
  const art = artFor(asset)
  const state = stateOf(asset)
  const vendor = asset.vendor || asset.publisherDisplayName || asset.title
  const inReview = state.label === "In review"
  return (
    <article className="cn-card cn-pcard">
      <div className="art">
        {/* eslint-disable-next-line @next/next/no-img-element -- static SVG illustrations */}
        <img src={art.src} alt={art.alt} />
        <span className="state">
          <StatusPill status={state.status} label={state.label} />
        </span>
      </div>
      <div className="meta">
        <VendorTile vendor={vendor} size="md" style={{ boxShadow: "0 0 0 4px var(--gv-card)" }} />
        <span className="cn-row-flex" style={{ gap: 6 }}>
          {asset.verified ? <span className="cn-pill connected">Certified</span> : null}
          <span className="cn-pill neutral">{formatPrice(asset)}</span>
        </span>
      </div>
      <div className="body">
        <div>
          <div style={{ fontWeight: 600, fontSize: 16 }}>{asset.title}</div>
          <div className="cn-sub" style={{ fontSize: 13 }}>
            {["by " + vendor, asset.category || asset.department].filter(Boolean).join(" · ")}
          </div>
        </div>
        {asset.description ? (
          <p className="cn-sub" style={{ margin: 0, fontSize: 14, lineHeight: 1.5 }}>
            {asset.description}
          </p>
        ) : null}
        <div className="cn-row-flex" style={{ gap: 8, marginTop: "auto", paddingTop: 4 }}>
          {asset.slug ? (
            <Link href={`/marketplace/assets/${encodeURIComponent(asset.slug)}`} className="gv-btn dark sm">
              View details
            </Link>
          ) : null}
          {inReview ? (
            <span className="cn-sub" style={{ fontSize: 13 }}>In review</span>
          ) : (
            <Link href="/marketplace/submit" className="cn-btn-text sm">
              Partner track
            </Link>
          )}
          <span className="cn-sub" style={{ marginLeft: "auto", fontSize: 12 }}>
            {asset.installCount ? `${asset.installCount.toLocaleString()} ${asset.installCount === 1 ? "install" : "installs"}` : "New"}
          </span>
        </div>
      </div>
    </article>
  )
}

export default function FederatedConnectorsPage() {
  const { user } = useAuth()
  const [search, setSearch] = useState("")
  const [filter, setFilter] = useState<Filter>("all")
  const debouncedSearch = useDebouncedValue(search.trim())
  const { data, error, isLoading, mutate } = useSWR(
    user ? (["marketplace-federated-connectors", debouncedSearch] as const) : null,
    () => marketplaceApi.listFederatedConnectors({ search: debouncedSearch || undefined, limit: 100 }),
  )

  const assets = useMemo(() => data?.assets ?? [], [data])
  const counts = useMemo(
    () => ({
      all: assets.length,
      certified: assets.filter((a) => a.verified).length,
      free: assets.filter((a) => a.pricingType === "free").length,
      paid: assets.filter((a) => a.pricingType !== "free").length,
    }),
    [assets],
  )
  const shown = useMemo(
    () =>
      assets.filter((a) =>
        filter === "certified" ? a.verified : filter === "free" ? a.pricingType === "free" : filter === "paid" ? a.pricingType !== "free" : true,
      ),
    [assets, filter],
  )
  const tabs: Array<{ id: Filter; label: string }> = [
    { id: "all", label: "All" },
    { id: "certified", label: "Certified" },
    { id: "free", label: "Free" },
    { id: "paid", label: "Paid" },
  ]

  return (
    <AppShell title="Partner connectors">
      <div className="gv-ws" data-composition="discover" style={{ minHeight: "100%", background: "var(--gv-canvas)" }}>
        <div className="cn-page">
          <div className="cn-row-flex" style={{ justifyContent: "space-between", alignItems: "flex-end", gap: 16 }}>
            <div style={{ flex: "1 1 420px", minWidth: 0 }}>
              <div className="cn-eyebrow">Marketplace / Partner connectors</div>
              <h1 className="cn-h1" style={{ margin: "6px 0 0" }}>
                Partner connectors
              </h1>
              <p className="cn-lede" style={{ margin: "6px 0 0" }}>
                Connectors built and maintained by partners. Certified ones passed Gravitre&apos;s security review and appear in the main catalog too.
              </p>
            </div>
            <div className="cn-row-flex" style={{ gap: 8 }}>
              <Link href="/connectors" className="gv-btn outline sm">
                <ArrowLeft size={14} aria-hidden /> Back to connectors
              </Link>
              <Link href="/marketplace/submit" className="gv-btn dark sm">
                Become a partner
              </Link>
            </div>
          </div>

          <div className="cn-filters">
            <label className="gv-field cn-search">
              <Search size={16} aria-hidden />
              <input
                aria-label="Search partner connectors"
                placeholder="Search partner connectors"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <div className="cn-tabs" role="tablist" aria-label="Filter">
              {tabs.map((t) => (
                <button key={t.id} type="button" role="tab" className="cn-tab" aria-selected={filter === t.id} onClick={() => setFilter(t.id)}>
                  {t.label}
                  <span className="n">{counts[t.id]}</span>
                </button>
              ))}
            </div>
            {data ? (
              <span className="cn-sub" style={{ fontSize: 13 }}>
                {shown.length} of {data.total ?? assets.length} shown
              </span>
            ) : null}
          </div>

          {error ? (
            <div className="cn-alert bad" role="alert">
              <span style={{ flex: 1 }}>Could not refresh partner connectors. Loaded entries stay available.</span>
              <button type="button" className="gv-btn outline sm" onClick={() => void mutate()}>
                Retry
              </button>
            </div>
          ) : null}

          {isLoading && !data ? (
            <div className="cn-grid3" aria-busy="true">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="cn-card" style={{ height: 360, background: "var(--gv-soft)" }} />
              ))}
            </div>
          ) : !data ? null : shown.length === 0 ? (
            <section className="cn-card cn-pad" style={{ alignItems: "flex-start" }}>
              <div style={{ fontWeight: 600, fontSize: 16 }}>
                {debouncedSearch || filter !== "all" ? "No partner connectors match" : "No published partner connectors yet"}
              </div>
              <p className="cn-sub" style={{ margin: 0 }}>
                {debouncedSearch || filter !== "all" ? "Try a different search or filter." : "Partner registry entries appear here when they are published."}
              </p>
            </section>
          ) : (
            <div className="cn-grid3">
              {shown.map((asset) => (
                <PartnerCard key={asset.registryId ?? asset.id} asset={asset} />
              ))}
            </div>
          )}

          <section className="cn-card cn-pad" aria-labelledby="sdk-h" style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 24 }}>
            <div style={{ flex: "1 1 280px", minWidth: 0 }}>
              <div className="cn-eyebrow">Partner SDK</div>
              <h2 id="sdk-h" className="cn-h2" style={{ margin: "6px 0 4px" }}>
                Build a connector for your product
              </h2>
              <p className="cn-sub" style={{ margin: 0 }}>
                Describe your actions once and every Gravitre agent can use them, with approvals and audit built in.
              </p>
            </div>
            <ol className="cn-path" style={{ flex: "1 1 280px" }}>
              <li>
                <span className="cn-stepn">1</span>Define actions and scopes in a manifest
              </li>
              <li>
                <span className="cn-stepn">2</span>Test in the sandbox against a live workspace
              </li>
              <li>
                <span className="cn-stepn">3</span>Submit for security review and certification
              </li>
            </ol>
            <Link href="/marketplace/submit" className="gv-btn outline sm">
              Start a submission
            </Link>
          </section>
        </div>
      </div>
    </AppShell>
  )
}
