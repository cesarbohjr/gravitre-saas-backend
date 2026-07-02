"use client"

import { useCallback, useRef, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { assistantApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { DEFAULT_CHAT_PERSONA_KEY } from "@/lib/chat-personas"

type UsePreferredPersonaOptions = {
  enabled?: boolean
  successMessage?: string
}

export function usePreferredPersona(options: UsePreferredPersonaOptions = {}) {
  const { enabled = true, successMessage = "Response style updated" } = options
  const [preferredPersona, setPreferredPersona] = useState(DEFAULT_CHAT_PERSONA_KEY)
  const preferredPersonaRef = useRef(DEFAULT_CHAT_PERSONA_KEY)

  const syncPersona = useCallback((personaKey: string) => {
    const normalized = personaKey.trim() || DEFAULT_CHAT_PERSONA_KEY
    setPreferredPersona(normalized)
    preferredPersonaRef.current = normalized
  }, [])

  useSWR(enabled ? "assistant-preferences" : null, () => assistantApi.getPreferences(), {
    revalidateOnFocus: false,
    onSuccess: (prefs) => {
      if (prefs?.preferred_persona) {
        syncPersona(prefs.preferred_persona)
      }
    },
  })

  const handlePersonaChange = useCallback(
    async (personaKey: string) => {
      syncPersona(personaKey)
      try {
        await assistantApi.updatePreferences({ preferred_persona: personaKey })
        toast.success(successMessage)
      } catch (error) {
        toast.error(error instanceof ApiError ? error.message : "Could not update response style")
      }
    },
    [successMessage, syncPersona],
  )

  return {
    preferredPersona,
    preferredPersonaRef,
    handlePersonaChange,
    syncPersona,
  }
}
