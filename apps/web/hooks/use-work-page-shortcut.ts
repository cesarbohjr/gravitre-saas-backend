"use client"

import { useEffect } from "react"
import {
  WORK_SHORTCUT_EVENT,
  type WorkShortcutAction,
} from "@/lib/work-page-shortcuts"

export function useWorkPageShortcut(
  action: WorkShortcutAction,
  handler: () => void,
  enabled = true,
) {
  useEffect(() => {
    if (!enabled) return

    const onShortcut = (event: Event) => {
      const detail = (event as CustomEvent<{ action?: WorkShortcutAction }>).detail
      if (detail?.action === action) {
        handler()
      }
    }

    window.addEventListener(WORK_SHORTCUT_EVENT, onShortcut)
    return () => window.removeEventListener(WORK_SHORTCUT_EVENT, onShortcut)
  }, [action, enabled, handler])
}
