/** Reject malformed rows rather than silently importing a subset of a user's material. */
export function parseTrainingExamples(text: string) {
  const records: { input: string; expected_output: string }[] = []
  const invalidLines: number[] = []
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trim()
    if (!line) return
    const separator = line.includes("\t") ? /\t/ : /\s+(?:=>|→)\s+/
    const parts = line.split(separator)
    const input = parts.shift()?.trim() ?? ""
    const expected_output = parts
      .join(line.includes("\t") ? "\t" : " => ")
      .trim()
    if (!input || !expected_output) invalidLines.push(index + 1)
    else records.push({ input, expected_output })
  })
  return { records, invalidLines }
}

export function reportedTrainingProgress(value: unknown): number | null {
  return typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0 &&
    value <= 100
    ? value
    : null
}
