"use client"

import { useCallback, useEffect, useState } from "react"
import {
  CHAT_BACKGROUND_STORAGE_KEY,
  DEFAULT_CHAT_BACKGROUND,
  isChatBackgroundId,
  type ChatBackgroundId,
} from "@/lib/chat-background-themes"

/**
 * localStorage-backed chat canvas background preference.
 *
 * Starts from the default on the server / first paint to avoid hydration
 * mismatch, then reconciles with the stored value after mount. Writes are
 * mirrored to localStorage and broadcast to other open tabs via the `storage`
 * event so the preference stays in sync everywhere.
 */
export function useChatBackground(): {
  background: ChatBackgroundId
  setBackground: (id: ChatBackgroundId) => void
} {
  const [background, setBackgroundState] = useState<ChatBackgroundId>(DEFAULT_CHAT_BACKGROUND)

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(CHAT_BACKGROUND_STORAGE_KEY)
      if (isChatBackgroundId(stored)) setBackgroundState(stored)
    } catch {
      // Access to localStorage can throw in privacy modes — ignore and keep default.
    }

    const onStorage = (event: StorageEvent) => {
      if (event.key !== CHAT_BACKGROUND_STORAGE_KEY) return
      if (isChatBackgroundId(event.newValue)) setBackgroundState(event.newValue)
    }
    window.addEventListener("storage", onStorage)
    return () => window.removeEventListener("storage", onStorage)
  }, [])

  const setBackground = useCallback((id: ChatBackgroundId) => {
    setBackgroundState(id)
    try {
      window.localStorage.setItem(CHAT_BACKGROUND_STORAGE_KEY, id)
    } catch {
      // Non-fatal — the in-memory preference still applies for this session.
    }
  }, [])

  return { background, setBackground }
}
