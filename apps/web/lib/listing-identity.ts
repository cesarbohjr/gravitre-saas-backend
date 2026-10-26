/**
 * Listing identity system (UIRefresh-System and UIRefresh-Banners designs).
 *
 * Every Marketplace listing and every agent detail page is drawn from two
 * facts: what it is (agent, workflow, knowledge, pack, connector) and which
 * team it serves. The kind picks the badge icon and the cover scene; the
 * department picks the color, the agent icon and the cover palette.
 */
import { mapApiDepartmentToFleet } from "@/lib/agent-identity-bridge"

export type IdentityDepartmentId =
  | "sales"
  | "marketing"
  | "support"
  | "customer_success"
  | "finance"
  | "operations"
  | "hr"
  | "engineering"
  | "security"
  | "general"

export type ListingKind = "agent" | "workflow" | "knowledge" | "pack" | "connector"

export type CoverMark = { x: number; y: number; scale: number; opacity: number; width: number; d: string }

export type CoverPalette = {
  /** Paper ground. */
  base: string
  /** Three soft color fields that drift across the ground. */
  mesh: [string, string, string]
  /** Light tint of the department color for the line art. */
  stroke: string
  /** One oversized mark and four companions from the same job (1300x168 cover). */
  marks: CoverMark[]
  /** Small marks in place of the loose rings (Finance draws dollar signs). */
  companions?: CoverMark[]
}

export type IdentityDepartment = {
  id: IdentityDepartmentId
  label: string
  /** Icon and chip color; 4.5:1 on white. */
  color: string
  /** 24x24 stroke path: the department icon, also the default avatar for every agent. */
  icon: string
  cover: CoverPalette
}

