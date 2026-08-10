"use client"

import { useEffect, useMemo, useState } from "react"
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
  systemIdsFromNames,
  systemNamesFromIds,
} from "@/lib/agent-config-catalog"
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

export function AgentPersonalityEditorCard({ agent, onSaved }: AgentPersonalityEditorCardProps) {
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
    () => agent.voiceProfile ?? { tts_model: "eleven_flash_v2_5", turn_sensitivity: "normal", language: "en" },
  )
  const [responseStyle, setResponseStyle] = useState(
    () => normalizeAgentResponseStyle(agent.responseStyle ?? DEFAULT_AGENT_RESPONSE_STYLE),
  )
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setVoiceProfile(
      agent.voiceProfile ?? { tts_model: "eleven_flash_v2_5", turn_sensitivity: "normal", language: "en" },
    )
    setResponseStyle(normalizeAgentResponseStyle(agent.responseStyle ?? DEFAULT_AGENT_RESPONSE_STYLE))
  }, [agent.id, agent.voiceProfile, agent.responseStyle])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await agentsApi.update(agent.id, {
        ...(showVoiceConfigure ? { voiceProfile } : {}),
        responseStyle,
      } as Partial<Agent>)
      toast.success("Personality saved")
      await globalMutate("/api/agents")
      await globalMutate(`agent-profile/${agent.id}`)
      onSaved?.(updated)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save personality")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card/50 p-6">
      <AgentPersonalitySection
        voiceProfile={voiceProfile}
        onVoiceProfileChange={setVoiceProfile}
        responseStyle={responseStyle}
        onResponseStyleChange={setResponseStyle}
        department={agent.department}
        showVoiceConfigure={showVoiceConfigure}
      />
      <div className="flex justify-end">
        <Button type="button" onClick={() => void handleSave()} disabled={saving}>
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

export function AgentCapabilitiesEditorCard({ agent, onSaved }: AgentCapabilitiesEditorCardProps) {
  const initialCapabilityIds = useMemo(
    () => capabilityIdsFromNames(agent.capabilities ?? []),
    [agent.capabilities],
  )
  const initialCustom = useMemo(
    () => customCapabilityNames(agent.capabilities ?? []),
    [agent.capabilities],
  )
  const initialSystems = useMemo(
    () => systemIdsFromNames(agent.permissions ?? []),
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
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setCapabilityIds(capabilityIdsFromNames(agent.capabilities ?? []))
    setCustomCapabilities(customCapabilityNames(agent.capabilities ?? []))
    setSystemIds(systemIdsFromNames(agent.permissions ?? []))
    setGuardrailIds(guardrailIdsFromNames(agent.guardrails ?? []))
  }, [agent.id, agent.capabilities, agent.permissions, agent.guardrails])

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await agentsApi.update(agent.id, {
        capabilities: capabilityNamesFromIds(capabilityIds, customCapabilities),
        permissions: systemNamesFromIds(systemIds),
        systems: systemNamesFromIds(systemIds),
        guardrails: guardrailNamesFromIds(guardrailIds),
      } as Partial<Agent> & { systems?: string[] })
      toast.success("Capabilities saved")
      await globalMutate("/api/agents")
      await globalMutate(`agent-profile/${agent.id}`)
      onSaved?.(updated)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save capabilities")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4 rounded-xl border border-border bg-card/50 p-6">
      <AgentCapabilitiesEditor
        capabilityIds={capabilityIds}
        customCapabilities={customCapabilities}
        systemIds={systemIds}
        guardrailIds={guardrailIds}
        onCapabilityIdsChange={setCapabilityIds}
        onCustomCapabilitiesChange={setCustomCapabilities}
        onSystemIdsChange={setSystemIds}
        onGuardrailIdsChange={setGuardrailIds}
        knowledgeHref={`/agents/${agent.id}/knowledge`}
      />
      <div className="flex justify-end">
        <Button type="button" onClick={() => void handleSave()} disabled={saving}>
          {saving ? "Saving…" : "Save capabilities"}
        </Button>
      </div>
    </div>
  )
}
