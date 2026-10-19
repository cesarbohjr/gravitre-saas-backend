// @vitest-environment jsdom
import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { MspClientList, MspOverview } from "@/lib/msp-program"

const mocks = vi.hoisted(() => ({ byKey: {} as Record<string, unknown> }))

vi.mock("swr", () => ({
  default: (key: unknown) => {
    const k = key === null ? "" : String(key)
    return { data: k ? mocks.byKey[k] : undefined, error: undefined, isLoading: false, mutate: vi.fn() }
  },
}))
vi.mock("@/lib/api", () => ({ organizationsApi: { switch: vi.fn() } }))
vi.mock("@/lib/org-context", () => ({ invalidateOrgCache: vi.fn(), setSelectedOrgInStorage: vi.fn() }))
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}))
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }))
;(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

import { MspClientsContent } from "@/components/settings/msp-clients"
import { MSP_CLIENTS_KEY } from "@/components/settings/msp-clients"
import { MSP_OVERVIEW_KEY } from "@/lib/use-msp-overview"
import { billingStateCopy, formatCents, parseDollarsToCents, MSP_EARNING_COPY } from "@/lib/msp-program"

let root: Root
let host: HTMLDivElement

beforeEach(() => {
  host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  mocks.byKey = {}
})
afterEach(() => {
  act(() => root.unmount())
  host.remove()
})

function render() {
  act(() =>
    root.render(
      <div className="gv-set">
        <MspClientsContent />
      </div>,
    ),
  )
}

const baseOverview: MspOverview = {
  org: { id: "msp-1", name: "Acme IT", account_type: "msp" },
  role: "owner",
  is_msp: true,
  can_manage: true,
  can_enroll: false,
  wholesale: {
    status: "ready",
    stripe_configured: true,
    configured_tiers: ["node", "control", "command"],
    message: null,
    prices: { node: { monthly_cents: 4100, currency: "usd" }, control: { monthly_cents: 10400, currency: "usd" }, command: null },
  },
  billing_account: { status: "active", current_period_end: null, cancel_at_period_end: false },
  managed_by: null,
  pending_request: null,
}

const list: MspClientList = {
  clients: [
    {
      id: "rel-1",
      client_org_id: "11111111-2222-3333-4444-555555555555",
      name: "Northwind Dental",
      plan_code: "control",
      plan_name: "Control",
      list_price_usd: 149,
      status: "active",
      origin: "created",
      access_level: "full",
      resale_price_cents: 25000,
      resale_interval: "month",
      resale_currency: "usd",
      resale_monthly_cents: 25000,
      wholesale_monthly_cents: 10400,
      margin_monthly_cents: 14600,
      approved_at: "2026-10-01T00:00:00Z",
      created_at: "2026-10-01T00:00:00Z",
      can_open: true,
      members: 6,
      usage: { ai_credits: 1234, workflow_runs: 9 },
      health: { label: "healthy", org_status: "active", billing_status: "active" },
    },
    {
      id: "rel-2",
      client_org_id: "99999999-8888-7777-6666-555555555555",
      name: "Contoso Legal",
      plan_code: "node",
      plan_name: "Node",
      list_price_usd: 59,
      status: "active",
      origin: "linked",
      access_level: "health_only",
      resale_price_cents: null,
      resale_interval: "month",
      resale_currency: "usd",
      resale_monthly_cents: null,
      wholesale_monthly_cents: 4100,
      margin_monthly_cents: null,
      approved_at: "2026-10-02T00:00:00Z",
      created_at: "2026-10-02T00:00:00Z",
      can_open: false,
      members: null,
      usage: null,
      health: null,
    },
    {
      id: "rel-3",
      client_org_id: "abcdef01-0000-0000-0000-000000000000",
      name: null,
      plan_code: "node",
      plan_name: "Node",
      list_price_usd: 59,
      status: "pending_client_approval",
      origin: "linked",
      access_level: null,
      resale_price_cents: 9900,
      resale_interval: "month",
      resale_currency: "usd",
      resale_monthly_cents: 9900,
      wholesale_monthly_cents: 4100,
      margin_monthly_cents: 5800,
      approved_at: null,
      created_at: "2026-10-03T00:00:00Z",
      can_open: false,
      members: null,
      usage: null,
      health: null,
    },
  ],
  totals: { wholesale_monthly_cents: 14500, resale_monthly_cents: 25000, margin_monthly_cents: 14600, active_clients: 2, complete: false },
  period: { start: "2026-10-01", end: "2026-10-31" },
  wholesale: baseOverview.wholesale,
  truncated: false,
}

describe("Settings › Clients", () => {
  it("lists clients with wholesale, resale, margin and totals", () => {
    mocks.byKey[MSP_OVERVIEW_KEY] = baseOverview
    mocks.byKey[MSP_CLIENTS_KEY] = list
    render()
    const text = host.textContent ?? ""
    expect(text).toContain(MSP_EARNING_COPY)
    expect(text).toContain("Northwind Dental")
    expect(text).toContain("$104.00")
    expect(text).toContain("$250.00")
    expect(text).toContain("$146.00")
    expect(text).toContain("Total (2 active)")
    expect(text).toContain("Wholesale billing is running")
    expect(text).toContain("Set a price for every client to see the full margin")
    // Health-only client: billing figures, but nothing private.
    expect(text).toContain("Contoso Legal")
    expect(text).toContain("Not shared")
    expect(text).toContain("Set price")
    // Pending link: no name until approved.
    expect(text).toContain("Workspace abcdef01")
    expect(text).toContain("Waiting for approval")
    expect(text).toContain("Withdraw")
    const openButtons = [...host.querySelectorAll("button")].filter((b) => b.textContent === "Open")
    expect(openButtons).toHaveLength(1)
  })

  it("shows the how-it-works guide when there are no clients and billing is not set up", () => {
    mocks.byKey[MSP_OVERVIEW_KEY] = { ...baseOverview, wholesale: { ...baseOverview.wholesale, status: "not_configured" }, billing_account: null }
    mocks.byKey[MSP_CLIENTS_KEY] = { ...list, clients: [], totals: { ...list.totals, active_clients: 0 } }
    render()
    const text = host.textContent ?? ""
    expect(text).toContain("Wholesale billing isn't set up yet")
    expect(text).toContain("No clients yet")
    expect(text).toContain("1. Add a client")
    expect(text).toContain("2. Start wholesale billing")
    expect(text).toContain("3. Bill your client")
  })

  it("invites an owner of a normal workspace to join", () => {
    mocks.byKey[MSP_OVERVIEW_KEY] = { ...baseOverview, is_msp: false, can_manage: false, can_enroll: true, org: { ...baseOverview.org, account_type: "standard" } }
    render()
    const text = host.textContent ?? ""
    expect(text).toContain("Resell Gravitre to your clients")
    expect(text).toContain("Join the partner program")
  })

  it("tells partner members that only owners and admins manage clients", () => {
    mocks.byKey[MSP_OVERVIEW_KEY] = { ...baseOverview, role: "member", can_manage: false }
    render()
    expect(host.textContent).toContain("Only its owners and admins can add clients")
    expect(host.textContent).not.toContain("Northwind Dental")
  })
})

describe("msp-program helpers", () => {
  it("parses dollars and formats cents", () => {
    expect(parseDollarsToCents("$1,200.50")).toBe(120050)
    expect(parseDollarsToCents("")).toBeNull()
    expect(parseDollarsToCents("abc")).toBeNull()
    expect(formatCents(4100)).toBe("$41.00")
    expect(formatCents(null)).toBeNull()
  })

  it("explains each billing state honestly", () => {
    const ws = baseOverview.wholesale
    expect(billingStateCopy({ wholesale: { ...ws, status: "not_configured" }, billing_account: null }).title).toBe(
      "Wholesale billing isn't set up yet",
    )
    expect(billingStateCopy({ wholesale: ws, billing_account: null }).action).toBe("start")
    expect(billingStateCopy({ wholesale: ws, billing_account: { status: "past_due", current_period_end: null, cancel_at_period_end: false } }).tone).toBe("red")
  })
})
