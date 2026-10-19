/**
 * Environments data (GET/POST /api/environments, PATCH/DELETE /api/environments/{id}).
 * The backend allows exactly three stages (development, staging, production);
 * production is the default and cannot be deleted. Resource counts come from
 * rows tagged with the environment and are null when the backend cannot count them.
 */
import { apiFetch, fetcher } from "@/lib/fetcher"
import { extractApiErrorMessage } from "@/lib/api-error-message"

export type StageId = "development" | "staging" | "production"

export const ENVIRONMENTS_KEY = "/api/environments"

export interface StageMeta {
  id: StageId
  name: string
  hint: string
  why: string
}

/** Design copy for the three pipeline stages, in promotion order. */
export const STAGES: StageMeta[] = [
  {
    id: "development",
    name: "Development",
    hint: "Try changes safely with test data",
    why: "Build and test agents without touching real records.",
  },
  {
    id: "staging",
    name: "Staging",
    hint: "Rehearse with a copy of production",
    why: "Check changes against production like data before they go live.",
  },
  {
    id: "production",
    name: "Production",
    hint: "Live for everyone",
    why: "Production is where agents and workflows run for everyone in this workspace.",
  },
]

export interface EnvResources {
  workflows: number | null
  agents: number | null
  connectors: number | null
  sources: number | null
}

export interface EnvRecord {
  id: string
  name: string
  stage: StageId | null
  isActive: boolean
  isDefault: boolean
  createdAt: string | null
  apiUrl: string | null
  resources: EnvResources
}

export interface EnvironmentsPayload {
  environments?: unknown[]
  stages?: string[]
  environmentsLimit?: number | null
}

function count(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

export function stageFor(name: string): StageId | null {
  const slug = name.trim().toLowerCase()
  if (slug === "production" || slug === "default") return "production"
  if (slug === "staging" || slug === "stage") return "staging"
  if (slug === "development" || slug === "dev") return "development"
  return null
}

export function normalizeEnvironments(payload: unknown): EnvRecord[] {
  if (!payload || typeof payload !== "object") return []
  const raw = (payload as EnvironmentsPayload).environments
  if (!Array.isArray(raw)) return []
  return raw
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item) => {
      const name = String(item.name ?? "").trim().toLowerCase()
      const resources = (item.resources as Record<string, unknown> | undefined) ?? {}
      const stage = stageFor(name)
      return {
        id: String(item.id ?? ""),
        name,
        stage,
        isActive: item.is_active !== false && item.isActive !== false,
        isDefault: Boolean(item.is_default ?? item.isDefault ?? stage === "production"),
        createdAt: text(item.created_at ?? item.createdAt),
        apiUrl: text(item.api_url ?? item.apiUrl),
        resources: {
          workflows: count(item.workflows ?? resources.workflows),
          agents: count(item.agents ?? resources.agents),
          connectors: count(item.connectors ?? resources.connectors),
          sources: count(item.sources ?? resources.sources),
        },
      } satisfies EnvRecord
    })
    .filter((env) => env.id.length > 0)
}

export interface StageView extends StageMeta {
  env: EnvRecord | null
  /** Set up and switched on. */
  live: boolean
}

/** One entry per pipeline stage; a real "production" row wins over a legacy "default" row. */
export function buildStages(envs: EnvRecord[]): StageView[] {
  return STAGES.map((stage) => {
    const matches = envs.filter((env) => env.stage === stage.id)
    const env = matches.find((item) => item.name === stage.id) ?? matches[0] ?? null
    return { ...stage, env, live: Boolean(env && env.isActive) }
  })
}

/** Sum of a resource across environments; null when no environment reports it. */
export function sumResource(envs: EnvRecord[], key: keyof EnvResources): number | null {
  const values = envs.map((env) => env.resources[key]).filter((value): value is number => value !== null)
  if (!values.length) return null
  return values.reduce((total, value) => total + value, 0)
}

/** "None yet" for missing or zero counts; the design never shows "Not reported". */
export function countOrNull(value: number | null): number | null {
  return value === null || value === 0 ? null : value
}

async function send<T>(url: string, init: RequestInit): Promise<T> {
  const response = await apiFetch(url, {
    ...init,
    headers: init.body ? { "Content-Type": "application/json" } : undefined,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(extractApiErrorMessage(payload) || `Request failed (${response.status})`)
  }
  return payload as T
}

export const environmentsSettingsApi = {
  list: () => fetcher<EnvironmentsPayload>(ENVIRONMENTS_KEY),
  create: (stage: StageId) =>
    send<{ id: string; name: string }>(ENVIRONMENTS_KEY, { method: "POST", body: JSON.stringify({ name: stage }) }),
  setActive: (id: string, isActive: boolean) =>
    send<{ id: string; is_active: boolean }>(`${ENVIRONMENTS_KEY}/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ isActive }),
    }),
  remove: (id: string) => send<{ id: string; deleted: boolean }>(`${ENVIRONMENTS_KEY}/${id}`, { method: "DELETE" }),
}
