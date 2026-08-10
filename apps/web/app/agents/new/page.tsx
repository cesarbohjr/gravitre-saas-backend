"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { Button } from "@/components/ui/button"
import {
  ArrowLeft,
  ArrowRight,
  Sparkles,
  Database,
  Shield,
  Check,
  AlertTriangle,
  Megaphone,
  TrendingUp,
  PieChart,
  Headphones,
  Bot,
  type LucideIcon,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ModelSelector } from "@/components/gravitre/model-selector"
import { AgentReferenceFoldersEditor } from "@/components/agents/agent-reference-folders-editor"
import { formatReferenceFolderBreadcrumb } from "@/lib/agent-reference-folders"
import type { AgentReferenceFolder } from "@/types/api"
import { agentsApi } from "@/lib/api"
import { inferAgentDepartment, type AgentDepartment } from "@/lib/agent-display"
import {
  AgentIdentityPicker,
  useSuggestedAgentIdentity,
} from "@/components/gravitre/agent-identity-picker"
import {
  personalityFromAvatarColor,
  type AgentAvatarColorId,
  type AgentIconId,
} from "@/lib/agent-identity"
import { AgentPersonalitySection } from "@/components/gravitre/agent-personality-section"
import { LoadingIndicator } from "@/components/gravitre/gravitre-loader"
import { useViewModeSafe } from "@/lib/view-mode-context"
import { canConfigureVoice } from "@/lib/seat-entitlements"
import useSWR from "swr"
import { fetcher as apiFetcher } from "@/lib/fetcher"
import { mutate as globalMutate } from "swr"
import { toast } from "sonner"
import type { AgentVoiceProfile } from "@/types/api"
import {
  AGENT_CAPABILITY_OPTIONS,
  AGENT_GUARDRAIL_OPTIONS,
  AGENT_SYSTEM_OPTIONS,
  capabilityNamesFromIds,
  guardrailNamesFromIds,
  systemNamesFromIds,
} from "@/lib/agent-config-catalog"
import {
  DEFAULT_AGENT_RESPONSE_STYLE,
  responseStyleLabel,
} from "@/lib/agent-response-style"
import { voiceProfileIsConfigured } from "@/lib/voice-configure-gate"

const steps = [
  { id: 1, name: "Purpose", description: "What should this AI do?" },
  { id: 2, name: "Skills", description: "Choose what it can do" },
  { id: 3, name: "Apps", description: "Connect your apps" },
  { id: 4, name: "Limits", description: "Set safety rules" },
  { id: 5, name: "Review", description: "Review and create" },
]

const suggestedCapabilities = AGENT_CAPABILITY_OPTIONS
const availableSystems = AGENT_SYSTEM_OPTIONS.map((system) => ({
  ...system,
  connected: !["postgresql", "microsoft365"].includes(system.id),
}))
const guardrailOptions = AGENT_GUARDRAIL_OPTIONS

// Map agent names to icons
const agentIconMap: Record<string, LucideIcon> = {
  "Marketing Operator": Megaphone,
  "Sales Assistant": TrendingUp,
  "Data Quality Agent": Database,
  "Finance Reporter": PieChart,
  "Support Coordinator": Headphones,
}

function getAgentIcon(agentName: string): LucideIcon {
  // Check for partial matches
  const lowerName = agentName.toLowerCase()
  if (lowerName.includes("marketing")) return Megaphone
  if (lowerName.includes("sales")) return TrendingUp
  if (lowerName.includes("data") || lowerName.includes("quality")) return Database
  if (lowerName.includes("finance") || lowerName.includes("report")) return PieChart
  if (lowerName.includes("support") || lowerName.includes("customer")) return Headphones
  return agentIconMap[agentName] || Bot
}

const DEPARTMENT_OPTIONS: AgentDepartment[] = [
  "Marketing",
  "Sales",
  "Finance",
  "Support",
  "HR",
  "Operations",
]

