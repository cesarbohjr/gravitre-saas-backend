"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  KNOWLEDGE_NODE_TYPE_LABELS,
  RELATIONSHIPS_GUIDE,
  RELATIONSHIPS_ONBOARDING,
  knowledgeNodeTypeLabel,
} from "@/lib/learning-ui-copy"
import { intelligenceApi } from "@/lib/api"
import {
  findLearnedEntityMatches,
  type EntityMatchCandidate,
} from "@/lib/relationships-graph/match-candidates"
import { entityKey } from "@/lib/relationships-graph/utils"
import { ResolveMark } from "@/components/gravitre/visual/resolve-mark"
import { Building, Cube, Storefront, User, UsersThree } from "@phosphor-icons/react"
import { DuplicateMatchPanel } from "./duplicate-match-panel"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

const FIRST_ENTITY_TYPES = ["company", "customer", "employee", "product", "vendor"] as const

const TYPE_ICONS: Record<string, typeof Building> = {
  company: Building,
  customer: UsersThree,
  employee: User,
  product: Cube,
  vendor: Storefront,
}

export function AddKnowledgeNodeSheet({
  workspace,
}: {
  workspace: RelationshipsWorkspaceState
}) {
  const {
    addNodeOpen,
    setAddNodeOpen,
    addNodeMode,
    nodeTypes,
    nodes,
    filtered,
    labelFor,
    createNode,
    focusExistingEntity,
  } = workspace
  const [nodeName, setNodeName] = useState("")
  const [nodeType, setNodeType] = useState("company")
  const [busy, setBusy] = useState(false)
  const [debouncedName, setDebouncedName] = useState("")
  const [forceCreate, setForceCreate] = useState(false)
  const [showResolve, setShowResolve] = useState(false)
  const isFirst = addNodeMode === "first"

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedName(nodeName.trim()), 300)
    return () => window.clearTimeout(handle)
  }, [nodeName])

  useEffect(() => {
    setForceCreate(false)
  }, [debouncedName, nodeType, addNodeOpen])

  const clientMatches = useMemo(() => {
    if (!debouncedName || debouncedName.length < 2) return []
    const fromNodes = nodes
      .filter((n) => {
        const t = String(n.node_type ?? "")
        return !nodeType || t === nodeType
      })
      .map((n) => {
        const name = String(n.name ?? "")
        const id = String(n.id ?? "")
        const score = scoreLocal(debouncedName, name)
        if (score < 60 || !id) return null
        return {
          id: `seed::${id}`,
          name,
          nodeType: String(n.node_type ?? ""),
          entityType: String(n.node_type ?? "company"),
          entityId: id,
          matchScore: score,
          source: "confirmed_knowledge" as const,
        }
      })
      .filter(Boolean) as EntityMatchCandidate[]
    const learned = findLearnedEntityMatches(debouncedName, filtered, labelFor)
    const merged = new Map<string, EntityMatchCandidate>()
    for (const m of [...fromNodes, ...learned]) merged.set(m.id, m)
    return [...merged.values()]
      .sort((a, b) => b.matchScore - a.matchScore || a.name.localeCompare(b.name))
      .slice(0, 5)
  }, [debouncedName, nodeType, nodes, filtered, labelFor])

  const { data: apiMatchData } = useSWR(
    addNodeOpen && debouncedName.length >= 2
      ? ["admin/intelligence/knowledge-nodes/match", debouncedName, nodeType]
      : null,
    () => intelligenceApi.matchKnowledgeNodes({ name: debouncedName, nodeType }),
    { revalidateOnFocus: false },
  )

  const apiMatches = useMemo(() => {
    const rows = (apiMatchData?.matches ?? []) as Array<Record<string, unknown>>
    return rows.map((row) => ({
      id: `seed::${String(row.id ?? "")}`,
      name: String(row.name ?? ""),
      nodeType: String(row.nodeType ?? ""),
      entityType: String(row.entityType ?? row.nodeType ?? "company"),
      entityId: String(row.id ?? ""),
      matchScore: Number(row.matchScore ?? 0),
      source: "confirmed_knowledge" as const,
    })) satisfies EntityMatchCandidate[]
  }, [apiMatchData])

  const matchCandidates = useMemo(() => {
    const merged = new Map<string, EntityMatchCandidate>()
    for (const m of [...clientMatches, ...apiMatches]) {
      const existing = merged.get(m.id)
      if (!existing || m.matchScore > existing.matchScore) merged.set(m.id, m)
    }
    return [...merged.values()]
      .sort((a, b) => b.matchScore - a.matchScore || a.name.localeCompare(b.name))
      .slice(0, 5)
  }, [clientMatches, apiMatches])

  async function handleSubmit() {
    setBusy(true)
    const result = await createNode(nodeType, nodeName)
    setBusy(false)
    if (result.ok) {
      setShowResolve(true)
      window.setTimeout(() => {
        setShowResolve(false)
        setNodeName("")
        setForceCreate(false)
        setAddNodeOpen(false)
      }, 900)
    }
  }

  function handleUseExisting(match: EntityMatchCandidate) {
    focusExistingEntity(match.entityType, match.entityId, match.name)
    setAddNodeOpen(false)
    setNodeName("")
    setForceCreate(false)
  }

  return (
    <Sheet open={addNodeOpen} onOpenChange={setAddNodeOpen}>
      <SheetContent className="sm:max-w-md">
        <SheetHeader>
          <SheetTitle>
            {isFirst ? RELATIONSHIPS_ONBOARDING.sheetTitle : "Add organization entity"}
          </SheetTitle>
          <SheetDescription>
            {isFirst ? RELATIONSHIPS_ONBOARDING.sheetLead : RELATIONSHIPS_GUIDE.nodesBody}
          </SheetDescription>
        </SheetHeader>
        <div className="space-y-4 px-4 py-2">
          {isFirst ? (
            <div className="space-y-2">
              <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Entity type</span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {FIRST_ENTITY_TYPES.map((t) => {
                  const Icon = TYPE_ICONS[t] ?? Building
                  const selected = nodeType === t
                  return (
                    <button
                      key={t}
                      type="button"
                      className={`flex flex-col items-center gap-1.5 rounded-[var(--np-radius-md)] border px-2 py-3 text-center transition-colors ${
                        selected
                          ? "border-[color:var(--g-brand)]/50 bg-[color:var(--g-brand-soft)]/40"
                          : "border-divide bg-[color:var(--g-surface-1)] hover:bg-[color:var(--g-surface-2)]"
                      }`}
                      onClick={() => setNodeType(t)}
                    >
                      <Icon className="h-5 w-5 text-[color:var(--g-brand)]" aria-hidden />
                      <span className="text-xs font-medium">{KNOWLEDGE_NODE_TYPE_LABELS[t] ?? t}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-[color:var(--g-text-muted)]">Type</span>
              <div className="flex flex-wrap gap-2">
                {nodeTypes.map((t) => (
                  <Button
                    key={t}
                    type="button"
                    size="sm"
                    variant={nodeType === t ? "default" : "outline"}
                    onClick={() => setNodeType(t)}
                  >
                    {knowledgeNodeTypeLabel(t)}
                  </Button>
                ))}
              </div>
            </div>
          )}
          <div className="space-y-1.5">
            <label htmlFor="kn-name-drawer" className="text-xs font-medium text-[color:var(--g-text-muted)]">
              Name
            </label>
            <Input
              id="kn-name-drawer"
              value={nodeName}
              onChange={(e) => setNodeName(e.target.value)}
              placeholder="e.g. Acme Corp"
            />
          </div>
          {!forceCreate && matchCandidates.length > 0 ? (
            <DuplicateMatchPanel
              matches={matchCandidates}
              onUseExisting={handleUseExisting}
              onCreateSeparate={() => setForceCreate(true)}
            />
          ) : null}
          {!isFirst ? (
            <p className="text-xs leading-relaxed text-[color:var(--g-text-muted)]">{RELATIONSHIPS_GUIDE.nodesHint}</p>
          ) : null}
        </div>
        <SheetFooter className="flex-row items-center justify-between gap-2 sm:justify-end">
          {showResolve ? <ResolveMark label="Entity added" /> : null}
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => setAddNodeOpen(false)}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={busy || !nodeName.trim()}
              onClick={() => void handleSubmit()}
            >
              {isFirst ? "Add organization entity" : "Add entity"}
            </Button>
          </div>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function scoreLocal(candidate: string, target: string): number {
  const cand = candidate.trim().toLowerCase()
  const node = target.trim().toLowerCase()
  if (!cand || !node) return 0
  if (cand === node) return 100
  if (node.startsWith(cand) || cand.startsWith(node)) return 80
  if (cand.includes(node) || node.includes(cand)) return 60
  return 0
}
