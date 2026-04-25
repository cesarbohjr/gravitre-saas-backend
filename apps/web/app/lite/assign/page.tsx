"use client"

import { useState, useEffect, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Checkbox } from "@/components/ui/checkbox"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"

// Agents available
const agents = [
  { 
    id: "marketing", 
    name: "Marketing Agent", 
    department: "Marketing",
    capabilities: ["Campaign creation", "Email sequences", "Content writing", "Social posts"],
    status: "online"
  },
  { 
    id: "sales", 
    name: "Sales Agent", 
    department: "Sales",
    capabilities: ["Lead scoring", "Outreach sequences", "Pipeline analysis", "Territory planning"],
    status: "online"
  },
  { 
    id: "analytics", 
    name: "Analytics Agent", 
    department: "Operations",
    capabilities: ["Performance reports", "Data analysis", "Trend identification", "Forecasting"],
    status: "busy"
  },
]

// Output types
const outputTypes = [
  { id: "emails", label: "Email Drafts", icon: "mail", description: "Email sequences and templates" },
  { id: "social", label: "Social Posts", icon: "share", description: "Social media content" },
  { id: "segments", label: "Audience Segments", icon: "users", description: "Targeted audience lists" },
  { id: "reports", label: "Reports", icon: "file", description: "Analysis and insights" },
  { id: "workflows", label: "Workflows", icon: "automations", description: "Automated sequences" },
]

// Delivery destinations with connection status
const destinations = [
  { 
    id: "email", 
    label: "My email", 
    icon: "mail", 
    description: "Send to your inbox",
    connected: true,
    default: true
  },
  { 
    id: "outlook", 
    label: "Outlook", 
    icon: "mail", 
    description: "Push to Outlook inbox",
    connected: true,
    default: false
  },
  { 
    id: "slack", 
    label: "Slack", 
    icon: "message", 
    description: "Post to a channel",
    connected: true,
    channels: ["#marketing", "#sales", "#general"],
    default: false
  },
  { 
    id: "hubspot", 
    label: "HubSpot", 
    icon: "database", 
    description: "Create campaign in CRM",
    connected: true,
    default: false
  },
  { 
    id: "salesforce", 
    label: "Salesforce", 
    icon: "database", 
    description: "Push to Salesforce",
    connected: false,
    default: false
  },
  { 
    id: "download", 
    label: "Download only", 
    icon: "download", 
    description: "Export as file",
    connected: true,
    default: false
  },
]

const steps = [
  { id: 1, title: "Select Agent", description: "Choose your AI worker" },
  { id: 2, title: "Describe Task", description: "What should they do?" },
  { id: 3, title: "Add Details", description: "Provide context" },
  { id: 4, title: "Choose Outputs", description: "What do you need?" },
  { id: 5, title: "Delivery", description: "Where to send it" },
  { id: 6, title: "Review", description: "Confirm and run" },
]

