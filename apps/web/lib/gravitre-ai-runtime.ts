/**
 * Live canonical conversation runtime registry + test/dev instrumentation.
 *
 * Product UI never renders this. Playwright and local debug read
 * `window.__GRAVITRE_AI_DEBUG` only when instrumentation is enabled.
 */

export const CANONICAL_AI_RUNTIME_OWNER_ID = "canonical-ai-workspace"

export type GravitreAiRuntimeDebugSnapshot = {
  liveInstanceCount: number
  liveOwnerIds: string[]
  liveInstanceIds: string[]
  currentInstanceId: string | null
  mountCount: number
  unmountCount: number
  chatSubmitCount: number
  conversationId: string | null
  streamStatus: string | null
  presentation: string | null
  canonicalPresentation: string | null
  pathname: string | null
  agentScopeId: string | null
  agentScopeName: string | null
  selected: { kind: string; id: string; label: string } | null
  voiceModality: string | null
  voicePresence: string | null
  lastChatRequestSummary: Record<string, unknown> | null
}

const LIVE_INSTANCES = new Map<string, string>()
let mountCount = 0
let unmountCount = 0
let chatSubmitCount = 0
let currentInstanceId: string | null = null
let lastChatRequestSummary: Record<string, unknown> | null = null

const workspaceFields: Partial<GravitreAiRuntimeDebugSnapshot> = {}

function createInstanceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID()
  }
  return `ai-rt-${Math.random().toString(36).slice(2)}-${Date.now()}`
}

export function isGravitreAiInstrumentationEnabled(): boolean {
  if (typeof window === "undefined") return false
  if (process.env.NEXT_PUBLIC_PLAYWRIGHT_E2E === "1") return true
  if (process.env.NODE_ENV === "production") return false
  return Boolean((window as Window & { __GRAVITRE_AI_INSTRUMENT?: boolean }).__GRAVITRE_AI_INSTRUMENT)
}

function publishCount(): number {
  const count = LIVE_INSTANCES.size
  if (typeof window !== "undefined") {
    const w = window as Window & {
      __GRAVITRE_AI_LIVE_RUNTIME_COUNT?: number
      __GRAVITRE_AI_DEBUG?: GravitreAiRuntimeDebugSnapshot
    }
    w.__GRAVITRE_AI_LIVE_RUNTIME_COUNT = count
    if (isGravitreAiInstrumentationEnabled()) {
      w.__GRAVITRE_AI_DEBUG = getGravitreAiRuntimeDebugSnapshot()
    } else if (process.env.NODE_ENV === "production") {
      delete w.__GRAVITRE_AI_DEBUG
    }
  }
  return count
}

export function getGravitreAiRuntimeDebugSnapshot(): GravitreAiRuntimeDebugSnapshot {
  return {
    liveInstanceCount: LIVE_INSTANCES.size,
    liveOwnerIds: [...new Set(LIVE_INSTANCES.values())].sort(),
    liveInstanceIds: [...LIVE_INSTANCES.keys()].sort(),
    currentInstanceId,
    mountCount,
    unmountCount,
    chatSubmitCount,
    lastChatRequestSummary,
    conversationId: workspaceFields.conversationId ?? null,
    streamStatus: workspaceFields.streamStatus ?? null,
    presentation: workspaceFields.presentation ?? null,
    canonicalPresentation: workspaceFields.canonicalPresentation ?? null,
    pathname: workspaceFields.pathname ?? null,
    agentScopeId: workspaceFields.agentScopeId ?? null,
    agentScopeName: workspaceFields.agentScopeName ?? null,
    selected: workspaceFields.selected ?? null,
    voiceModality: workspaceFields.voiceModality ?? null,
    voicePresence: workspaceFields.voicePresence ?? null,
  }
}

export function publishGravitreAiWorkspaceDebug(partial: Partial<GravitreAiRuntimeDebugSnapshot>): void {
  Object.assign(workspaceFields, partial)
  publishCount()
}

export function recordCanonicalChatSubmit(summary?: Record<string, unknown>): void {
  chatSubmitCount += 1
  if (summary) lastChatRequestSummary = summary
  publishCount()
}

export function registerGravitreAiChatRuntime(ownerId: string): () => void {
  const instanceId = createInstanceId()
  mountCount += 1
  currentInstanceId = instanceId
  LIVE_INSTANCES.set(instanceId, ownerId)
  publishCount()
  return () => {
    unmountCount += 1
    LIVE_INSTANCES.delete(instanceId)
    if (currentInstanceId === instanceId) {
      const remaining = LIVE_INSTANCES.keys().next()
      currentInstanceId = remaining.done ? null : remaining.value
    }
    publishCount()
  }
}

export function getGravitreAiLiveRuntimeCount(): number {
  return LIVE_INSTANCES.size
}

export function getGravitreAiLiveRuntimeOwnerIds(): string[] {
  return [...new Set(LIVE_INSTANCES.values())].sort()
}

export function getGravitreAiLiveRuntimeInstanceIds(): string[] {
  return [...LIVE_INSTANCES.keys()]
}

/** Tests only — never call from product UI. */
export function resetGravitreAiChatRuntimeRegistryForTests(): void {
  LIVE_INSTANCES.clear()
  mountCount = 0
  unmountCount = 0
  chatSubmitCount = 0
  currentInstanceId = null
  lastChatRequestSummary = null
  for (const key of Object.keys(workspaceFields)) {
    delete workspaceFields[key as keyof typeof workspaceFields]
  }
  publishCount()
}
