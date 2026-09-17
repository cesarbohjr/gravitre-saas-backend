/**
 * Canonical per-turn product focus for the authenticated AI transport.
 * Agent scope stays `agent_id` on the request root — not duplicated here.
 */

export type WorkspaceFocusObjectType =
  | "entity"
  | "agent"
  | "workflow"
  | "run"
  | "connector"
  | "relationship"
  | "department"
  | "signal"
  | "customer"
  | "company"
  | "contact"
  | "product"

export type WorkspaceFocusSelection = {
  object_type: string
  object_id: string
  label?: string | null
}

export type WorkspaceFocusPayload = {
  surface?: string | null
  route?: string | null
  selection?: WorkspaceFocusSelection | null
}

export function buildWorkspaceFocusPayload(args: {
  surface: string
  route: string
  selected?: { kind: string; id: string; label?: string } | null
}): WorkspaceFocusPayload | undefined {
  const route = args.route.trim()
  const surface = args.surface.trim()
  const selected = args.selected
  const selection =
    selected?.id && selected.kind
      ? {
          object_type: selected.kind,
          object_id: selected.id,
          label: selected.label?.trim() || null,
        }
      : undefined
  if (!route && !selection) return undefined
  return {
    surface: surface || null,
    route: route || null,
    selection: selection ?? null,
  }
}
