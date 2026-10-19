"use client"

/**
 * Settings › Clients: the MSP partner program.
 *
 * You pay Gravitre the wholesale price for each client and bill them your own
 * price. The difference is your margin. Every figure here comes from
 * /api/msp/program; wholesale amounts are read from the configured Stripe
 * Prices, never invented.
 */
import { useMemo, useState } from "react"
import Link from "next/link"
import useSWR from "swr"
import { Building2, Download, HandCoins, Plus, Users, Wallet } from "lucide-react"
import { toast } from "sonner"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { SetError, SetNote, SetPill, SetSkeleton, SetStat, SetTabs } from "@/components/settings/settings-kit"
import { MspClientRelationship } from "@/components/settings/msp-client-relationship"
import { MSP_OVERVIEW_KEY, useMspOverview } from "@/lib/use-msp-overview"
import { organizationsApi } from "@/lib/api"
import { invalidateOrgCache, setSelectedOrgInStorage } from "@/lib/org-context"
import {
  MSP_DOCS_HREF,
  MSP_EARNING_COPY,
  MSP_PLAN_OPTIONS,
  accessLevelLabel,
  billingStateCopy,
  clientStatusLabel,
  formatCents,
  mspProgramApi,
  parseDollarsToCents,
  type BillingSync,
  type MspClientList,
  type MspClientRow,
  type MspInterval,
  type MspOverview,
  type MspPlanCode,
} from "@/lib/msp-program"

export const MSP_CLIENTS_KEY = "msp:program:clients"

const COLS = "minmax(180px,1.6fr) 110px 120px 90px 110px 110px 120px 110px minmax(150px,auto)"

export function MspClientsContent() {
  const { data: overview, error, isLoading, mutate } = useMspOverview()
  if (error && !overview) return <SetError message="Could not load the partner program." onRetry={() => void mutate()} />
  if (isLoading || !overview) return <SetSkeleton rows={4} label="Loading partner program" />
  if (!overview.is_msp) return <NotPartner overview={overview} onEnrolled={() => void mutate()} />
  if (!overview.can_manage) {
    return (
      <section className="gs-card" style={{ padding: 20 }}>
        <p className="gs-sub" style={{ margin: 0 }}>
          This workspace is a Gravitre partner. Only its owners and admins can add clients and see wholesale billing.
        </p>
      </section>
    )
  }
  return <PartnerClients overview={overview} onOverviewChange={() => void mutate()} />
}

/** The 3-step how / when / where guide. Shown before joining and on an empty client list. */
export function MspHowItWorks() {
  const steps = [
    {
      title: "1. Add a client",
      body: "Create a new workspace for them, or link one they already have. Linking waits for their owner to approve.",
    },
    {
      title: "2. Start wholesale billing",
      body: "With your first client, start one subscription. Each active client adds its plan's wholesale price, prorated.",
    },
    {
      title: "3. Bill your client",
      body: "Set your own price per client here, then invoice them from your own system. Download a statement each month.",
    },
  ]
  return (
    <div className="gs-stats" data-review-surface="msp-how-it-works">
      {steps.map((step) => (
        <div key={step.title} className="gs-stat" style={{ flexDirection: "column", gap: 6 }}>
          <b style={{ fontSize: 15 }}>{step.title}</b>
          <span className="gs-sub" style={{ margin: 0 }}>
            {step.body}
          </span>
        </div>
      ))}
    </div>
  )
}

function NotPartner({ overview, onEnrolled }: { overview: MspOverview; onEnrolled: () => void }) {
  const [busy, setBusy] = useState(false)
  async function enroll() {
    setBusy(true)
    try {
      await mspProgramApi.enroll()
      toast.success("You're in the partner program. Add your first client.")
      onEnrolled()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not join the partner program")
    } finally {
      setBusy(false)
    }
  }
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <MspClientRelationship />
      <section className="gs-card" style={{ padding: 20, display: "grid", gap: 14 }} data-review-surface="msp-join">
        <div className="gs-card-title">
          <HandCoins size={18} aria-hidden />
          <h3>Resell Gravitre to your clients</h3>
        </div>
        <p className="gs-sub" style={{ margin: 0 }}>
          For managed service providers and agencies. {MSP_EARNING_COPY}
        </p>
        <MspHowItWorks />
        {overview.can_enroll ? (
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            <button type="button" className="gs-btn dark sm" disabled={busy} onClick={() => void enroll()}>
              Join the partner program
            </button>
            <Link href={MSP_DOCS_HREF} className="gs-btn line sm">
              Read the guide
            </Link>
          </div>
        ) : (
          <p className="gs-sub" style={{ margin: 0 }}>
            {overview.managed_by || overview.pending_request
              ? "A workspace managed by a partner can't become a partner itself. Use a separate workspace for your MSP."
              : "Only the workspace owner can join the partner program."}
          </p>
        )}
      </section>
    </div>
  )
}

