"use client"

import { useState } from "react"

/**
 * TEMPORARY capture utility — delete after refreshing product screenshots.
 * See app/api/e2e-shot-upload/route.ts for why this exists.
 */
export default function ShotUploadPage() {
  const [result, setResult] = useState("idle")

  async function onChange(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? [])
    if (files.length === 0) return

    const body = new FormData()
    for (const file of files) body.append("files", file)

    setResult("uploading")
    const res = await fetch("/api/e2e-shot-upload", { method: "POST", body })
    const json = await res.json()
    setResult(res.ok ? `done: ${JSON.stringify(json.written)}` : `error: ${JSON.stringify(json)}`)
  }

  return (
    <main style={{ padding: 24, fontFamily: "monospace" }}>
      <input data-testid="shot-input" type="file" accept="image/png" multiple onChange={onChange} />
      <pre data-testid="shot-result">{result}</pre>
    </main>
  )
}
