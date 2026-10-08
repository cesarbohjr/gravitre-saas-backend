"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import useSWR from "swr"
import { UserRound } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
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
import {
  DEFAULT_CHAT_PERSONA_KEY,
  normalizeChatPersonaOptions,
} from "@/lib/chat-personas"

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

  const [selectedPersona, setSelectedPersona] = useState(
    DEFAULT_CHAT_PERSONA_KEY,
  )
  const lock = useRef(false)
  const dirty = useRef(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!data || dirty.current || lock.current) return
    setSelectedPersona(data.org_default_persona || DEFAULT_CHAT_PERSONA_KEY)
  }, [data])

  if (error && !data) {
    const message =
      error instanceof ApiError
        ? error.message
        : "Failed to load persona settings."
    return (
      <ErrorState
        title="Unable to load personas"
        description={message}
        onRetry={() => mutate()}
      />
    )
  }

  if ((isLoading && !data) || !data) {
    return (
      <p className="text-sm text-muted-foreground">
        Loading communication personas…
      </p>
    )
  }

  const handleSave = async () => {
    if (lock.current) return
    lock.current = true
    setFailure(null)
    setSaving(true)
    try {
      const result = await chatAdminApi.setDefaultPersona(selectedPersona)
      if (result.status === "error") {
        setFailure(result.message || "Could not save org default persona")
        return
      }
      toast.success("Org default response style saved")
      dirty.current = false
      await Promise.allSettled([mutate()])
    } catch (saveError) {
      setFailure(
        saveError instanceof Error
          ? saveError.message
          : "Could not save persona settings. Your selection is retained.",
      )
    } finally {
      lock.current = false
      setSaving(false)
    }
  }

  return (
    <Card className="border-0 border-t border-border rounded-none shadow-none [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11">
      <CardHeader>
        <div className="flex items-center gap-2">
          <UserRound
            className="h-5 w-5 text-[color:var(--g-emerald-deep)]"
            aria-hidden
          />
          <CardTitle>Default response style</CardTitle>
        </div>
        <CardDescription>
          Choose how Gravitre sounds by default in chat and agent conversations
          when someone has not set a personal preference. Style only. Never
          overrides approvals or governance.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <fieldset disabled={saving} className="min-w-0 space-y-5">
          <div className="space-y-2">
            <Label htmlFor="org-default-persona">Org default persona</Label>
            <Select
              value={selectedPersona}
              disabled={saving}
              onValueChange={(value) => {
                dirty.current = true
                setSelectedPersona(value)
              }}
            >
              <SelectTrigger
                id="org-default-persona"
                className="min-h-11 max-w-md"
              >
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
                {personaOptions.find(
                  (persona) => persona.key === data.org_default_persona,
                )?.label ?? "Not reported"}
              </span>
            </p>
          </div>

          <details className="border-t border-divide py-3">
            <summary className="min-h-11 cursor-pointer py-3 text-sm">
              Explore response styles
            </summary>

            <ul className="mt-3 grid gap-2 sm:grid-cols-2">
              {personaOptions.map((persona) => (
                <li
                  key={persona.key}
                  className="rounded-[8px] border border-divide bg-[color:var(--g-surface-1)] px-3 py-2 text-sm"
                >
                  <p className="font-medium text-foreground">{persona.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {[persona.tone, persona.verbosity]
                      .filter(Boolean)
                      .join(" · ") || "Adaptive tone"}
                  </p>
                </li>
              ))}
            </ul>
          </details>
        </fieldset>
        {error ? (
          <ErrorState
            title="Could not refresh settings"
            description="Your draft is retained."
            onRetry={() => mutate()}
          />
        ) : null}
        {failure ? (
          <p role="alert" className="text-sm text-destructive">
            {failure}
          </p>
        ) : null}
        <Button onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save org default"}
        </Button>
      </CardContent>
    </Card>
  )
}
