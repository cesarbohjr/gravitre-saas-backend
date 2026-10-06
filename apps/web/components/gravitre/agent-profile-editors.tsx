"use client"

import { useMemo, useRef, useState } from "react"
import { mutate as globalMutate } from "swr"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { AgentPersonalitySection } from "@/components/gravitre/agent-personality-section"
import { AgentCapabilitiesEditor } from "@/components/gravitre/agent-capabilities-editor"
import { agentsApi } from "@/lib/api"
import {
  capabilityIdsFromNames,
  customCapabilityNames,
  capabilityNamesFromIds,
  guardrailIdsFromNames,
  guardrailNamesFromIds,
  normalizeMaxActionsPerHour,
} from "@/lib/agent-config-catalog"
import { agentSystemKeys } from "@/lib/agent-connected-apps"
import {
  DEFAULT_AGENT_RESPONSE_STYLE,
  normalizeAgentResponseStyle,
} from "@/lib/agent-response-style"
import { canConfigureVoice } from "@/lib/seat-entitlements"
import { useViewModeSafe } from "@/lib/view-mode-context"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import type { Agent, AgentVoiceProfile } from "@/types/api"

type AgentPersonalityEditorCardProps = {
  agent: Agent
  onSaved?: (agent: Agent) => void
}

export function AgentPersonalityEditorCard(
  props: AgentPersonalityEditorCardProps,
) {
  return <PersonalityForm key={props.agent.id} {...props} />
}

function PersonalityForm({
  agent: incomingAgent,
  onSaved,
}: AgentPersonalityEditorCardProps) {
  const [agent, setSavedAgent] = useState(incomingAgent)
  const { isLite } = useViewModeSafe()
  const { data: liteMembership } = useSWR<{
    is_lite?: boolean
    is_full_seat?: boolean
    is_admin?: boolean
    is_department_manager?: boolean
  }>("/api/settings/lite-membership", apiFetcher, { revalidateOnFocus: false })
  const showVoiceConfigure = canConfigureVoice({
    is_lite: liteMembership?.is_lite ?? isLite,
    is_full_seat: liteMembership?.is_full_seat,
    is_admin: liteMembership?.is_admin,
    is_department_manager: liteMembership?.is_department_manager,
  })

  const [voiceProfile, setVoiceProfile] = useState<AgentVoiceProfile>(
    () =>
      agent.voiceProfile ?? {
        tts_model: "eleven_flash_v2_5",
        turn_sensitivity: "normal",
        language: "en",
      },
  )
  const [responseStyle, setResponseStyle] = useState(() =>
    normalizeAgentResponseStyle(
      agent.responseStyle ?? DEFAULT_AGENT_RESPONSE_STYLE,
    ),
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const busy = useRef(false)

  const handleSave = async () => {
    if (busy.current || !dirty) return
    busy.current = true
    setError(null)
    setSaving(true)
    try {
      const updated = await agentsApi.update(agent.id, {
        ...(showVoiceConfigure ? { voiceProfile } : {}),
        responseStyle,
      } as Partial<Agent>)
      setSavedAgent(updated)
      toast.success("Personality saved")
      await Promise.allSettled([
        globalMutate("/api/agents"),
        globalMutate(`agent-profile/${agent.id}`),
        globalMutate(`agent/${agent.id}`),
        globalMutate(`agent/${agent.id}/capabilities`),
      ])
      onSaved?.(updated)
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Failed to save personality",
      )
    } finally {
      setSaving(false)
      busy.current = false
    }
  }

  const savedStyle = normalizeAgentResponseStyle(
    agent.responseStyle ?? DEFAULT_AGENT_RESPONSE_STYLE,
  )
  const savedVoice = agent.voiceProfile ?? {
    tts_model: "eleven_flash_v2_5",
    turn_sensitivity: "normal",
    language: "en",
  }
  const dirty =
    responseStyle !== savedStyle ||
    (showVoiceConfigure &&
      JSON.stringify(voiceProfile) !== JSON.stringify(savedVoice))

  return (
    <div className="space-y-6">
      <fieldset disabled={saving} className="min-w-0">
        <AgentPersonalitySection
          voiceProfile={voiceProfile}
          onVoiceProfileChange={setVoiceProfile}
          responseStyle={responseStyle}
          onResponseStyleChange={setResponseStyle}
          department={agent.department}
          showVoiceConfigure={showVoiceConfigure}
        />
      </fieldset>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap items-center justify-end gap-3 border-t border-[color:var(--g-border-subtle)] pt-4">
        <span
          aria-live="polite"
          className="mr-auto text-xs text-muted-foreground"
        >
          {dirty ? "Unsaved changes" : "All changes saved"}
        </span>
        {dirty ? (
          <Button
            type="button"
            className="min-h-11"
            variant="ghost"
            onClick={() => {
              setVoiceProfile(savedVoice)
              setResponseStyle(savedStyle)
            }}
            disabled={saving}
          >
            Discard
          </Button>
        ) : null}
        <Button
          className="min-h-11"
          type="button"
          onClick={() => void handleSave()}
          disabled={saving || !dirty}
        >
          {saving ? "Saving…" : "Save personality"}
        </Button>
      </div>
    </div>
  )
}

type AgentCapabilitiesEditorCardProps = {
  agent: Agent
  onSaved?: (agent: Agent) => void
}

