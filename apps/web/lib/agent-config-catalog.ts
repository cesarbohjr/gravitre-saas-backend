/**
 * Shared catalogs for agent create + profile edit.
 * Capability / system / guardrail labels are product affordances (not prices).
 */

import type { LucideIcon } from "lucide-react"
import {
  BarChart3,
  Database,
  FileText,
  MessageSquare,
  Sparkles,
  Users,
  Zap,
  BookOpen,
} from "lucide-react"

export type AgentCapabilityOption = {
  id: string
  name: string
  description: string
  icon: LucideIcon
}

export type AgentSystemOption = {
  id: string
  name: string
  type: string
}

export type AgentGuardrailOption = {
  id: string
  name: string
  description: string
  recommended: boolean
}

export const AGENT_CAPABILITY_OPTIONS: AgentCapabilityOption[] = [
  {
    id: "analyze",
    name: "Analyze data",
    description: "Look through your data and find insights",
    icon: BarChart3,
  },
  {
    id: "generate",
    name: "Create reports",
    description: "Write reports and summaries for you",
    icon: FileText,
  },
  {
    id: "suggest",
    name: "Give suggestions",
    description: "Recommend ways to improve based on what it sees",
    icon: Sparkles,
  },
  {
    id: "sync",
    name: "Sync data",
    description: "Keep your apps up to date with each other",
    icon: Zap,
  },
  {
    id: "communicate",
    name: "Send messages",
    description: "Send updates and alerts to your team",
    icon: MessageSquare,
  },
  {
    id: "coordinate",
    name: "Manage tasks",
    description: "Assign tasks and follow up on them",
    icon: Users,
  },
  {
    id: "knowledge",
    name: "Use knowledge",
    description: "Ground answers in assigned folders, docs, and sources",
    icon: BookOpen,
  },
]

export const AGENT_SYSTEM_OPTIONS: AgentSystemOption[] = [
  { id: "hubspot", name: "HubSpot", type: "Marketing" },
  { id: "salesforce", name: "Salesforce", type: "CRM" },
  { id: "slack", name: "Slack", type: "Communication" },
  { id: "google-analytics", name: "Google Analytics", type: "Analytics" },
  { id: "postgresql", name: "PostgreSQL", type: "Database" },
  { id: "microsoft365", name: "Microsoft 365", type: "Productivity" },
]

export const AGENT_GUARDRAIL_OPTIONS: AgentGuardrailOption[] = [
  {
    id: "approval-changes",
    name: "Ask before making changes",
    description: "Get approval before the AI makes any changes",
    recommended: true,
  },
  {
    id: "admin-delete",
    name: "Only admins can delete",
    description: "Only admins can delete or remove things",
    recommended: true,
  },
  {
    id: "env-restrict",
    name: "Workspace limits",
    description: "Different rules for live vs test workspaces",
    recommended: false,
  },
  {
    id: "rate-limit",
    name: "Slow down",
    description: "Limit how many things it can do per hour",
    recommended: false,
  },
]

export function capabilityIdsFromNames(names: string[]): string[] {
  const normalized = names.map((name) => name.trim().toLowerCase())
  const ids = AGENT_CAPABILITY_OPTIONS.filter((option) =>
    normalized.includes(option.name.toLowerCase()),
  ).map((option) => option.id)
  return ids
}

export function capabilityNamesFromIds(ids: string[], customNames: string[] = []): string[] {
  const fromCatalog = ids
    .map((id) => AGENT_CAPABILITY_OPTIONS.find((option) => option.id === id)?.name)
    .filter((value): value is string => Boolean(value))
  const extras = customNames.map((name) => name.trim()).filter(Boolean)
  return Array.from(new Set([...fromCatalog, ...extras]))
}

export function systemIdsFromNames(names: string[]): string[] {
  const normalized = names.map((name) => name.trim().toLowerCase())
  return AGENT_SYSTEM_OPTIONS.filter((option) =>
    normalized.includes(option.name.toLowerCase()),
  ).map((option) => option.id)
}

export function systemNamesFromIds(ids: string[]): string[] {
  return ids
    .map((id) => AGENT_SYSTEM_OPTIONS.find((option) => option.id === id)?.name)
    .filter((value): value is string => Boolean(value))
}

export function guardrailIdsFromNames(names: string[]): string[] {
  const normalized = names.map((name) => name.trim().toLowerCase())
  return AGENT_GUARDRAIL_OPTIONS.filter((option) =>
    normalized.includes(option.name.toLowerCase()),
  ).map((option) => option.id)
}

export function guardrailNamesFromIds(ids: string[]): string[] {
  return ids
    .map((id) => AGENT_GUARDRAIL_OPTIONS.find((option) => option.id === id)?.name)
    .filter((value): value is string => Boolean(value))
}

export function customCapabilityNames(names: string[]): string[] {
  const catalog = new Set(AGENT_CAPABILITY_OPTIONS.map((option) => option.name.toLowerCase()))
  return names.filter((name) => name.trim() && !catalog.has(name.trim().toLowerCase()))
}

/** Keep Database icon available for legacy new-page icon map imports. */
export { Database }
