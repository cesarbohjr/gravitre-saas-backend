"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { UserRound } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ErrorState } from "@/components/gravitre/empty-state"
import { chatAdminApi } from "@/lib/api"
import { ApiError } from "@/lib/fetcher"
import { DEFAULT_CHAT_PERSONA_KEY, normalizeChatPersonaOptions } from "@/lib/chat-personas"

export function ChatPersonaSettingsCard({ enabled }: { enabled: boolean }) {
  const { data, error, isLoading, mutate } = useSWR(
    enabled ? "admin/chat/personas" : null,
    () => chatAdminApi.personas(),
    { revalidateOnFocus: false },
  )

  const personaOptions = useMemo(
    () => normalizeChatPersonaOptions(data?.personas),
    [data?.personas],
  )

  const [selectedPersona, setSelectedPersona] = useState(DEFAULT_CHAT_PERSONA_KEY)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!data) return
    setSelectedPersona(data.org_default_persona || DEFAULT_CHAT_PERSONA_KEY)
  }, [data])

  if (error) {
    const message = error instanceof ApiError ? error.message : "Failed to load persona settings."
    return <ErrorState title="Unable to load personas" description={message} onRetry={() => mutate()} />
  }

  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">Loading communication personas…</p>
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const result = await chatAdminApi.setDefaultPersona(selectedPersona)
      if (result.status === "error") {
        toast.error(result.message || "Could not save org default persona")
        return
      }
      toast.success("Org default response style saved")
      await mutate()
    } catch (saveError) {
      toast.error(saveError instanceof ApiError ? saveError.message : "Could not save persona settings")
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <UserRound className="h-5 w-5 text-emerald-500" aria-hidden />
          <CardTitle>Default response style</CardTitle>
        </div>
        <CardDescription>
          Choose how Gravitre sounds by default in chat and agent conversations when someone has not set a personal
          preference. Style only. Never overrides approvals or governance.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="org-default-persona">Org default persona</Label>
          <Select value={selectedPersona} onValueChange={setSelectedPersona}>
            <SelectTrigger id="org-default-persona" className="max-w-md">
              <SelectValue placeholder="Select default persona" />
            </SelectTrigger>
            <SelectContent>
              {personaOptions.map((persona) => (
                <SelectItem key={persona.key} value={persona.key}>
                  {persona.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Current org default:{" "}
            <span className="font-medium text-foreground">
              {personaOptions.find((persona) => persona.key === data.org_default_persona)?.label ??
                "Friendly Assistant"}
            </span>
          </p>
        </div>

        <div className="rounded-xl border border-border/70 bg-secondary/20 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Available personas</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-2">
            {personaOptions.map((persona) => (
              <li
                key={persona.key}
                className="rounded-lg border border-border/60 bg-background/70 px-3 py-2 text-sm"
              >
                <p className="font-medium text-foreground">{persona.label}</p>
                <p className="text-xs text-muted-foreground">
                  {[persona.tone, persona.verbosity].filter(Boolean).join(" · ") || "Adaptive tone"}
                </p>
              </li>
            ))}
          </ul>
        </div>

        <Button onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save org default"}
        </Button>
      </CardContent>
    </Card>
  )
}
