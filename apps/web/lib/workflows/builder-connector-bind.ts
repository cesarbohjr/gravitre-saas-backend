/**
 * Bind workflow builder connector nodes to vendor + action keys
 * (e.g. apollo.lists.create → vendor=apollo, selectedAction=lists.create).
 */

export type ConnectorBind = {
  vendor?: string
  selectedAction?: string
  /** Canonical invoke_tool key, e.g. apollo.lists.create */
  action?: string
}

function nonEmpty(value: unknown): string | undefined {
  const text = String(value ?? "").trim()
  return text || undefined
}

/** Split `apollo.lists.create` into vendor + action id (lists.create). */
export function splitToolAction(toolAction: string): { vendor: string; selectedAction: string } | null {
  const text = String(toolAction || "").trim()
  const dot = text.indexOf(".")
  if (dot <= 0 || dot >= text.length - 1) return null
  return {
    vendor: text.slice(0, dot),
    selectedAction: text.slice(dot + 1),
  }
}

export function compiledConnectorAction(vendor?: string, selectedAction?: string): string | undefined {
  const v = nonEmpty(vendor)
  const a = nonEmpty(selectedAction)
  if (!v || !a) return undefined
  if (a.startsWith(`${v}.`)) return a
  return `${v}.${a}`
}

/** Resolve vendor/action from canvas node fields + step config (marketplace hydrate). */
export function resolveConnectorBind(input: {
  vendor?: string
  selectedAction?: string
  config?: Record<string, unknown> | null
}): ConnectorBind {
  const config = input.config && typeof input.config === "object" ? input.config : {}
  const rawAction =
    nonEmpty(config.tool_action) ||
    nonEmpty(config.action) ||
    compiledConnectorAction(input.vendor, input.selectedAction)

  const fromAction = rawAction ? splitToolAction(rawAction) : null
  const vendor =
    nonEmpty(input.vendor) ||
    nonEmpty(config.vendor) ||
    nonEmpty(config.connector) ||
    fromAction?.vendor
  const selectedAction =
    nonEmpty(input.selectedAction) ||
    nonEmpty(config.selected_action) ||
    nonEmpty(config.selectedAction) ||
    fromAction?.selectedAction

  const action = compiledConnectorAction(vendor, selectedAction) || rawAction
  return { vendor, selectedAction, action }
}

/** Merge bind fields into node.config for save + runtime compile. */
export function connectorConfigWithBind(
  config: Record<string, unknown> | undefined,
  bind: ConnectorBind,
): Record<string, unknown> {
  const next = { ...(config || {}) }
  if (bind.vendor) {
    next.vendor = bind.vendor
    next.connector = bind.vendor
  }
  if (bind.selectedAction) {
    next.selectedAction = bind.selectedAction
    next.selected_action = bind.selectedAction
  }
  if (bind.action) {
    next.action = bind.action
    next.tool_action = bind.action
  }
  return next
}