function syncToast(billing: BillingSync | undefined) {
  if (!billing) return
  if (billing.status === "checkout_required") toast.message("Start wholesale billing to cover this client.")
  else if (billing.status === "error") toast.error(billing.message ?? "Billing didn't update. Use Sync billing to retry.")
}

function PartnerClients({ overview, onOverviewChange }: { overview: MspOverview; onOverviewChange: () => void }) {
  const { data, error, isLoading, mutate } = useSWR<MspClientList>(MSP_CLIENTS_KEY, () => mspProgramApi.listClients(), {
    revalidateOnFocus: false,
  })
  const [addOpen, setAddOpen] = useState(false)
  const [editing, setEditing] = useState<MspClientRow | null>(null)
  const [busy, setBusy] = useState(false)
  const [period, setPeriod] = useState(() => new Date().toISOString().slice(0, 7))
  const billing = billingStateCopy(overview)
  const clients = data?.clients ?? []
  const totals = data?.totals

  const refresh = async () => {
    await Promise.all([mutate(), onOverviewChange()])
  }

  async function startBilling() {
    setBusy(true)
    try {
      const { url } = await mspProgramApi.startBilling()
      window.location.assign(url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start billing")
      setBusy(false)
    }
  }

  async function syncBilling() {
    setBusy(true)
    try {
      const result = await mspProgramApi.syncBilling()
      if (result.status === "error") toast.error(result.message ?? "Billing didn't update")
      else toast.success("Billing is up to date")
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not sync billing")
    } finally {
      setBusy(false)
    }
  }

  async function downloadStatement() {
    try {
      const { blob, filename } = await mspProgramApi.statement(period)
      const href = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = href
      a.download = filename
      a.click()
      URL.revokeObjectURL(href)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not download the statement")
    }
  }

  async function openClient(row: MspClientRow) {
    try {
      await organizationsApi.switch(row.client_org_id)
      setSelectedOrgInStorage({ id: row.client_org_id, name: row.name ?? "Client" })
      invalidateOrgCache()
      // Full page load (not router.push) so cached data from the partner workspace is dropped.
      // eslint-disable-next-line @next/next/no-location-assign-relative-destination
      window.location.href = "/home"
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not open this client")
    }
  }

  async function detach(row: MspClientRow) {
    const label = row.name ?? "this workspace"
    const msg =
      row.status === "pending_client_approval"
        ? `Withdraw the request to manage ${label}?`
        : `Stop managing ${label}? You stop paying for it, your people lose any access it gave them, and it moves to a 7-day trial.`
    if (!window.confirm(msg)) return
    try {
      await mspProgramApi.detach(row.id)
      toast.success(row.status === "pending_client_approval" ? "Request withdrawn" : `${label} detached`)
      await refresh()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not detach")
    }
  }

  return (
    <div style={{ display: "grid", gap: 16 }} data-review-surface="msp-clients">
      <p className="gs-sub" style={{ margin: 0 }}>
        {MSP_EARNING_COPY}
      </p>

      <SetNote tone={billing.tone}>
        <b>{billing.title}.</b> {billing.body}
        {billing.action === "start" && clients.some((c) => c.status === "active") ? (
          <div style={{ marginTop: 8 }}>
            <button type="button" className="gs-btn dark sm" disabled={busy} onClick={() => void startBilling()}>
              Start wholesale billing
            </button>
          </div>
        ) : null}
      </SetNote>

      <div className="gs-stats">
        <SetStat icon={Users} label="Active clients" value={totals ? totals.active_clients : null} />
        <SetStat
          icon={Wallet}
          label="You pay Gravitre"
          value={totals ? formatCents(totals.wholesale_monthly_cents) : null}
          hint="per month, wholesale"
        />
        <SetStat
          icon={Building2}
          label="You bill clients"
          value={totals ? formatCents(totals.resale_monthly_cents) : null}
          hint="per month, your prices"
        />
        <SetStat
          icon={HandCoins}
          tone="green"
          label="Your margin"
          value={totals ? formatCents(totals.margin_monthly_cents) : null}
          hint={totals && !totals.complete ? "Set a price for every client to see the full margin" : "per month"}
        />
      </div>

      <section className="gs-card clip">
        <div className="gs-toolbar">
          <button type="button" className="gs-btn dark sm" onClick={() => setAddOpen(true)}>
            <Plus size={15} aria-hidden />
            Add client
          </button>
          <span style={{ flex: 1 }} />
          <label className="gs-field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <span>Statement</span>
            <input
              type="month"
              aria-label="Statement month"
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              style={{ minHeight: 36, width: 160 }}
            />
          </label>
          <button type="button" className="gs-btn line sm" onClick={() => void downloadStatement()}>
            <Download size={15} aria-hidden />
            Download CSV
          </button>
          {overview.billing_account?.status === "active" || overview.billing_account?.status === "trialing" ? (
            <button type="button" className="gs-btn text sm" disabled={busy} onClick={() => void syncBilling()}>
              Sync billing
            </button>
          ) : null}
        </div>

        {error && !data ? (
          <SetError message="Could not load your clients." onRetry={() => void mutate()} />
        ) : isLoading && !data ? (
          <SetSkeleton rows={3} label="Loading clients" />
        ) : clients.length === 0 ? (
          <div className="gs-empty" style={{ display: "grid", gap: 14 }}>
            <b>No clients yet</b>
            <p>Here is how it works, start to finish.</p>
            <MspHowItWorks />
            <div>
              <button type="button" className="gs-btn dark sm" onClick={() => setAddOpen(true)}>
                <Plus size={15} aria-hidden />
                Add your first client
              </button>
            </div>
          </div>
        ) : (
          <div className="gs-scroll-x">
            <div className="gs-tbl stack" role="table" aria-label="Clients" style={{ ["--cols" as string]: COLS, minWidth: 1100 }}>
              <div className="gs-tr head" role="row">
                {["Client", "Plan", "Status", "Members", "AI credits", "Health", "Wholesale", "Your price", "Margin"].map((h) => (
                  <div key={h} className="gs-th" role="columnheader">
                    {h}
                  </div>
                ))}
              </div>
              {clients.map((row) => (
                <ClientRow
                  key={row.id}
                  row={row}
                  onOpen={() => void openClient(row)}
                  onEdit={() => setEditing(row)}
                  onDetach={() => void detach(row)}
                />
              ))}
              {totals ? (
                <div className="gs-row" role="row" style={{ fontWeight: 600 }}>
                  <div className="gs-td" role="cell">
                    Total ({totals.active_clients} active)
                  </div>
                  <div className="gs-td" role="cell" />
                  <div className="gs-td" role="cell" />
                  <div className="gs-td" role="cell" />
                  <div className="gs-td" role="cell" />
                  <div className="gs-td" role="cell" />
                  <div className="gs-td" role="cell">
                    {formatCents(totals.wholesale_monthly_cents)}
                  </div>
                  <div className="gs-td" role="cell">
                    {formatCents(totals.resale_monthly_cents)}
                  </div>
                  <div className="gs-td" role="cell">
                    {formatCents(totals.margin_monthly_cents)}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        )}
        {data?.truncated ? (
          <div className="gs-foot">Showing your first {clients.length} clients.</div>
        ) : null}
      </section>

      <p className="orgs-docs gs-sub">
        Amounts are per month. Usage is for {data ? `${data.period.start} to ${data.period.end}` : "this month"}.{" "}
        <Link href={MSP_DOCS_HREF} className="gs-link">
          How the partner program works
        </Link>
      </p>

      <AddClientDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        overview={overview}
        onAdded={async (billingResult) => {
          syncToast(billingResult)
          await refresh()
        }}
      />
      <EditClientDialog row={editing} onClose={() => setEditing(null)} onSaved={refresh} />
    </div>
  )
}

function ClientRow({
  row,
  onOpen,
  onEdit,
  onDetach,
}: {
  row: MspClientRow
  onOpen: () => void
  onEdit: () => void
  onDetach: () => void
}) {
  const pending = row.status === "pending_client_approval"
  const notShared = <span className="gs-sub">Not shared</span>
  return (
    <div className="gs-row" role="row" data-client-id={row.id}>
      <div className="gs-td" role="cell">
        <div className="t">{row.name ?? `Workspace ${row.client_org_id.slice(0, 8)}`}</div>
        <div className="s">
          {pending ? "Their owner needs to approve" : `${accessLevelLabel(row.access_level)}${row.origin === "created" ? " · created by you" : ""}`}
        </div>
        <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
          {row.can_open ? (
            <button type="button" className="gs-btn green sm" onClick={onOpen}>
              Open
            </button>
          ) : null}
          {!pending ? (
            <button type="button" className="gs-btn line sm" onClick={onEdit}>
              Edit
            </button>
          ) : null}
          <button type="button" className="gs-btn text sm" onClick={onDetach}>
            {pending ? "Withdraw" : "Detach"}
          </button>
        </div>
      </div>
      <div className="gs-td" role="cell">
        <span className="gs-chip">{row.plan_name}</span>
      </div>
      <div className="gs-td" role="cell">
        <SetPill tone={row.status === "active" ? "green" : row.status === "detached" ? "neutral" : "amber"}>
          {clientStatusLabel(row.status)}
        </SetPill>
      </div>
      <div className="gs-td" role="cell">
        {pending ? "" : row.members ?? notShared}
      </div>
      <div className="gs-td" role="cell">
        {pending ? "" : row.usage ? (row.usage.ai_credits ?? 0).toLocaleString() : notShared}
      </div>
      <div className="gs-td" role="cell">
        {pending ? (
          ""
        ) : row.health ? (
          <SetPill tone={row.health.label === "healthy" ? "green" : "red"} dot>
            {row.health.label === "healthy" ? "Healthy" : "Needs attention"}
          </SetPill>
        ) : (
          notShared
        )}
      </div>
      <div className="gs-td" role="cell">
        {formatCents(row.wholesale_monthly_cents) ?? <span className="gs-sub">Not available</span>}
      </div>
      <div className="gs-td" role="cell">
        {row.resale_price_cents === null ? (
          <button type="button" className="gs-link" onClick={onEdit} disabled={pending}>
            Set price
          </button>
        ) : (
          <>
            {formatCents(row.resale_price_cents, row.resale_currency)}
            <span className="gs-sub">/{row.resale_interval === "year" ? "yr" : "mo"}</span>
          </>
        )}
      </div>
      <div className="gs-td" role="cell">
        {formatCents(row.margin_monthly_cents) ?? <span className="gs-sub">-</span>}
      </div>
    </div>
  )
}

type AddMode = "create" | "link"

function PriceFields({
  price,
  setPrice,
  billedEvery,
  setBilledEvery,
  plan,
  setPlan,
  overview,
}: {
  price: string
  setPrice: (v: string) => void
  billedEvery: MspInterval
  setBilledEvery: (v: MspInterval) => void
  plan: MspPlanCode
  setPlan: (v: MspPlanCode) => void
  overview: Pick<MspOverview, "wholesale">
}) {
  const wholesale = overview.wholesale.prices?.[plan]
  return (
    <div className="gv-set">
      <div className="gs-grid-fields">
        <label className="gs-field">
          Plan
          <select value={plan} onChange={(event) => setPlan(event.target.value as MspPlanCode)}>
            {MSP_PLAN_OPTIONS.map((option) => (
              <option key={option.code} value={option.code}>
                {option.name}
              </option>
            ))}
          </select>
          <span className="hint">
            {wholesale ? `You pay ${formatCents(wholesale.monthly_cents, wholesale.currency)} a month wholesale.` : "Wholesale price not available yet."}
          </span>
        </label>
        <label className="gs-field">
          Your price to the client
          <input inputMode="decimal" placeholder="e.g. 199" value={price} onChange={(event) => setPrice(event.target.value)} />
          <span className="hint">In US dollars. Optional, you can set it later.</span>
        </label>
        <label className="gs-field">
          Billed
          <select value={billedEvery} onChange={(event) => setBilledEvery(event.target.value as MspInterval)}>
            <option value="month">Monthly</option>
            <option value="year">Yearly</option>
          </select>
        </label>
      </div>
    </div>
  )
}

function AddClientDialog({
  open,
  onOpenChange,
  overview,
  onAdded,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  overview: MspOverview
  onAdded: (billing?: BillingSync) => Promise<void>
}) {
  const [mode, setMode] = useState<AddMode>("create")
  const [name, setName] = useState("")
  const [workspaceId, setWorkspaceId] = useState("")
  const [plan, setPlan] = useState<MspPlanCode>("control")
  const [price, setPrice] = useState("")
  const [billedEvery, setBilledEvery] = useState<MspInterval>("month")
  const [busy, setBusy] = useState(false)
  const cents = useMemo(() => parseDollarsToCents(price), [price])
  const priceInvalid = price.trim() !== "" && cents === null

  async function submit() {
    if (priceInvalid) {
      toast.error("Enter the price as a number, like 199 or 199.50")
      return
    }
    setBusy(true)
    try {
      if (mode === "create") {
        const out = await mspProgramApi.createClient({ name: name.trim(), plan_code: plan, resale_price_cents: cents, resale_interval: billedEvery })
        toast.success(`${out.client.name} is ready. Invite their team from Organizations.`)
        await onAdded(out.billing)
      } else {
        await mspProgramApi.linkClient({ client_org_id: workspaceId.trim(), plan_code: plan, resale_price_cents: cents, resale_interval: billedEvery })
        toast.success("Request sent. Their owner sees it in Settings › Organizations.")
        await onAdded()
      }
      setName("")
      setWorkspaceId("")
      setPrice("")
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not add the client")
    } finally {
      setBusy(false)
    }
  }

  const ready = mode === "create" ? name.trim().length > 0 : /^[0-9a-f-]{36}$/i.test(workspaceId.trim())
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add a client</DialogTitle>
          <DialogDescription>
            {mode === "create"
              ? "A new workspace you own. Invite the client's people to it like any workspace."
              : "Their owner gets a request to approve and chooses what your team can see."}
          </DialogDescription>
        </DialogHeader>
        <div className="gv-set" style={{ display: "grid", gap: 14 }}>
          <SetTabs<AddMode>
            label="How to add"
            value={mode}
            onChange={setMode}
            options={[
              { id: "create", label: "Create a client workspace" },
              { id: "link", label: "Link an existing workspace" },
            ]}
          />
          {mode === "create" ? (
            <label className="gs-field">
              Client name
              <input value={name} placeholder="Northwind Dental" onChange={(event) => setName(event.target.value)} />
            </label>
          ) : (
            <label className="gs-field">
              Their workspace ID
              <input className="gs-mono" value={workspaceId} placeholder="00000000-0000-0000-0000-000000000000" onChange={(event) => setWorkspaceId(event.target.value)} />
              <span className="hint">Their owner finds it in Settings › Organizations under the workspace name.</span>
            </label>
          )}
          <PriceFields price={price} setPrice={setPrice} billedEvery={billedEvery} setBilledEvery={setBilledEvery} plan={plan} setPlan={setPlan} overview={overview} />
        </div>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={busy || !ready || priceInvalid} onClick={() => void submit()}>
            {mode === "create" ? "Create workspace" : "Send request"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function EditClientDialog({ row, onClose, onSaved }: { row: MspClientRow | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const { data: overview } = useSWR<MspOverview>(MSP_OVERVIEW_KEY)
  const [plan, setPlan] = useState<MspPlanCode>("control")
  const [price, setPrice] = useState("")
  const [billedEvery, setBilledEvery] = useState<MspInterval>("month")
  const [busy, setBusy] = useState(false)
  const [loadedFor, setLoadedFor] = useState<string | null>(null)
  if (row && loadedFor !== row.id) {
    setLoadedFor(row.id)
    setPlan(row.plan_code)
    setPrice(row.resale_price_cents === null ? "" : String(row.resale_price_cents / 100))
    setBilledEvery(row.resale_interval)
  }
  const cents = parseDollarsToCents(price)
  const invalid = price.trim() !== "" && cents === null

  async function save() {
    if (!row) return
    setBusy(true)
    try {
      const out = await mspProgramApi.updateClient(row.id, {
        plan_code: plan,
        resale_interval: billedEvery,
        ...(cents === null ? { clear_resale_price: true } : { resale_price_cents: cents }),
      })
      syncToast(out.billing)
      toast.success("Saved")
      await onSaved()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={Boolean(row)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Edit {row?.name ?? "client"}</DialogTitle>
          <DialogDescription>
            Changing the plan changes what you pay Gravitre for this client, prorated, and what the client can use.
          </DialogDescription>
        </DialogHeader>
        <PriceFields
          price={price}
          setPrice={setPrice}
          billedEvery={billedEvery}
          setBilledEvery={setBilledEvery}
          plan={plan}
          setPlan={setPlan}
          overview={overview ?? { wholesale: { status: "not_configured", stripe_configured: false, configured_tiers: [], message: null } }}
        />
        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="button" disabled={busy || invalid} onClick={() => void save()}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
