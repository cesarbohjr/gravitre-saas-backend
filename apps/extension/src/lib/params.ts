import type { EnrichResult, Extracted } from "./types"

/**
 * Build the staged parameters for a write action.
 *
 * Ported verbatim from the previous content/shared.js. This is business logic,
 * not presentation: the shapes here have to match what each connector's action
 * expects, so the redesign must not "tidy" them. Only the types are new.
 */
export function buildParamsForAction(
  action: string,
  extracted: Extracted,
  enrichResult: EnrichResult,
): Record<string, unknown> {
  const email = extracted.email || ""
  const first = extracted.firstName || (extracted.fullName || "").split(/\s+/)[0] || ""
  const last =
    extracted.lastName || (extracted.fullName || "").split(/\s+/).slice(1).join(" ") || ""

  if (action === "apollo.contacts.create") {
    return {
      first_name: first || "Unknown",
      last_name: last || "Contact",
      email: email || undefined,
      organization_name: extracted.company || undefined,
    }
  }

  if (action === "apollo.lists.create") {
    return {
      name: extracted.company
        ? `${extracted.company} — Extension`
        : `Extension list ${new Date().toISOString().slice(0, 10)}`,
      modality: "contacts",
    }
  }

  if (action === "apollo.lists.add") {
    const match = (enrichResult.matches || []).find(
      (m) => m.action === "apollo.people.match" && m.success,
    )
    const data = (match?.data || {}) as Record<string, any>
    const person = data.person || data.contact || data
    const id = person.id || person.contact_id || data.primary_contact_id
    return {
      entity_ids: id ? [String(id)] : [],
      label_names: ["Extension Prospects"],
      modality: "contacts",
    }
  }

  if (action === "hubspot.contacts.create") {
    return {
      properties: {
        email: email || undefined,
        firstname: first || undefined,
        lastname: last || "Contact",
        company: extracted.company || undefined,
        jobtitle: extracted.title || undefined,
      },
    }
  }

  if (action === "hubspot.lists.create") {
    return {
      name: extracted.company
        ? `${extracted.company} — Extension`
        : `Extension list ${new Date().toISOString().slice(0, 10)}`,
    }
  }

  if (action === "hubspot.lists.add_contact") {
    return { list_id: "", contact_id: "" }
  }

  return {}
}

/** "hubspot.contacts.create" -> "hubspot" (for connector attribution). */
export function connectorOf(action: string): string {
  return action.split(".")[0] || "gravitre"
}

/**
 * Whether an action removes or overwrites data, so the approval step can style
 * itself as destructive rather than as a routine create.
 */
export function isDestructiveAction(action: string): boolean {
  return /\.(delete|remove|archive|destroy)\b/.test(action)
}

/** Flatten nested staged params into readable "label / value" rows. */
export function flattenParams(
  params: Record<string, unknown>,
  prefix = "",
): Array<{ key: string; value: string }> {
  const rows: Array<{ key: string; value: string }> = []
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    const label = prefix ? `${prefix}.${key}` : key
    if (Array.isArray(value)) {
      if (value.length) rows.push({ key: label, value: value.join(", ") })
      continue
    }
    if (typeof value === "object") {
      rows.push(...flattenParams(value as Record<string, unknown>, label))
      continue
    }
    rows.push({ key: label, value: String(value) })
  }
  return rows
}

/** "properties.firstname" -> "Firstname"; "list_id" -> "List id". */
export function humanizeKey(key: string): string {
  const last = key.split(".").pop() || key
  const spaced = last.replace(/_/g, " ")
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}