export function AgentCapabilitiesEditorCard(
  props: AgentCapabilitiesEditorCardProps,
) {
  return <CapabilityForm key={props.agent.id} {...props} />
}

function CapabilityForm({
  agent: incomingAgent,
  onSaved,
}: AgentCapabilitiesEditorCardProps) {
  const [agent, setSavedAgent] = useState(incomingAgent)
  const initialCapabilityIds = useMemo(
    () => capabilityIdsFromNames(agent.capabilities ?? []),
    [agent.capabilities],
  )
  const initialCustom = useMemo(
    () => customCapabilityNames(agent.capabilities ?? []),
    [agent.capabilities],
  )
  const initialSystems = useMemo(
    () => agentSystemKeys(agent.permissions ?? []),
    [agent.permissions],
  )
  const initialGuardrails = useMemo(
    () => guardrailIdsFromNames(agent.guardrails ?? []),
    [agent.guardrails],
  )

  const [capabilityIds, setCapabilityIds] = useState(initialCapabilityIds)
  const [customCapabilities, setCustomCapabilities] = useState(initialCustom)
  const [systemIds, setSystemIds] = useState(initialSystems)
  const [guardrailIds, setGuardrailIds] = useState(initialGuardrails)
  const initialMaxPerHour = normalizeMaxActionsPerHour(agent.guardrailLimits?.maxActionsPerHour)
  const [maxActionsPerHour, setMaxActionsPerHour] = useState(initialMaxPerHour)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const busy = useRef(false)
  const dirty =
    JSON.stringify([...capabilityIds].sort()) !==
      JSON.stringify([...initialCapabilityIds].sort()) ||
    JSON.stringify([...customCapabilities].sort()) !==
      JSON.stringify([...initialCustom].sort()) ||
    JSON.stringify([...systemIds].sort()) !==
      JSON.stringify([...initialSystems].sort()) ||
    JSON.stringify([...guardrailIds].sort()) !==
      JSON.stringify([...initialGuardrails].sort()) ||
    maxActionsPerHour !== initialMaxPerHour

  const handleSave = async () => {
    if (busy.current || !dirty) return
    busy.current = true
    setError(null)
    setSaving(true)
    try {
      const updated = await agentsApi.update(agent.id, {
        capabilities: capabilityNamesFromIds(capabilityIds, customCapabilities),
        // Integration keys, so tool scoping matches the registry; empty means every connected app.
        permissions: systemIds,
        systems: systemIds,
        guardrails: [
          ...guardrailNamesFromIds(guardrailIds),
          ...(agent.guardrails ?? []).filter(
            (name) => !guardrailIdsFromNames([name]).length,
          ),
        ],
        guardrailLimits: { maxActionsPerHour },
      } as Partial<Agent> & { systems?: string[] })
      setSavedAgent(updated)
      toast.success("Capabilities saved")
      await Promise.allSettled([
        globalMutate("/api/agents"),
        globalMutate(`agent-profile/${agent.id}`),
        globalMutate(`agent/${agent.id}`),
        globalMutate(`agent/${agent.id}/capabilities`),
      ])
      onSaved?.(updated)
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Failed to save capabilities",
      )
    } finally {
      setSaving(false)
      busy.current = false
    }
  }

  return (
    <div className="space-y-6">
      <fieldset disabled={saving} className="min-w-0">
        <AgentCapabilitiesEditor
          capabilityIds={capabilityIds}
          customCapabilities={customCapabilities}
          systemIds={systemIds}
          guardrailIds={guardrailIds}
          onCapabilityIdsChange={setCapabilityIds}
          onCustomCapabilitiesChange={setCustomCapabilities}
          onSystemIdsChange={setSystemIds}
          onGuardrailIdsChange={setGuardrailIds}
          maxActionsPerHour={maxActionsPerHour}
          onMaxActionsPerHourChange={setMaxActionsPerHour}
          knowledgeHref={`/agents/${agent.id}/knowledge`}
        />
      </fieldset>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      {(agent.guardrails ?? []).filter(
        (name) => !guardrailIdsFromNames([name]).length,
      ).length ? (
        <p className="break-words text-xs text-muted-foreground">
          Other guardrails retained:{" "}
          {(agent.guardrails ?? [])
            .filter((name) => !guardrailIdsFromNames([name]).length)
            .join(", ")}
        </p>
      ) : null}
      <p className="text-xs text-muted-foreground">
        The apps you pick decide which connector tools this agent can call.
        Existing non-catalog guardrail labels are preserved.
      </p>
      <div className="flex flex-wrap items-center justify-end gap-3">
        <span
          aria-live="polite"
          className="mr-auto text-xs text-muted-foreground"
        >
          {dirty ? "Unsaved changes" : "All changes saved"}
        </span>
        {dirty ? (
          <Button
            className="min-h-11"
            variant="ghost"
            disabled={saving}
            onClick={() => {
              setCapabilityIds(initialCapabilityIds)
              setCustomCapabilities(initialCustom)
              setSystemIds(initialSystems)
              setGuardrailIds(initialGuardrails)
              setMaxActionsPerHour(initialMaxPerHour)
              setError(null)
            }}
          >
            Discard
          </Button>
        ) : null}
        <Button
          className="min-h-11"
          type="button"
          onClick={() => void handleSave()}
          disabled={saving || !dirty}
        >
          {saving ? "Saving…" : "Save capabilities"}
        </Button>
      </div>
    </div>
  )
}
