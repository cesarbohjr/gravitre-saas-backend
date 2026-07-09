import {
  DEFAULT_RESULT_BLOCK_ORDER,
  type LayoutColumn,
  type ResultBlockId,
} from "./draggable-result-stack"

const ORDER_KEY = "gravitre_ai_layout_order"
const ENABLED_KEY = "gravitre_ai_layout_enabled"
const COLUMNS_KEY = "gravitre_ai_layout_columns"

function parseOrder(raw: string | null): ResultBlockId[] {
  if (!raw) return DEFAULT_RESULT_BLOCK_ORDER
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return DEFAULT_RESULT_BLOCK_ORDER
    const allowed = new Set<ResultBlockId>(DEFAULT_RESULT_BLOCK_ORDER)
    const filtered = parsed.filter((id): id is ResultBlockId => typeof id === "string" && allowed.has(id as ResultBlockId))
    const missing = DEFAULT_RESULT_BLOCK_ORDER.filter((id) => !filtered.includes(id))
    return [...filtered, ...missing]
  } catch {
    return DEFAULT_RESULT_BLOCK_ORDER
  }
}

function parseEnabled(raw: string | null): ResultBlockId[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    const allowed = new Set<ResultBlockId>(DEFAULT_RESULT_BLOCK_ORDER)
    return parsed.filter((id): id is ResultBlockId => typeof id === "string" && allowed.has(id as ResultBlockId))
  } catch {
    return []
  }
}

function parseColumns(raw: string | null): Partial<Record<ResultBlockId, LayoutColumn>> {
  if (!raw) return {}
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== "object") return {}
    const next: Partial<Record<ResultBlockId, LayoutColumn>> = {}
    for (const [key, value] of Object.entries(parsed)) {
      if ((value === "main" || value === "rail") && DEFAULT_RESULT_BLOCK_ORDER.includes(key as ResultBlockId)) {
        next[key as ResultBlockId] = value
      }
    }
    return next
  } catch {
    return {}
  }
}

export function loadLayoutOrder(): ResultBlockId[] {
  if (typeof window === "undefined") return DEFAULT_RESULT_BLOCK_ORDER
  return parseOrder(localStorage.getItem(ORDER_KEY))
}

export function loadLayoutEnabled(): ResultBlockId[] {
  if (typeof window === "undefined") return []
  return parseEnabled(localStorage.getItem(ENABLED_KEY))
}

export function loadLayoutColumns(): Partial<Record<ResultBlockId, LayoutColumn>> {
  if (typeof window === "undefined") return {}
  return parseColumns(localStorage.getItem(COLUMNS_KEY))
}

export function persistLayoutOrder(order: ResultBlockId[]) {
  if (typeof window === "undefined") return
  localStorage.setItem(ORDER_KEY, JSON.stringify(order))
}

export function persistLayoutEnabled(enabled: ResultBlockId[]) {
  if (typeof window === "undefined") return
  localStorage.setItem(ENABLED_KEY, JSON.stringify(enabled))
}

export function persistLayoutColumns(columns: Partial<Record<ResultBlockId, LayoutColumn>>) {
  if (typeof window === "undefined") return
  localStorage.setItem(COLUMNS_KEY, JSON.stringify(columns))
}

export function resolveBlockColumn(
  blockId: ResultBlockId,
  columns: Partial<Record<ResultBlockId, LayoutColumn>>,
): LayoutColumn {
  return columns[blockId] ?? "main"
}
