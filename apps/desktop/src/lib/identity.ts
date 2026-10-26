/**
 * Agent identity: the same department color and icon the web app uses for
 * every agent (apps/web/lib/listing-identity.ts, which imports web-only
 * modules, so the table is copied here).
 */
import type { Agent } from "./api"

export type Department = { id: string; label: string; color: string; icon: string }

const SHIELD = "M12 3l7 3v5c0 4.4-3 8.3-7 10-4-1.7-7-5.6-7-10V6z M9 12l2 2 4-4"
const BOT = "M8 8h8a3 3 0 0 1 3 3v5a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3v-5a3 3 0 0 1 3-3z M12 5.5v2.5 M12 2.6v.01 M9.5 13.5h.01 M14.5 13.5h.01"

export const DEPARTMENTS: Record<string, Department> = {
  sales: { id: "sales", label: "Sales", color: "#5B5BD6", icon: "M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z M12 7a5 5 0 1 0 0 10a5 5 0 1 0 0-10z M12 11a1 1 0 1 0 0 2a1 1 0 1 0 0-2z" },
  marketing: { id: "marketing", label: "Marketing", color: "#A5563C", icon: "M3 10v4h3l7 4V6L6 10z M16 9a4 4 0 0 1 0 6 M18.5 6.5a7.5 7.5 0 0 1 0 11" },
  support: { id: "support", label: "Support", color: "#4D6472", icon: "M4 5h16v11H9l-5 4z M8 9h8 M8 12h5" },
  customer_success: { id: "customer_success", label: "Customer success", color: "#1F7A6E", icon: "M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z" },
  finance: { id: "finance", label: "Finance", color: "#4E7350", icon: "M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M8 6h8v3.5H8z M8.5 13h1 M11.5 13h1 M14.5 13h1 M8.5 16.5h1 M11.5 16.5h1 M14.5 16.5h1" },
  operations: { id: "operations", label: "Operations", color: "#8A5A06", icon: "M12 8a4 4 0 1 0 0 8a4 4 0 1 0 0-8z M12 2v3 M12 19v3 M2 12h3 M19 12h3 M4.9 4.9l2.1 2.1 M17 17l2.1 2.1 M4.9 19.1l2.1-2.1 M17 7l2.1-2.1" },
  hr: { id: "hr", label: "HR", color: "#9C4668", icon: "M9 11a3 3 0 1 0 0-6a3 3 0 1 0 0 6z M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M16 11a3 3 0 1 0 0-6 M21 20c0-3-2-5.5-5-6" },
  engineering: { id: "engineering", label: "Engineering", color: "#33342F", icon: "M8 7l-5 5 5 5 M16 7l5 5-5 5 M14 4l-4 16" },
  security: { id: "security", label: "Security", color: "#A3333D", icon: SHIELD },
  general: { id: "general", label: "General", color: "#55564F", icon: BOT },
}

/** "Customer Success", "customer_success", "Sales Development Rep" → a department. Unknown reads as General. */
export function departmentFor(value: string | null | undefined): Department {
  const key = String(value ?? "").trim().toLowerCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ")
  if (!key) return DEPARTMENTS.general
  if (key.includes("customer success") || key === "cs" || key.includes("renewal") || key.includes("account manag")) return DEPARTMENTS.customer_success
  if (key.includes("support") || key.includes("helpdesk") || key.includes("service desk")) return DEPARTMENTS.support
  if (key.includes("sales") || key.includes("revenue") || key.includes("sdr") || key.includes("bdr")) return DEPARTMENTS.sales
  if (key.includes("market") || key.includes("growth") || key.includes("content")) return DEPARTMENTS.marketing
  if (key.includes("financ") || key.includes("account") || key.includes("billing")) return DEPARTMENTS.finance
  if (key.includes("security") || key.includes("compliance")) return DEPARTMENTS.security
  if (key.includes("engineer") || key.includes("devops") || key.includes("developer")) return DEPARTMENTS.engineering
  if (key === "hr" || key.includes("human resource") || key.includes("people") || key.includes("recruit") || key.includes("talent")) return DEPARTMENTS.hr
  if (key.includes("operation") || key === "ops" || key === "it" || key.includes("revops")) return DEPARTMENTS.operations
  return DEPARTMENTS.general
}

export type AgentIdentity = { name: string; dept: Department }

/** Looks an agent up by id first, then by name; anything unknown is a General agent with that name. */
export function identityOf(agents: Agent[], name: string | null | undefined, id?: string | null): AgentIdentity {
  const hit = (id && agents.find((a) => a.id === id)) || (name && agents.find((a) => a.name.toLowerCase() === name.trim().toLowerCase())) || null
  if (hit) return { name: hit.name, dept: departmentFor(hit.department || hit.role) }
  return { name: (name || "").trim() || "Gravitre", dept: DEPARTMENTS.general }
}