function AssignWorkContent() {
  const searchParams = useSearchParams()
  const [currentStep, setCurrentStep] = useState(1)
  const [mounted, setMounted] = useState(false)
  
  // Form state
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [taskDescription, setTaskDescription] = useState("")
  const [audience, setAudience] = useState("")
  const [goal, setGoal] = useState("")
  const [tone, setTone] = useState("professional")
  const [selectedOutputs, setSelectedOutputs] = useState<string[]>([])
  const [selectedDestinations, setSelectedDestinations] = useState<string[]>(["email"])
  const [slackChannel, setSlackChannel] = useState("#marketing")
  const [requireApproval, setRequireApproval] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Prefill task from URL if provided
    const task = searchParams.get("task")
    if (task) {
      setTaskDescription(task)
      setCurrentStep(2)
    }
  }, [searchParams])

  const canProceed = () => {
    switch (currentStep) {
      case 1: return selectedAgent !== null
      case 2: return taskDescription.trim().length > 10
      case 3: return true // Optional step
      case 4: return selectedOutputs.length > 0
      case 5: return selectedDestinations.length > 0
      case 6: return true
      default: return false
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    // Simulate submission
    await new Promise(resolve => setTimeout(resolve, 1500))
    // Navigate to execution view
    window.location.href = "/lite/tasks/executing"
  }

  const selectedAgentData = agents.find(a => a.id === selectedAgent)

  return (
    <div className="min-h-screen bg-background">
      {/* Progress Header */}
      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur border-b border-border">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-3 sm:py-4">
          {/* Mobile: Current step indicator */}
          <div className="flex items-center justify-between mb-2 sm:hidden">
            <span className="text-xs text-muted-foreground">Step {currentStep} of {steps.length}</span>
            <span className="text-xs font-medium text-foreground">{steps[currentStep - 1].title}</span>
          </div>
          {/* Step indicators */}
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <button
                  onClick={() => step.id < currentStep && setCurrentStep(step.id)}
                  disabled={step.id > currentStep}
                  className={cn(
                    "flex items-center gap-2 transition-all",
                    step.id === currentStep && "scale-105"
                  )}
                >
                  <div className={cn(
                    "w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-[10px] sm:text-xs font-semibold transition-all",
                    step.id < currentStep && "bg-emerald-500 text-white",
                    step.id === currentStep && "bg-foreground text-background ring-2 sm:ring-4 ring-foreground/10",
                    step.id > currentStep && "bg-secondary text-muted-foreground"
                  )}>
                    {step.id < currentStep ? (
                      <Icon name="check" size="sm" />
                    ) : (
                      step.id
                    )}
                  </div>
                  <div className="hidden md:block text-left">
                    <p className={cn(
                      "text-xs font-medium transition-colors",
                      step.id === currentStep ? "text-foreground" : "text-muted-foreground"
                    )}>
                      {step.title}
                    </p>
                  </div>
                </button>
                {index < steps.length - 1 && (
                  <div className={cn(
                    "w-8 lg:w-16 h-0.5 mx-2 transition-colors",
                    step.id < currentStep ? "bg-emerald-500" : "bg-border"
                  )} />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* Step 1: Select Agent */}
        {currentStep === 1 && (
          <div className={cn(
            "transition-all duration-500",
            mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          )}>
            <div className="text-center mb-6 sm:mb-8">
              <h2 className="text-xl sm:text-2xl font-bold text-foreground mb-2">Who should do this work?</h2>
              <p className="text-sm sm:text-base text-muted-foreground">Select an AI agent from your team</p>
            </div>
            
            <div className="grid gap-3 sm:gap-4">
              {agents.map((agent) => (
                <Card
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent.id)}
                  className={cn(
                    "p-4 sm:p-6 cursor-pointer transition-all duration-200 hover:shadow-lg",
                    selectedAgent === agent.id
                      ? "border-emerald-500 bg-emerald-500/5 ring-1 ring-emerald-500/20"
                      : "border-border/50 hover:border-border"
                  )}
                >
                  <div className="flex items-start gap-3 sm:gap-5">
                    {/* Avatar */}
                    <div className="relative shrink-0">
                      <div className={cn(
                        "w-11 h-11 sm:w-14 sm:h-14 rounded-lg sm:rounded-xl flex items-center justify-center transition-colors",
                        selectedAgent === agent.id
                          ? "bg-emerald-500/20"
                          : "bg-secondary"
                      )}>
                        <Icon name="ai" size="lg" className={selectedAgent === agent.id ? "text-emerald-500" : "text-muted-foreground"} />
                      </div>
                      <div className={cn(
                        "absolute -bottom-1 -right-1 w-3 h-3 sm:w-4 sm:h-4 rounded-full ring-2 ring-background",
                        agent.status === "online" ? "bg-emerald-500" : "bg-amber-500"
                      )} />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <h3 className="text-base sm:text-lg font-semibold text-foreground">{agent.name}</h3>
                        <Badge variant="outline" className="text-[10px] sm:text-xs">{agent.department}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-1.5 sm:gap-2 mt-2 sm:mt-3">
                        {agent.capabilities.slice(0, 3).map((cap) => (
                          <span key={cap} className="px-2 py-0.5 sm:py-1 bg-secondary rounded text-[10px] sm:text-xs text-muted-foreground">
                            {cap}
                          </span>
                        ))}
                        {agent.capabilities.length > 3 && (
                          <span className="px-2 py-0.5 sm:py-1 bg-secondary rounded text-[10px] sm:text-xs text-muted-foreground">
                            +{agent.capabilities.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                    
                    {/* Selection indicator */}
                    <div className={cn(
                      "w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 transition-all",
                      selectedAgent === agent.id
                        ? "border-emerald-500 bg-emerald-500"
                        : "border-muted-foreground/30"
                    )}>
                      {selectedAgent === agent.id && (
                        <Icon name="check" size="xs" className="text-white" />
                      )}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Task Description */}
        {currentStep === 2 && (
          <div className={cn(
            "transition-all duration-500",
            "opacity-100 translate-y-0"
          )}>
            <div className="text-center mb-6 sm:mb-8">
              <h2 className="text-xl sm:text-2xl font-bold text-foreground mb-2">What do you need done?</h2>
              <p className="text-sm sm:text-base text-muted-foreground">Describe the task in plain language</p>
            </div>
            
            <Card className="p-4 sm:p-6 border-border/50">
              <div className="flex items-center gap-3 mb-4 pb-4 border-b border-border">
                <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <Icon name="ai" size="md" className="text-emerald-500" />
                </div>
                <div>
                  <p className="text-sm sm:text-base font-medium text-foreground">{selectedAgentData?.name}</p>
                  <p className="text-xs text-muted-foreground">{selectedAgentData?.department}</p>
                </div>
              </div>
              
              <Textarea
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
                placeholder="Example: Create a Q3 email campaign targeting mid-market healthcare companies. Focus on our new compliance features."
                className="min-h-32 sm:min-h-40 text-base border-0 bg-transparent resize-none focus-visible:ring-0 p-0"
              />
              
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 pt-4 border-t border-border mt-4">
                <span className="text-xs text-muted-foreground">
                  {taskDescription.length} characters
                </span>
                <div className="flex flex-wrap gap-2">
                  {["Campaign", "Sequence", "Report", "Analysis"].map((tag) => (
                    <button
                      key={tag}
                      onClick={() => setTaskDescription(prev => prev + ` #${tag.toLowerCase()}`)}
                      className="px-2 py-1 rounded text-xs bg-secondary text-muted-foreground hover:text-foreground transition-colors"
                    >
                      #{tag}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Step 3: Details */}
        {currentStep === 3 && (
          <div className="transition-all duration-500 opacity-100 translate-y-0">
            <div className="text-center mb-6 sm:mb-8">
              <h2 className="text-xl sm:text-2xl font-bold text-foreground mb-2">Add some context</h2>
              <p className="text-sm sm:text-base text-muted-foreground">Help the agent understand your needs (optional)</p>
            </div>
            
            <div className="space-y-4 sm:space-y-6">
              <Card className="p-4 sm:p-6 border-border/50">
                <label className="block text-sm font-medium text-foreground mb-2">Target Audience</label>
                <Input
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="e.g., Mid-market healthcare companies"
                  className="h-11 sm:h-12"
                />
              </Card>
              
              <Card className="p-6 border-border/50">
                <label className="block text-sm font-medium text-foreground mb-2">Goal or Objective</label>
                <Input
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  placeholder="e.g., Generate 50 qualified leads, Increase engagement by 20%"
                  className="h-12"
                />
              </Card>
              
              <Card className="p-6 border-border/50">
                <label className="block text-sm font-medium text-foreground mb-3">Tone</label>
                <div className="flex flex-wrap gap-2">
                  {["professional", "friendly", "urgent", "casual", "formal"].map((t) => (
                    <button
                      key={t}
                      onClick={() => setTone(t)}
                      className={cn(
                        "px-4 py-2 rounded-lg text-sm font-medium capitalize transition-all",
                        tone === t
                          ? "bg-foreground text-background"
                          : "bg-secondary text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* Step 4: Outputs */}
        {currentStep === 4 && (
          <div className="transition-all duration-500 opacity-100 translate-y-0">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-2">What should be delivered?</h2>
              <p className="text-muted-foreground">Select the outputs you need</p>
            </div>
            
            <div className="grid md:grid-cols-2 gap-4">
              {outputTypes.map((output) => {
                const isSelected = selectedOutputs.includes(output.id)
                return (
                  <Card
                    key={output.id}
                    onClick={() => {
                      setSelectedOutputs(prev => 
                        isSelected 
                          ? prev.filter(id => id !== output.id)
                          : [...prev, output.id]
                      )
                    }}
                    className={cn(
                      "p-5 cursor-pointer transition-all duration-200",
                      isSelected
                        ? "border-emerald-500 bg-emerald-500/5 ring-1 ring-emerald-500/20"
                        : "border-border/50 hover:border-border"
                    )}
                  >
                    <div className="flex items-center gap-4">
                      <div className={cn(
                        "w-12 h-12 rounded-xl flex items-center justify-center transition-colors",
                        isSelected ? "bg-emerald-500/20" : "bg-secondary"
                      )}>
                        <Icon name={output.icon as any} size="lg" className={isSelected ? "text-emerald-500" : "text-muted-foreground"} />
                      </div>
                      <div className="flex-1">
                        <h3 className="font-semibold text-foreground">{output.label}</h3>
                        <p className="text-xs text-muted-foreground">{output.description}</p>
                      </div>
                      <Checkbox checked={isSelected} className="h-5 w-5" />
                    </div>
                  </Card>
                )
              })}
            </div>
          </div>
        )}

        {/* Step 5: Delivery */}
        {currentStep === 5 && (
          <div className="transition-all duration-500 opacity-100 translate-y-0">
            <div className="text-center mb-6 sm:mb-8">
              <h2 className="text-xl sm:text-2xl font-bold text-foreground mb-2">Where should results go?</h2>
              <p className="text-sm sm:text-base text-muted-foreground">Select one or more delivery destinations</p>
            </div>
            
            {/* Always stored in Gravitre notice */}
            <div className="flex items-center gap-3 p-3 sm:p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20 mb-4 sm:mb-6">
              <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                <Icon name="check" size="sm" className="text-emerald-500" />
              </div>
              <div>
                <p className="text-xs sm:text-sm font-medium text-foreground">Always stored in Gravitre</p>
                <p className="text-[10px] sm:text-xs text-muted-foreground">Your deliverables are always saved and accessible in Gravitre</p>
              </div>
            </div>
            
            <div className="space-y-3">
              {destinations.map((dest) => {
                const isSelected = selectedDestinations.includes(dest.id)
                const isDisabled = !dest.connected
                
                return (
                  <Card
                    key={dest.id}
                    onClick={() => {
                      if (isDisabled) return
                      setSelectedDestinations(prev => 
                        isSelected 
                          ? prev.filter(id => id !== dest.id)
                          : [...prev, dest.id]
                      )
                    }}
                    className={cn(
                      "p-4 sm:p-5 transition-all duration-200",
                      isDisabled 
                        ? "opacity-50 cursor-not-allowed"
                        : "cursor-pointer",
                      isSelected && !isDisabled
                        ? "border-emerald-500 bg-emerald-500/5 ring-1 ring-emerald-500/20"
                        : "border-border/50 hover:border-border"
                    )}
                  >
                    <div className="flex items-center gap-3 sm:gap-4">
                      <div className={cn(
                        "w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center transition-colors shrink-0",
                        isSelected && !isDisabled ? "bg-emerald-500/20" : "bg-secondary"
                      )}>
                        <Icon 
                          name={dest.icon as any} 
                          size="lg" 
                          className={isSelected && !isDisabled ? "text-emerald-500" : "text-muted-foreground"} 
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-foreground text-sm sm:text-base">{dest.label}</h3>
                          {dest.default && (
                            <Badge variant="outline" className="text-[10px] text-emerald-500 border-emerald-500/30 bg-emerald-500/10">
                              Default
                            </Badge>
                          )}
                          {!dest.connected && (
                            <Badge variant="outline" className="text-[10px] text-muted-foreground">
                              Connect to enable
                            </Badge>
                          )}
                        </div>
                        <p className="text-[10px] sm:text-xs text-muted-foreground">{dest.description}</p>
                        
                        {/* Slack channel selector */}
                        {dest.id === "slack" && isSelected && dest.channels && (
                          <div className="mt-2 sm:mt-3 flex flex-wrap gap-1.5 sm:gap-2">
                            {dest.channels.map((channel) => (
                              <button
                                key={channel}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setSlackChannel(channel)
                                }}
                                className={cn(
                                  "px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[10px] sm:text-xs font-medium transition-all",
                                  slackChannel === channel
                                    ? "bg-emerald-500/20 text-emerald-500 ring-1 ring-emerald-500/30"
                                    : "bg-secondary/50 text-muted-foreground hover:text-foreground"
                                )}
                              >
                                {channel}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      <Checkbox 
                        checked={isSelected} 
                        disabled={isDisabled}
                        className="h-4 w-4 sm:h-5 sm:w-5" 
                      />
                    </div>
                  </Card>
                )
              })}
            </div>
            
            {/* Selected summary */}
            {selectedDestinations.length > 0 && (
              <div className="mt-4 sm:mt-6 p-3 sm:p-4 rounded-lg bg-secondary/30 border border-border/50">
                <p className="text-xs sm:text-sm text-muted-foreground mb-2">Results will be delivered to:</p>
                <div className="flex flex-wrap gap-1.5 sm:gap-2">
                  {selectedDestinations.map(id => {
                    const dest = destinations.find(d => d.id === id)
                    return (
                      <Badge key={id} variant="outline" className="gap-1 text-xs">
                        <Icon name={dest?.icon as any} size="xs" />
                        {dest?.label}
                        {id === "slack" && slackChannel && ` (${slackChannel})`}
                      </Badge>
                    )
                  })}
                  <Badge variant="outline" className="gap-1 text-xs text-emerald-500 border-emerald-500/30">
                    <Icon name="check" size="xs" />
                    Gravitre
                  </Badge>
                </div>
              </div>
            )}
            
            {/* Approval toggle */}
            <Card className="p-4 sm:p-5 mt-4 sm:mt-6 border-border/50">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="font-semibold text-foreground text-sm sm:text-base">Require approval before sending</h3>
                  <p className="text-[10px] sm:text-xs text-muted-foreground">Review outputs before they are delivered</p>
                </div>
                <button
                  onClick={() => setRequireApproval(!requireApproval)}
                  className={cn(
                    "w-11 sm:w-12 h-6 sm:h-7 rounded-full transition-colors relative shrink-0",
                    requireApproval ? "bg-emerald-500" : "bg-secondary"
                  )}
                >
                  <div className={cn(
                    "absolute w-4 sm:w-5 h-4 sm:h-5 rounded-full bg-white shadow-sm top-1 transition-transform",
                    requireApproval ? "translate-x-5 sm:translate-x-6" : "translate-x-1"
                  )} />
                </button>
              </div>
            </Card>
          </div>
        )}

        {/* Step 6: Review */}
        {currentStep === 6 && (
          <div className="transition-all duration-500 opacity-100 translate-y-0">
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-foreground mb-2">Ready to run?</h2>
              <p className="text-muted-foreground">Review your task and submit</p>
            </div>
            
            <Card className="p-6 border-border/50 mb-6">
              <div className="space-y-6">
                {/* Agent */}
                <div className="flex items-center justify-between pb-4 border-b border-border">
                  <span className="text-sm text-muted-foreground">Assigned to</span>
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                      <Icon name="ai" size="sm" className="text-emerald-500" />
                    </div>
                    <span className="font-medium text-foreground">{selectedAgentData?.name}</span>
                  </div>
                </div>
                
                {/* Task */}
                <div className="pb-4 border-b border-border">
                  <span className="text-sm text-muted-foreground block mb-2">Task</span>
                  <p className="text-foreground">{taskDescription}</p>
                </div>
                
                {/* Context */}
                {(audience || goal) && (
                  <div className="pb-4 border-b border-border">
                    <span className="text-sm text-muted-foreground block mb-2">Context</span>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      {audience && (
                        <div>
                          <span className="text-muted-foreground">Audience: </span>
                          <span className="text-foreground">{audience}</span>
                        </div>
                      )}
                      {goal && (
                        <div>
                          <span className="text-muted-foreground">Goal: </span>
                          <span className="text-foreground">{goal}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Outputs */}
                <div className="pb-4 border-b border-border">
                  <span className="text-sm text-muted-foreground block mb-2">Outputs</span>
                  <div className="flex flex-wrap gap-2">
                    {selectedOutputs.map(id => {
                      const output = outputTypes.find(o => o.id === id)
                      return (
                        <Badge key={id} variant="outline" className="gap-1">
                          <Icon name={output?.icon as any} size="xs" />
                          {output?.label}
                        </Badge>
                      )
                    })}
                  </div>
                </div>
                
                {/* Delivery */}
                <div>
                  <span className="text-sm text-muted-foreground block mb-2">Delivery</span>
                  <div className="flex flex-wrap items-center gap-2">
                    {selectedDestinations.map(id => {
                      const dest = destinations.find(d => d.id === id)
                      return (
                        <div key={id} className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-secondary/50">
                          <Icon name={dest?.icon as any} size="sm" className="text-muted-foreground" />
                          <span className="text-sm text-foreground">
                            {dest?.label}
                            {id === "slack" && slackChannel && ` (${slackChannel})`}
                          </span>
                        </div>
                      )
                    })}
                    <div className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-emerald-500/10">
                      <Icon name="check" size="sm" className="text-emerald-500" />
                      <span className="text-sm text-emerald-500">Gravitre</span>
                    </div>
                    {requireApproval && (
                      <Badge variant="outline" className="text-amber-500 border-amber-500/30">
                        Approval required
                      </Badge>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8 pt-6 border-t border-border">
          <Button
            variant="ghost"
            onClick={() => setCurrentStep(prev => Math.max(1, prev - 1))}
            disabled={currentStep === 1}
            className="gap-2"
          >
            <Icon name="chevronLeft" size="sm" />
            Back
          </Button>
          
          {currentStep < 6 ? (
            <Button
              onClick={() => setCurrentStep(prev => Math.min(6, prev + 1))}
              disabled={!canProceed()}
              className="gap-2 bg-foreground text-background hover:bg-foreground/90"
            >
              Continue
              <Icon name="chevronRight" size="sm" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting}
              className="gap-2 bg-emerald-500 hover:bg-emerald-600 text-white min-w-32"
            >
              {isSubmitting ? (
                <>
                  <Icon name="spinner" size="sm" className="animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Icon name="play" size="sm" />
                  Run Task
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function LiteAssignPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background flex items-center justify-center"><Icon name="spinner" size="xl" className="animate-spin text-muted-foreground" /></div>}>
      <AssignWorkContent />
    </Suspense>
  )
}
