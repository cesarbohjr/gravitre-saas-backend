import { describe, expect, it } from "vitest"
import {
  catalogActionIndex,
  connectedVendorSet,
  getConnectorValidationIssues,
} from "@/lib/workflows/builder-connector-validation"
import type { VendorActionCatalog } from "@/lib/connector-actions"

function vendor(id: string, actions: Array<{ id: string; implemented?: boolean }>): VendorActionCatalog {
  const defs = actions.map((a) => ({
    id: a.id,
    tool: `${id}.${a.id}`,
    name: a.id,
    description: a.id,
    tier: "v2" as const,
    kind: "write" as const,
    scopes: [],
    implemented: a.implemented ?? true,
  }))
  return {
    vendor: id,
    displayName: id,
    tiers: {
      v1: { label: "Read", actions: [] },
      v2: { label: "Write", actions: defs },
      v3: { label: "Advanced", actions: [] },
    },
  } as unknown as VendorActionCatalog
}

const node = (overrides: Partial<{ vendor: string; selectedAction: string }>) => ({
  id: "n1",
  name: "Step",
  type: "connector",
  ...overrides,
})

describe("builder connector validation", () => {
  it("uses real connector state, not a hard-coded library", () => {
    const connected = connectedVendorSet([
      { vendor: "hubspot", status: "active" },
      { vendor: "salesforce", status: "expired" },
    ])
    const catalog = catalogActionIndex({ vendors: [vendor("hubspot", [{ id: "contacts.create" }]), vendor("salesforce", [{ id: "leads.update" }])] })
    const issues = getConnectorValidationIssues(
      [node({ vendor: "hubspot", selectedAction: "contacts.create" }), node({ vendor: "salesforce", selectedAction: "leads.update" })],
      { connectedVendors: connected, catalogActions: catalog },
    )
    expect(issues).toHaveLength(1)
    expect(issues[0].message).toMatch(/salesforce is not connected/)
  })

  it("accepts canonical catalog actions the legacy list does not know", () => {
    const issues = getConnectorValidationIssues([node({ vendor: "hubspot", selectedAction: "contacts.create" })], {
      connectedVendors: new Set(["hubspot"]),
      catalogActions: catalogActionIndex({ vendors: [vendor("hubspot", [{ id: "contacts.create" }])] }),
      isLegacyActionImplemented: () => false,
    })
    expect(issues).toEqual([])
  })

  it("rejects unimplemented catalog actions", () => {
    const issues = getConnectorValidationIssues([node({ vendor: "hubspot", selectedAction: "deals.merge" })], {
      connectedVendors: new Set(["hubspot"]),
      catalogActions: catalogActionIndex({ vendors: [vendor("hubspot", [{ id: "deals.merge", implemented: false }])] }),
    })
    expect(issues.map((i) => i.message)).toEqual([`Action "deals.merge" is not available for hubspot.`])
  })

  it("falls back to the legacy list only when the catalog lacks the vendor", () => {
    const issues = getConnectorValidationIssues([node({ vendor: "stripe", selectedAction: "charge" })], {
      connectedVendors: new Set(["stripe"]),
      catalogActions: new Map(),
      isLegacyActionImplemented: (v, a) => v === "stripe" && a === "charge",
    })
    expect(issues).toEqual([])
  })

  it("does not block on connection state before connectors load", () => {
    const issues = getConnectorValidationIssues([node({ vendor: "hubspot", selectedAction: "contacts.create" })], {
      connectedVendors: null,
      catalogActions: catalogActionIndex({ vendors: [vendor("hubspot", [{ id: "contacts.create" }])] }),
    })
    expect(issues).toEqual([])
  })
})