export default function NewAgentPage() {
  const router = useRouter()
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
  const [currentStep, setCurrentStep] = useState(1)
  const [isCreating, setIsCreating] = useState(false)
  
  // Form state
  const [agentPurpose, setAgentPurpose] = useState("")
  const [agentName, setAgentName] = useState("")
  const [selectedDepartment, setSelectedDepartment] = useState<AgentDepartment>("Operations")
  const [agentModel, setAgentModel] = useState("auto")
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([])
  const [selectedSystems, setSelectedSystems] = useState<string[]>([])
  const [selectedGuardrails, setSelectedGuardrails] = useState<string[]>(["approval-changes", "admin-delete"])
  const [referenceFolders, setReferenceFolders] = useState<AgentReferenceFolder[]>([])
  const suggestedIdentity = useSuggestedAgentIdentity(agentName, agentPurpose)
  const [selectedIcon, setSelectedIcon] = useState<AgentIconId>(suggestedIdentity.icon)
  const [selectedColor, setSelectedColor] = useState<AgentAvatarColorId>(suggestedIdentity.avatarColor)
  const [voiceProfile, setVoiceProfile] = useState<AgentVoiceProfile>({
    tts_model: "eleven_flash_v2_5",
    turn_sensitivity: "normal",
    language: "en",
  })
  const [responseStyle, setResponseStyle] = useState(DEFAULT_AGENT_RESPONSE_STYLE)
  const [customCapabilities, setCustomCapabilities] = useState<string[]>([])

  const toggleCapability = (id: string) => {
    setSelectedCapabilities(prev =>
      prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
    )
  }

  const toggleSystem = (id: string) => {
    setSelectedSystems(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  const toggleGuardrail = (id: string) => {
    setSelectedGuardrails(prev =>
      prev.includes(id) ? prev.filter(g => g !== id) : [...prev, id]
    )
  }

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return (
          agentPurpose.trim().length > 10 &&
          agentName.trim().length > 0 &&
          (!showVoiceConfigure || voiceProfileIsConfigured(voiceProfile))
        )
      case 2: return selectedCapabilities.length > 0 || customCapabilities.length > 0
      case 3: return selectedSystems.length > 0
      case 4: return true
      case 5: return true
      default: return false
    }
  }

  const handleCreate = async () => {
    setIsCreating(true)
    try {
      const selectedSystemNames = systemNamesFromIds(selectedSystems)
      const selectedCapabilityNames = capabilityNamesFromIds(
        selectedCapabilities,
        customCapabilities,
      )
      const selectedGuardrailNames = guardrailNamesFromIds(selectedGuardrails)

      const trimmedName = agentName.trim()
      const trimmedPurpose = agentPurpose.trim()
      const department = selectedDepartment || inferAgentDepartment(trimmedName, trimmedPurpose, trimmedName)

      const created = await agentsApi.create({
        name: trimmedName,
        purpose: trimmedPurpose,
        role: trimmedName,
        department,
        model: agentModel,
        icon: selectedIcon,
        avatarColor: selectedColor,
        personality: personalityFromAvatarColor(selectedColor),
        ...(showVoiceConfigure ? { voiceProfile } : {}),
        responseStyle,
        capabilities: selectedCapabilityNames,
        systems: selectedSystemNames,
        guardrails: selectedGuardrailNames,
        referenceFolders,
        status: "active",
      })

      toast.success("Agent created")
      await globalMutate("/api/agents")
      router.push(`/agents/${created.id}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to create agent")
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <AppShell title="Add Team Member">
      <div className="flex flex-col h-full">
        {/* Header */}
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center gap-2 text-sm">
            <Link
              href="/agents"
              className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              Your AI Team
            </Link>
            <span className="text-muted-foreground">/</span>
            <span className="text-foreground">Add Team Member</span>
          </div>
        </div>

        {/* Progress Steps */}
        <div className="border-b border-border px-6 py-4">
          <div className="flex items-center justify-between max-w-3xl mx-auto">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors",
                    currentStep === step.id
                      ? "bg-foreground text-background"
                      : currentStep > step.id
                        ? "bg-success text-success-foreground"
                        : "bg-muted text-muted-foreground"
                  )}>
                    {currentStep > step.id ? <Check className="h-4 w-4" /> : step.id}
                  </div>
                  <div className="hidden sm:block">
                    <p className={cn(
                      "text-sm font-medium",
                      currentStep === step.id ? "text-foreground" : "text-muted-foreground"
                    )}>
                      {step.name}
                    </p>
                  </div>
                </div>
                {index < steps.length - 1 && (
                  <div className={cn(
                    "mx-4 h-px w-12 transition-colors",
                    currentStep > step.id ? "bg-success" : "bg-border"
                  )} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-2xl mx-auto">
            {/* Step 1: Purpose */}
            {currentStep === 1 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Name this agent</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    The name is first-class identity — the agent will know and respond to it in text and voice.
                  </p>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="text-sm font-semibold text-foreground">Name <span className="text-destructive">*</span></label>
                    <input
                      type="text"
                      placeholder="e.g., Marketing Operator"
                      value={agentName}
                      onChange={(e) => setAgentName(e.target.value)}
                      required
                      className="mt-1.5 w-full rounded-md border border-border bg-secondary px-4 py-3 text-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-foreground">Department</label>
                    <select
                      value={selectedDepartment}
                      onChange={(e) => setSelectedDepartment(e.target.value as AgentDepartment)}
                      className="mt-1.5 w-full rounded-md border border-border bg-secondary px-4 py-2.5 text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {DEPARTMENT_OPTIONS.map((dept) => (
                        <option key={dept} value={dept}>
                          {dept}
                        </option>
                      ))}
                    </select>
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      Organize agents by team — used in filters, Meson, and reporting.
                    </p>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-foreground">Purpose</label>
                    <textarea
                      placeholder="e.g., Manage marketing campaigns, analyze performance data, and suggest optimizations to improve ROI"
                      value={agentPurpose}
                      onChange={(e) => setAgentPurpose(e.target.value)}
                      rows={4}
                      className="mt-1.5 w-full rounded-md border border-border bg-secondary px-4 py-2.5 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring resize-none"
                    />
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      Be specific about what tasks this agent should handle
                    </p>
                  </div>

                  <div className="rounded-lg border border-border bg-card p-4">
                    <AgentPersonalitySection
                      voiceProfile={voiceProfile}
                      onVoiceProfileChange={setVoiceProfile}
                      responseStyle={responseStyle}
                      onResponseStyleChange={setResponseStyle}
                      department={selectedDepartment}
                      showVoiceConfigure={showVoiceConfigure}
                    />
                  </div>

                  <AgentIdentityPicker
                    name={agentName.trim() || "New Agent"}
                    icon={selectedIcon}
                    avatarColor={selectedColor}
                    onIconChange={setSelectedIcon}
                    onColorChange={setSelectedColor}
                    className="rounded-lg border border-border bg-card p-4"
                  />

                  {/* Model Selection */}
                  <div>
                    <label className="text-sm font-medium text-foreground">Default Model</label>
                    <p className="mt-0.5 text-xs text-muted-foreground mb-2">
                      Choose the AI model that powers this agent&apos;s reasoning
                    </p>
                    <ModelSelector
                      value={agentModel}
                      onChange={setAgentModel}
                      inheritedFrom="workspace"
                      onResetToDefault={() => setAgentModel("auto")}
                      showAdvanced
                    />
                  </div>
                </div>

                <div className="rounded-lg border border-border bg-card p-4">
                  <div className="flex items-start gap-3">
                    <Sparkles className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-foreground">AI will suggest capabilities</p>
                      <p className="text-sm text-muted-foreground">
                        Based on your description, we&apos;ll recommend relevant capabilities and systems
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Capabilities */}
            {currentStep === 2 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Select capabilities</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Choose what this agent can do. You can add more later.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {suggestedCapabilities.map((cap) => {
                    const isSelected = selectedCapabilities.includes(cap.id)
                    return (
                      <button
                        key={cap.id}
                        onClick={() => toggleCapability(cap.id)}
                        className={cn(
                          "flex items-start gap-3 rounded-lg border p-4 text-left transition-all",
                          isSelected
                            ? "border-foreground bg-foreground/5"
                            : "border-border bg-card hover:border-foreground/30"
                        )}
                      >
                        <div className={cn(
                          "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
                          isSelected ? "bg-foreground text-background" : "bg-muted text-muted-foreground"
                        )}>
                          <cap.icon className="h-4 w-4" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">{cap.name}</p>
                          <p className="text-sm text-muted-foreground">{cap.description}</p>
                        </div>
                        {isSelected && (
                          <Check className="h-5 w-5 text-foreground shrink-0 ml-auto" />
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Step 3: Systems */}
            {currentStep === 3 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Connect systems & reference folders</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Select connected apps and link cloud folders this agent should read for department knowledge
                  </p>
                </div>

                <div className="space-y-3">
                  {availableSystems.map((sys) => {
                    const isSelected = selectedSystems.includes(sys.id)
                    return (
                      <button
                        key={sys.id}
                        onClick={() => sys.connected && toggleSystem(sys.id)}
                        disabled={!sys.connected}
                        className={cn(
                          "flex w-full items-center justify-between rounded-lg border p-4 transition-all",
                          !sys.connected
                            ? "border-border bg-card opacity-50 cursor-not-allowed"
                            : isSelected
                              ? "border-foreground bg-foreground/5"
                              : "border-border bg-card hover:border-foreground/30"
                        )}
                      >
                        <div className="flex items-center gap-3">
                          <Database className="h-5 w-5 text-muted-foreground" />
                          <div className="text-left">
                            <p className="font-medium text-foreground">{sys.name}</p>
                            <p className="text-sm text-muted-foreground">{sys.type}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {!sys.connected ? (
                            <span className="text-xs text-muted-foreground">Not connected</span>
                          ) : isSelected ? (
                            <Check className="h-5 w-5 text-foreground" />
                          ) : (
                            <div className="h-5 w-5 rounded border border-border" />
                          )}
                        </div>
                      </button>
                    )
                  })}
                </div>

                <Link
                  href="/connectors"
                  className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                >
                  Manage connected systems
                  <ArrowRight className="h-3 w-3" />
                </Link>

                <AgentReferenceFoldersEditor
                  value={referenceFolders}
                  onChange={setReferenceFolders}
                />
              </div>
            )}

            {/* Step 4: Limits */}
            {currentStep === 4 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Set safety rules</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Choose what this AI can and can&apos;t do on its own
                  </p>
                </div>

                <div className="space-y-3">
                  {guardrailOptions.map((guard) => {
                    const isSelected = selectedGuardrails.includes(guard.id)
                    return (
                      <button
                        key={guard.id}
                        onClick={() => toggleGuardrail(guard.id)}
                        className={cn(
                          "flex w-full items-center justify-between rounded-lg border p-4 transition-all",
                          isSelected
                            ? "border-foreground bg-foreground/5"
                            : "border-border bg-card hover:border-foreground/30"
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <Shield className={cn(
                            "h-5 w-5 shrink-0 mt-0.5",
                            isSelected ? "text-foreground" : "text-muted-foreground"
                          )} />
                          <div className="text-left">
                            <div className="flex items-center gap-2">
                              <p className="font-medium text-foreground">{guard.name}</p>
                              {guard.recommended && (
                                <span className="rounded bg-success/10 px-1.5 py-0.5 text-[10px] font-medium text-success">
                                  Recommended
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-muted-foreground">{guard.description}</p>
                          </div>
                        </div>
                        {isSelected ? (
                          <Check className="h-5 w-5 text-foreground shrink-0" />
                        ) : (
                          <div className="h-5 w-5 rounded border border-border shrink-0" />
                        )}
                      </button>
                    )
                  })}
                </div>

                <div className="rounded-lg border border-warning/50 bg-warning/10 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-foreground">You can change these later</p>
                      <p className="text-sm text-muted-foreground">
                        Adjust the rules anytime as you see how your AI performs
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Step 5: Review */}
            {currentStep === 5 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-semibold text-foreground">Review and create</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Review your new AI team member before adding them
                  </p>
                </div>

                <div className="rounded-lg border border-border bg-card divide-y divide-border">
                  {/* Name & Purpose */}
                  <div className="p-5">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Name & Purpose</p>
                    <div className="mt-3 flex items-start gap-4">
                      {(() => {
                        const AgentIcon = getAgentIcon(agentName)
                        return (
                          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500">
                            <AgentIcon className="h-7 w-7 text-white" />
                          </div>
                        )
                      })()}
                      <div>
                        <p className="text-lg font-semibold text-foreground">{agentName || "Unnamed Agent"}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{agentPurpose || "No description provided"}</p>
                      </div>
                    </div>
                  </div>

                  <div className="p-5">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Personality</p>
                    <ul className="mt-2 space-y-1 text-sm text-foreground">
                      <li>
                        Spoken voice:{" "}
                        {voiceProfileIsConfigured(voiceProfile)
                          ? voiceProfile.voice_key || voiceProfile.voice_id || "Configured"
                          : "Org default (not assigned)"}
                      </li>
                      <li>Response style: {responseStyleLabel(responseStyle)}</li>
                    </ul>
                  </div>

                  {/* Capabilities */}
                  <div className="p-5">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Capabilities</p>
                    <ul className="mt-2 space-y-1">
                      {capabilityNamesFromIds(selectedCapabilities, customCapabilities).map((name) => (
                          <li key={name} className="flex items-center gap-2 text-sm text-foreground">
                            <Check className="h-3.5 w-3.5 text-success" />
                            {name}
                          </li>
                      ))}
                    </ul>
                  </div>

                  {/* Connected Systems */}
                  <div className="p-5">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Connected Systems</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedSystems.map(id => {
                        const sys = availableSystems.find(s => s.id === id)
                        return sys ? (
                          <span key={id} className="rounded bg-secondary px-2 py-1 text-sm text-foreground">
                            {sys.name}
                          </span>
                        ) : null
                      })}
                    </div>
                  </div>

                  {/* Reference Folders */}
                  <div className="p-5">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reference Folders</p>
                    {referenceFolders.length > 0 ? (
                      <ul className="mt-2 space-y-2">
                        {referenceFolders.map((folder) => (
                          <li key={folder.id} className="rounded-md bg-secondary/50 px-3 py-2">
                            <p className="text-sm font-medium text-foreground">{folder.label || folder.folderName}</p>
                            <p className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                              {formatReferenceFolderBreadcrumb(folder)}
                            </p>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">No cloud folders linked yet.</p>
                    )}
                  </div>

                  {/* Safety Rules */}
                  <div className="p-5">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Safety Rules</p>
                    <ul className="mt-2 space-y-1">
                      {selectedGuardrails.map(id => {
                        const guard = guardrailOptions.find(g => g.id === id)
                        return guard ? (
                          <li key={id} className="flex items-center gap-2 text-sm text-foreground">
                            <Shield className="h-3.5 w-3.5 text-muted-foreground" />
                            {guard.name}
                          </li>
                        ) : null
                      })}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border px-6 py-4">
          <div className="flex items-center justify-between max-w-2xl mx-auto">
            <Button
              variant="outline"
              onClick={() => currentStep > 1 ? setCurrentStep(currentStep - 1) : router.push("/agents")}
            >
              {currentStep === 1 ? "Cancel" : "Back"}
            </Button>

            {currentStep < 5 ? (
              <Button
                onClick={() => setCurrentStep(currentStep + 1)}
                disabled={!canProceed()}
                className="gap-2"
              >
                Continue
                <ArrowRight className="h-4 w-4" />
              </Button>
            ) : (
              <Button
                onClick={handleCreate}
                disabled={isCreating}
                className="gap-2"
              >
                {isCreating ? (
                  <>
                    <LoadingIndicator size="xs" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4" />
                    Create Team Member
                  </>
                )}
              </Button>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  )
}