const COVERS: Record<Exclude<IdentityDepartmentId, "security" | "general">, CoverPalette> = {
  finance: {
    base: "#E7ECE3",
    mesh: ["#CFDCCB", "#EBDCC0", "#DCE3E8"],
    stroke: "#C8D6C4",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M3 17l6-6 4 4 8-8 M15 7h6v6" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M4 7c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 7v4c0 1.7 3.6 3 8 3s8-1.3 8-3V7 M4 11v4c0 1.7 3.6 3 8 3s8-1.3 8-3v-4 M4 15v2c0 1.7 3.6 3 8 3s8-1.3 8-3v-2" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M8 6h8v3.5H8z M8.5 13h1 M11.5 13h1 M14.5 13h1 M8.5 16.5h1 M11.5 16.5h1 M14.5 16.5h1" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M19 5L5 19 M7 5a2 2 0 1 0 0 4a2 2 0 1 0 0-4z M17 15a2 2 0 1 0 0 4a2 2 0 1 0 0-4z" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M6 3h12v18l-3-2-3 2-3-2-3 2z M9 8h6 M9 12h6 M9 16h3" },
    ],
    companions: [
      { x: 706, y: 124, scale: 1.2, opacity: 0.85, width: 4, d: "M12 3v18 M16.5 7.5c0-1.9-2-3-4.5-3s-4.5 1.2-4.5 3.2c0 4.3 9 2.3 9 6.6 0 2-2 3.2-4.5 3.2s-4.5-1.1-4.5-3" },
      { x: 860, y: 0, scale: 1.6, opacity: 0.85, width: 4, d: "M12 3v18 M16.5 7.5c0-1.9-2-3-4.5-3s-4.5 1.2-4.5 3.2c0 4.3 9 2.3 9 6.6 0 2-2 3.2-4.5 3.2s-4.5-1.1-4.5-3" },
      { x: 1150, y: 124, scale: 2, opacity: 0.85, width: 4, d: "M12 3v18 M16.5 7.5c0-1.9-2-3-4.5-3s-4.5 1.2-4.5 3.2c0 4.3 9 2.3 9 6.6 0 2-2 3.2-4.5 3.2s-4.5-1.1-4.5-3" },
    ],
  },
  sales: {
    base: "#E9E9F3",
    mesh: ["#CACCE8", "#E4DDEF", "#D9E3EC"],
    stroke: "#CBCCEA",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M3 17l6-6 4 4 8-8 M15 7h6v6" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M3 5h18l-7 8v6l-4 2v-8z" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2z" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M3 6h18v12H3z M3 7l9 6 9-6" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M12 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8z M4 21c0-4 3.6-7 8-7s8 3 8 7" },
    ],
  },
  marketing: {
    base: "#F1EAE0",
    mesh: ["#EBDCC0", "#E9CDBF", "#E6E0D2"],
    stroke: "#E8D1C1",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M5 20V10 M12 20V4 M19 20v-7" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14z M20 20l-4-4" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M3 10v4h3l7 4V6L6 10z M16 9a4 4 0 0 1 0 6 M18.5 6.5a7.5 7.5 0 0 1 0 11" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M3 17l6-6 4 4 8-8 M15 7h6v6" },
    ],
  },
  support: {
    base: "#E8EBEE",
    mesh: ["#D9DEE3", "#D6E2E4", "#E6E2D8"],
    stroke: "#CED6DC",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7v5l3 2" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M4 14v-2a8 8 0 0 1 16 0v2 M4 14h3v5H4z M17 14h3v5h-3z" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M4 5h16v11H9l-5 4z M8 9h8 M8 12h5" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M8 12l3 3 5-6" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M3 7h18v4a2 2 0 0 0 0 4v4H3v-4a2 2 0 0 0 0-4z" },
    ],
  },
  customer_success: {
    base: "#E5EDE9",
    mesh: ["#CBDDD4", "#D8E6E1", "#E9E2D2"],
    stroke: "#C6DAD3",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M3 17l6-6 4 4 8-8 M15 7h6v6" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M8 12l3 3 5-6" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M12 11a4 4 0 1 0 0-8a4 4 0 1 0 0 8z M4 21c0-4 3.6-7 8-7s8 3 8 7" },
    ],
  },
  operations: {
    base: "#F1ECE0",
    mesh: ["#E6D6B6", "#E9E1CC", "#DDE2E3"],
    stroke: "#E3D3B2",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7v5l3 2" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M12 3l8 4.5v9L12 21l-8-4.5v-9z M4 7.5l8 4.5 8-4.5 M12 12v9" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M8 12l3 3 5-6" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M9 6h11 M9 12h11 M9 18h11 M4 6l1 1 2-2 M4 12l1 1 2-2 M4 18l1 1 2-2" },
    ],
  },
  hr: {
    base: "#F2E8E7",
    mesh: ["#E8D2CF", "#EADCE3", "#E9E2D6"],
    stroke: "#E7CFD6",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M8 12l3 3 5-6" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M6 3h12v18H6z M9 3v3h6V3 M12 10a2 2 0 1 0 0 4a2 2 0 1 0 0-4z M9 18h6" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M9 11a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M16 11a3 3 0 1 0 0-6 M21 20c0-3-2-5.5-5-6" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M4 5h16v15H4z M4 10h16 M9 3v4 M15 3v4" },
    ],
  },
  engineering: {
    base: "#ECEBE6",
    mesh: ["#DEDAD0", "#D9DEE3", "#E4E1D8"],
    stroke: "#D6D3CB",
    marks: [
      { x: 600, y: 6, scale: 7, opacity: 0.8, width: 5, d: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7v5l3 2" },
      { x: 776, y: 30, scale: 6.5, opacity: 0.8, width: 5, d: "M3 5h18v14H3z M7 10l3 2-3 2 M12 15h5" },
      { x: 956, y: -30, scale: 12, opacity: 1, width: 7, d: "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16" },
      { x: 1196, y: 6, scale: 4, opacity: 0.8, width: 4, d: "M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15z M10 20a2 2 0 0 0 4 0" },
      { x: 1226, y: 92, scale: 5, opacity: 0.8, width: 4, d: "M6 3v12 M18 9a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M6 21a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M18 9a9 9 0 0 1-9 9" },
    ],
  },
}

/** The loose rings drawn on every cover that has no companions of its own. */
export const COVER_RINGS = [
  { cx: 720, cy: 140, r: 9 },
  { cx: 880, cy: 20, r: 12 },
  { cx: 1172, cy: 150, r: 16 },
] as const

const SHIELD = "M12 3l7 3v5c0 4.4-3 8.3-7 10-4-1.7-7-5.6-7-10V6z M9 12l2 2 4-4"
const BOT = "M8 8h8a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3z M12 5.5v2.5 M12 2.6v.01 M9.5 13.5h.01 M14.5 13.5h.01"

