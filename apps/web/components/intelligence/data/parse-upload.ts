/**
 * Turn an uploaded file into training material the existing endpoints accept:
 * CSV / JSON / JSONL become example records (input + expected output),
 * text and Markdown become documents. Malformed rows reject the whole file so
 * nothing is imported partially.
 */
import { parseTrainingExamples } from "@/lib/training-journey"

export type ParsedUpload =
  | { kind: "examples"; records: { input: string; expected_output: string }[] }
  | { kind: "documents"; documents: { title: string; content: string }[] }

export const UPLOAD_ACCEPT = ".csv,.json,.jsonl,.txt,.md,.markdown"

const INPUT_KEYS = ["input", "prompt", "question", "instruction", "text"]
const OUTPUT_KEYS = ["expected_output", "output", "completion", "answer", "response", "label"]

function pick(row: Record<string, unknown>, keys: string[]): string {
  const lower = Object.fromEntries(Object.entries(row).map(([k, v]) => [k.toLowerCase().trim(), v]))
  for (const key of keys) {
    const value = lower[key]
    if (typeof value === "string" && value.trim()) return value.trim()
    if (typeof value === "number" || typeof value === "boolean") return String(value)
  }
  return ""
}

function rowsToRecords(rows: Record<string, unknown>[]) {
  const records: { input: string; expected_output: string }[] = []
  const invalid: number[] = []
  rows.forEach((row, index) => {
    const input = pick(row, INPUT_KEYS)
    const expected_output = pick(row, OUTPUT_KEYS)
    if (!input || !expected_output) invalid.push(index + 1)
    else records.push({ input, expected_output })
  })
  if (invalid.length) {
    throw new Error(
      `Rows ${invalid.slice(0, 8).join(", ")}${invalid.length > 8 ? "…" : ""} need an input and an expected output column (for example "input" and "expected_output"). Nothing was imported.`,
    )
  }
  return records
}

/** Minimal RFC 4180 CSV reader (quoted fields, escaped quotes, CRLF). */
export function parseCsv(text: string): string[][] {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ""
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++ }
      else if (ch === '"') quoted = false
      else cell += ch
    } else if (ch === '"') quoted = true
    else if (ch === ",") { row.push(cell); cell = "" }
    else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++
      row.push(cell); cell = ""
      if (row.some((c) => c.trim())) rows.push(row)
      row = []
    } else cell += ch
  }
  row.push(cell)
  if (row.some((c) => c.trim())) rows.push(row)
  return rows
}

export function parseUpload(fileName: string, text: string): ParsedUpload {
  const name = fileName.toLowerCase()
  const body = text.trim()
  if (!body) throw new Error(`${fileName} is empty. Nothing was imported.`)

  if (name.endsWith(".csv")) {
    const [header, ...rest] = parseCsv(body)
    if (!header || rest.length === 0) throw new Error("The CSV needs a header row and at least one example.")
    const rows = rest.map((cells) => Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ""])))
    return { kind: "examples", records: rowsToRecords(rows) }
  }
  if (name.endsWith(".jsonl")) {
    const rows = body.split(/\r?\n/).filter((l) => l.trim()).map((line, index) => {
      try { return JSON.parse(line) as Record<string, unknown> }
      catch { throw new Error(`Line ${index + 1} isn't valid JSON. Nothing was imported.`) }
    })
    return { kind: "examples", records: rowsToRecords(rows) }
  }
  if (name.endsWith(".json")) {
    let parsed: unknown
    try { parsed = JSON.parse(body) } catch { throw new Error("The file isn't valid JSON. Nothing was imported.") }
    const rows = Array.isArray(parsed)
      ? parsed
      : parsed && typeof parsed === "object" && Array.isArray((parsed as Record<string, unknown>).records)
        ? ((parsed as Record<string, unknown>).records as unknown[])
        : null
    if (!rows || rows.length === 0) throw new Error("Use a JSON array of examples, each with an input and an expected output.")
    return { kind: "examples", records: rowsToRecords(rows.filter((r): r is Record<string, unknown> => Boolean(r) && typeof r === "object")) }
  }
  if (/\.(txt|md|markdown)$/.test(name)) {
    // "input => output" lines are examples; anything else is a document.
    const asExamples = parseTrainingExamples(body)
    if (asExamples.records.length > 0 && asExamples.invalidLines.length === 0) {
      return { kind: "examples", records: asExamples.records }
    }
    return { kind: "documents", documents: [{ title: fileName, content: body }] }
  }
  throw new Error("Use a .csv, .json, .jsonl, .txt or .md file.")
}
