"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { NucleoWorkflow } from "@/components/icons/nucleo/semantic"
import {
  ArrowLeft,
  ArrowRight,
  Database,
  Shield,
  Check,
  AlertTriangle,
} from "lucide-react"
import { AgentIdentityAvatar } from "@/components/gravitre/agent-identity-avatar"
import { Illustration } from "@/components/gravitre/illustration"
import { cn } from "@/lib/utils"
import { ModelSelector } from "@/components/gravitre/model-selector"
import { AgentReferenceFoldersEditor } from "@/components/agents/agent-reference-folders-editor"
import {
  AgentKnowledgePacksEditor,
  type KnowledgePackSelection,
} from "@/components/agents/agent-knowledge-packs-editor"
import { formatReferenceFolderBreadcrumb } from "@/lib/agent-reference-folders"
import type { AgentReferenceFolder } from "@/types/api"
import { agentsApi } from "@/lib/api"
import { useConnectedAgentApps } from "@/lib/agent-connected-apps"
import {
  AGENT_DEPARTMENT_OPTIONS,
  inferAgentDepartment,
  normalizeAgentDepartment,
  type AgentDepartment,
} from "@/lib/agent-display"
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
  capabilityNamesFromIds,
  DEFAULT_MAX_ACTIONS_PER_HOUR,
  guardrailNamesFromIds,
} from "@/lib/agent-config-catalog"
import { MaxActionsPerHourInput } from "@/components/gravitre/max-actions-per-hour-input"
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
const guardrailOptions = AGENT_GUARDRAIL_OPTIONS

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
  // ?department=Engineering (from the Agents roster's empty department cards) preselects the team.
  useEffect(() => {
    const requested = new URLSearchParams(window.location.search).get("department")
    if (requested) setSelectedDepartment(normalizeAgentDepartment(requested))
  }, [])
  const [agentModel, setAgentModel] = useState("auto")
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([])
  const [selectedSystems, setSelectedSystems] = useState<string[]>([])
  const [selectedGuardrails, setSelectedGuardrails] = useState<string[]>(["approval-changes", "admin-delete"])
  const [maxActionsPerHour, setMaxActionsPerHour] = useState(DEFAULT_MAX_ACTIONS_PER_HOUR)
  const [referenceFolders, setReferenceFolders] = useState<AgentReferenceFolder[]>([])
  const [knowledgePacks, setKnowledgePacks] = useState<KnowledgePackSelection[]>([])
  const suggestedIdentity = useSuggestedAgentIdentity(agentName, agentPurpose)
  const [selectedIcon, setSelectedIcon] = useState<AgentIconId>(suggestedIdentity.icon)
  const [selectedColor, setSelectedColor] = useState<AgentAvatarColorId>(suggestedIdentity.avatarColor)
  const [voiceProfile, setVoiceProfile] = useState<AgentVoiceProfile>({
    tts_model: "eleven_flash_v2_5",
    turn_sensitivity: "normal",
    language: "en",
  })
  const [responseStyle, setResponseStyle] = useState(DEFAULT_AGENT_RESPONSE_STYLE)
  const [customCapabilities] = useState<string[]>([])
  const {
    apps: availableSystems,
    error: connectorError,
    isLoading: connectorsLoading,
  } = useConnectedAgentApps()

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
      case 3: return true
      case 4: return true
      case 5: return true
      default: return false
    }
  }

  const handleCreate = async () => {
    setIsCreating(true)
    try {
      // Store integration keys so tool scoping matches the registry; empty means every connected app.
      const selectedSystemNames = selectedSystems.filter((id) =>
        availableSystems.some((system) => system.id === id),
      )
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
        ...(selectedGuardrails.includes("rate-limit") ? { guardrailLimits: { maxActionsPerHour } } : {}),
        referenceFolders,
        knowledgePacks,
        status: "active",
      })

      for (const pack of knowledgePacks) {
        try {
          const { buildPackAssignmentPayload } = await import("@/lib/agent-knowledge-assign")
          const { agentKnowledgeApi } = await import("@/lib/api")
          await agentKnowledgeApi.createAssignment(created.id, buildPackAssignmentPayload(pack))
        } catch {
          // Config knowledge_packs still resolve via resolve_assignments when assignment POST fails
        }
      }

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
    <AppShell title="Add team member">
      <div className="flex h-full min-h-0 w-full flex-col bg-[color:var(--g-canvas)]" data-composition="create">
        <GravitrePageHeader
          eyebrow="AI Team"
          title="Add team member"
          description="Configure purpose, skills, apps, and limits for a new agent."
          icon={<NucleoWorkflow className="h-5 w-5" />}
          actions={
            <Button variant="outline" asChild>
              <Link href="/agents" className="gap-1">
                <ArrowLeft className="h-4 w-4" />
                Your AI Team
              </Link>
            </Button>
          }
        />

        {/* Progress Steps */}
        <div className="border-b border-divide px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)]">
          <div className="mx-auto flex max-w-3xl items-center justify-between">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <div className="flex items-center gap-2">
                  <div className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium transition-colors",
                    currentStep === step.id
                      ? "bg-[color:var(--g-emerald)] text-primary-foreground ring-2 ring-[color:var(--g-emerald)]/15"
                      : currentStep > step.id
                        ? "bg-[color:var(--g-emerald-deep)] text-[color:var(--g-bone)]"
                        : "bg-[color:var(--g-surface-2)] text-muted-foreground"
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
                    currentStep > step.id ? "bg-[color:var(--g-brand)]" : "bg-divide"
                  )} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-[var(--np-page-pad-sm)] py-8 sm:px-[var(--np-page-pad)]">
          <div className="mx-auto max-w-2xl">
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
                      {AGENT_DEPARTMENT_OPTIONS.map((dept) => (
                        <option key={dept} value={dept}>
                          {dept}
                        </option>
                      ))}
                    </select>
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      Assign this agent to a team lane on the Agents roster (TEAM / LIST / GRAPH).
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

                  <GravitreSurface>
                    <AgentPersonalitySection
                      voiceProfile={voiceProfile}
                      onVoiceProfileChange={setVoiceProfile}
                      responseStyle={responseStyle}
                      onResponseStyleChange={setResponseStyle}
                      department={selectedDepartment}
                      showVoiceConfigure={showVoiceConfigure}
                    />
                  </GravitreSurface>

                  <AgentIdentityPicker
                    department={selectedDepartment}
                    name={agentName.trim() || "New Agent"}
                    icon={selectedIcon}
                    avatarColor={selectedColor}
                    onIconChange={setSelectedIcon}
                    onColorChange={setSelectedColor}
                    className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] p-4 shadow-[var(--np-shadow)]"
                  />

                  {/* Model Selection */}
                  <div>
                    <label className="text-sm font-medium text-foreground">Default model</label>
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

                <p className="text-sm text-muted-foreground">
                  {selectedSystems.length === 0
                    ? "No apps selected: this agent can use every app your workspace has connected."
                    : "This agent can only use the apps you select, plus Gravitre's own reporting and workflow tools."}
                </p>

                <div className="space-y-3">
                  {connectorsLoading ? (
                    <p className="text-sm text-muted-foreground">Loading connected apps…</p>
                  ) : connectorError ? (
                    <p role="alert" className="text-sm text-destructive">
                      Could not load connected apps. You can continue; the agent will use every connected app.
                    </p>
                  ) : availableSystems.length === 0 ? (
                    <div className="py-2 text-center">
                      <Illustration name="moment-welcome" width={130} className="mx-auto mb-3" />
                      <p className="text-sm text-muted-foreground">
                        No apps are connected yet. Connect one to give this agent tools, or continue and add apps later.
                      </p>
                    </div>
                  ) : null}
                  {availableSystems.map((sys) => {
                    const isSelected = selectedSystems.includes(sys.id)
                    return (
                      <button
                        key={sys.id}
                        type="button"
                        onClick={() => toggleSystem(sys.id)}
                        aria-pressed={isSelected}
                        className={cn(
                          "flex w-full items-center justify-between rounded-lg border p-4 transition-all",
                          isSelected
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
                          {isSelected ? (
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

                <AgentKnowledgePacksEditor
                  value={knowledgePacks}
                  onChange={setKnowledgePacks}
                  department={selectedDepartment}
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

                {selectedGuardrails.includes("rate-limit") ? (
                  <MaxActionsPerHourInput value={maxActionsPerHour} onChange={setMaxActionsPerHour} />
                ) : null}

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

                <div className="rounded-[var(--np-radius-lg)] border border-divide bg-[color:var(--g-surface-1)] shadow-[var(--np-shadow)] divide-y divide-border">
                  {/* Name & Purpose */}
                  <div className="p-5">
                    <p className="text-xs font-medium text-muted-foreground">Name & Purpose</p>
                    <div className="mt-3 flex items-start gap-4">
                      <AgentIdentityAvatar
                        agent={{ name: agentName, icon: selectedIcon, avatarColor: selectedColor, role: agentPurpose, department: selectedDepartment }}
                        size="lg"
                        showStatusDot={false}
                      />
                      <div>
                        <p className="text-lg font-semibold text-foreground">{agentName || "Unnamed Agent"}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{agentPurpose || "No description provided"}</p>
                      </div>
                    </div>
                  </div>

                  <div className="p-5">
                    <p className="text-xs font-medium text-muted-foreground">Team and model</p>
                    <ul className="mt-2 space-y-1 text-sm text-foreground">
                      <li>Department: {selectedDepartment}</li>
                      <li>Default model: {agentModel === "auto" ? "Automatic (workspace default)" : agentModel}</li>
                    </ul>
                  </div>

                  <div className="p-5">
                    <p className="text-xs font-medium text-muted-foreground">Personality</p>
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
                    <p className="text-xs font-medium text-muted-foreground">Capabilities</p>
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
                    <p className="text-xs font-medium text-muted-foreground">Connected systems</p>
                    {selectedSystems.length === 0 ? (
                      <p className="mt-2 text-sm text-muted-foreground">Every connected app</p>
                    ) : null}
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
                    <p className="text-xs font-medium text-muted-foreground">Reference folders</p>
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

                  <div className="p-5">
                    <p className="text-xs font-medium text-muted-foreground">Knowledge packs</p>
                    {knowledgePacks.length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {knowledgePacks.map((pack) => (
                          <li key={pack.id} className="text-sm text-foreground">{pack.name}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-muted-foreground">No knowledge packs assigned.</p>
                    )}
                  </div>

                  {/* Safety Rules */}
                  <div className="p-5">
                    <p className="text-xs font-medium text-muted-foreground">Safety rules</p>
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
        <div className="border-t border-divide px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)]">
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
                    Create team member
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