export const IDENTITY_DEPARTMENTS: Record<IdentityDepartmentId, IdentityDepartment> = {
  sales: {
    id: "sales",
    label: "Sales",
    color: "#5B5BD6",
    icon: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2z",
    cover: COVERS.sales,
  },
  marketing: {
    id: "marketing",
    label: "Marketing",
    color: "#A5563C",
    icon: "M3 10v4h3l7 4V6L6 10z M16 9a4 4 0 0 1 0 6 M18.5 6.5a7.5 7.5 0 0 1 0 11",
    cover: COVERS.marketing,
  },
  support: {
    id: "support",
    label: "Support",
    color: "#4D6472",
    icon: "M4 5h16v11H9l-5 4z M8 9h8 M8 12h5",
    cover: COVERS.support,
  },
  customer_success: {
    id: "customer_success",
    label: "Customer Success",
    color: "#1F7A6E",
    icon: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z",
    cover: COVERS.customer_success,
  },
  finance: {
    id: "finance",
    label: "Finance",
    color: "#4E7350",
    icon: "M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M8 6h8v3.5H8z M8.5 13h1 M11.5 13h1 M14.5 13h1 M8.5 16.5h1 M11.5 16.5h1 M14.5 16.5h1",
    cover: COVERS.finance,
  },
  operations: {
    id: "operations",
    label: "Operations",
    color: "#8A5A06",
    icon: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1",
    cover: COVERS.operations,
  },
  hr: {
    id: "hr",
    label: "HR",
    color: "#9C4668",
    icon: "M9 11a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M16 11a3 3 0 1 0 0-6 M21 20c0-3-2-5.5-5-6",
    cover: COVERS.hr,
  },
  engineering: {
    id: "engineering",
    label: "Engineering",
    color: "#33342F",
    icon: "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16",
    cover: COVERS.engineering,
  },
  // Security and General are agent departments the designs do not cover yet:
  // they borrow the neutral Engineering ground and keep their own icon.
  security: {
    id: "security",
    label: "Security",
    color: "#A3333D",
    icon: SHIELD,
    cover: { ...COVERS.engineering, marks: COVERS.engineering.marks.map((mark, index) => (index === 2 ? { ...mark, d: SHIELD } : mark)) },
  },
  general: {
    id: "general",
    label: "General",
    color: "#55564F",
    icon: BOT,
    cover: COVERS.engineering,
  },
}

/** Order the department filter and the identity dialog list them in. */
export const IDENTITY_DEPARTMENT_ORDER: IdentityDepartmentId[] = [
  "sales",
  "marketing",
  "support",
  "customer_success",
  "finance",
  "operations",
  "hr",
  "engineering",
]

/**
 * Resolve a department label from the API ("Customer Success", "support",
 * "People Ops") to its identity. Unlike the roster lanes, Support and HR keep
 * their own identity here. A missing department reads as General.
 */
export function identityDepartmentFor(department: string | null | undefined): IdentityDepartment {
  const raw = String(department ?? "").trim()
  if (!raw) return IDENTITY_DEPARTMENTS.general
  const key = raw.toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ")
  if (key in IDENTITY_DEPARTMENTS) return IDENTITY_DEPARTMENTS[key as IdentityDepartmentId]
  if (key === "customer success") return IDENTITY_DEPARTMENTS.customer_success
  if (key === "it") return IDENTITY_DEPARTMENTS.operations
  if (key.includes("support") || key.includes("helpdesk") || key.includes("service desk")) return IDENTITY_DEPARTMENTS.support
  if (key === "hr" || key.includes("human resource") || key.includes("people") || key.includes("talent") || key.includes("recruit")) {
    return IDENTITY_DEPARTMENTS.hr
  }
  if (key === "general") return IDENTITY_DEPARTMENTS.general
  return IDENTITY_DEPARTMENTS[mapApiDepartmentToFleet(raw).id]
}

const KIND_BY_ASSET_TYPE: Record<string, ListingKind> = {
  ai_agent: "agent",
  workflow: "workflow",
  play: "workflow",
  knowledge_pack: "knowledge",
  dataset_pack: "knowledge",
  connector_config: "connector",
  department_pack: "pack",
  outcome_pack: "pack",
  dashboard_pack: "pack",
  capability_package: "pack",
}

export function listingKindFor(assetType: string | null | undefined): ListingKind {
  return KIND_BY_ASSET_TYPE[String(assetType ?? "")] ?? "pack"
}

export const LISTING_KINDS: Record<ListingKind, { label: string; icon: string }> = {
  agent: { label: "Agent", icon: "M8 8h8a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3z M12 5.5v2.5 M12 2.6v.01 M9.5 13.5h.01 M14.5 13.5h.01" },
  workflow: { label: "Workflow", icon: "M3 3h6v6H3z M15 15h6v6h-6z M9 6h4a2 2 0 0 1 2 2v7" },
  knowledge: { label: "Knowledge", icon: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z M4 19V5 M9 8h6 M9 11.5h4" },
  pack: { label: "Pack", icon: "M12 3l8 4.5v9L12 21l-8-4.5v-9z M4 7.5l8 4.5 8-4.5 M12 12v9" },
  connector: { label: "Connector", icon: "M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0z M12 17v4" },
}
