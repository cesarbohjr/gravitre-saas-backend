import { readFileSync } from "node:fs"
import { resolve } from "node:path"
import { describe, expect, it } from "vitest"
import {
  capabilitySnapshotToActionCatalog,
  deriveAutonomyLabel,
  type CapabilitySnapshot,
} from "@/lib/capabilities"

const webRoot = resolve(__dirname, "../..")
const read = (path: string) => readFileSync(resolve(webRoot, path), "utf8")

const snapshot = {
  orgId: "org-test",
  environment: "production",
  mutation: false,
  governance: {
    writeRequiresApprovalByDefault: true,
    noHitlPolicyMeans: "ACT WITH APPROVAL",
    hitlMatchedPolicyId: null,
  },
  connectedVendors: ["hubspot"],
  actions: [
    {
      tool: "hubspot.contacts.search",
      vendor: "hubspot",
      name: "Search contacts",
      tier: "v1",
      kind: "read",
      access: "read",
      requires_approval: false,
      destructive: false,
      implemented: true,
      runtimeRequiresUserApproval: false,
    },
    {
      tool: "hubspot.contacts.create",
      vendor: "hubspot",
      name: "Create contact",
      tier: "v2",
      kind: "write",
      access: "write",
      requires_approval: true,
      destructive: false,
      implemented: true,
      runtimeRequiresUserApproval: true,
    },
  ],
  catalogConnectors: [
    {
      vendor: "hubspot",
      display_name: "HubSpot",
      category: "crm",
      shipped: true,
      action_count: 2,
      implemented_read_count: 1,
      implemented_write_count: 1,
    },
  ],
  orgConnectors: [],
  agents: [],
  workflowPrimitives: [],
  verification: {},
  evidence: {},
} satisfies CapabilitySnapshot

describe("canonical capability convergence", () => {
  it("adapts canonical capability actions for existing workflow UI", () => {
    const catalog = capabilitySnapshotToActionCatalog(snapshot)
    const vendor = catalog.vendors[0]
    expect(vendor.vendor).toBe("hubspot")
    expect(vendor.tiers.v1.actions[0].tool).toBe("hubspot.contacts.search")
    expect(vendor.tiers.v2.actions[0].requiresApproval).toBe(true)
  })

  it("fails closed unless explicit autonomous auto_run is present", () => {
    expect(deriveAutonomyLabel(undefined, undefined, snapshot.governance)).toBe("ACT WITH APPROVAL")
    expect(deriveAutonomyLabel("read_only", {}, snapshot.governance)).toBe("READ ONLY")
    expect(
      deriveAutonomyLabel("autonomous", { write: "auto_run" }, snapshot.governance),
    ).toBe("ACT WITHIN POLICY")
    expect(
      deriveAutonomyLabel(
        "autonomous",
        { write: "auto_run" },
        { ...snapshot.governance, hitlMatchedPolicyId: "policy-1" },
      ),
    ).toBe("ACT WITH APPROVAL")
  })

  it("routes connector catalog consumers through GET /api/capabilities", () => {
    const api = read("lib/api.ts")
    const operating = read("components/connectors/connector-operating.tsx")
    expect(api).toMatch(/apiUrl\("\/api\/capabilities"\)/)
    expect(operating).toMatch(/"\/api\/capabilities"/)
    expect(operating).not.toMatch(/\/api\/connectors\/catalog\/actions/)
  })

  it("does not promise automatic writes in the chat execution panel", () => {
    const chat = read("components/gravitre/assistant/chat-execution-panel.tsx")
    expect(chat).toMatch(/writes wait for you unless policy allows them/)
    expect(chat).not.toMatch(/write steps run automatically unless your approval settings require confirmation/i)
  })
})
