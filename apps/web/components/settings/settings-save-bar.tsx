"use client"

import { useEffect, useState } from "react"
import { Check, Loader2 } from "lucide-react"

/**
 * Floating "Unsaved changes · Discard · Save changes" bar from the v5 Settings
 * design, and the "Saved" confirmation that replaces it for a moment.
 */
export function SettingsSaveBar({
  dirty,
  saving,
  savedAt,
  onDiscard,
  onSave,
}: {
  dirty: boolean
  saving: boolean
  /** Bump (e.g. Date.now()) after a successful save to show "Saved". */
  savedAt: number | null
  onDiscard: () => void
  onSave: () => void
}) {
  const [showSaved, setShowSaved] = useState(false)
  useEffect(() => {
    if (!savedAt) return
    setShowSaved(true)
    const timer = window.setTimeout(() => setShowSaved(false), 2400)
    return () => window.clearTimeout(timer)
  }, [savedAt])

  if (dirty) {
    return (
      <div role="status" className="st5-bar">
        <span className="msg">
          <span className="dot" aria-hidden />
          Unsaved changes
        </span>
        <button type="button" onClick={onDiscard} disabled={saving}>
          Discard
        </button>
        <button type="button" className="save" onClick={onSave} disabled={saving}>
          {saving ? <Loader2 size={15} className="animate-spin motion-reduce:animate-none" aria-hidden /> : <Check size={15} aria-hidden />}
          {saving ? "Saving..." : "Save changes"}
        </button>
      </div>
    )
  }
  if (showSaved) {
    return (
      <div role="status" className="st5-saved">
        Saved
      </div>
    )
  }
  return null
}
