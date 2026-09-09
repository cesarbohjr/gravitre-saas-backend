"use client"

import { useState } from "react"
import useSWR from "swr"
import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { entityTypeLabel, knowledgeNodeTypeLabel, relationshipTypeLabel } from "@/lib/learning-ui-copy"
import { intelligenceApi } from "@/lib/api"
import { CLUSTER_PREFIX, detectAggregateClusters } from "@/lib/relationships-graph/aggregate-edges"
import { findRelationshipPaths } from "@/lib/relationships-graph/pathfinding"
import {
  confidenceLabel,
  confidenceTone,
  entityKey,
  readNumber,
  relationshipEdgeId,
  truncateEntityId,
} from "@/lib/relationships-graph/utils"
import type { RelationshipRow } from "@/lib/relationships-graph/types"
import { formatTime } from "@/app/admin/intelligence/_components/shared"
import { TracePath, TRACE_PATH_HYBRID_BEAT } from "@/components/gravitre/visual/trace-path"
import { Archive, ArrowCounterClockwise, PencilSimple, X } from "@phosphor-icons/react"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

function buildAskPrompt(kind: "node" | "edge", detail: string): string {
  return `Help me understand this ${kind === "node" ? "entity" : "relationship"} in our organization knowledge graph: ${detail}. What does Gravitre know about it and how was it learned?`
}

function findRelationship(workspace: RelationshipsWorkspaceState, edgeId: string): RelationshipRow | undefined {
  return workspace.filtered.find((rel) => relationshipEdgeId(rel) === edgeId)
}

function relationshipLearnedCopy(relationshipType: string): string {
  const t = String(relationshipType ?? "").toLowerCase()
  if (t === "tracked-by") {
    return "Gravitre observed an agent act on this entity in account-monitoring or outcome records. Each observation increases evidence count."
  }
  if (t === "referenced-by-agent") {
    return "An agent memory mentioned this glossary term or entity while working."
  }
  if (t === "co-occurs-with") {
    return "Queries or topics that appeared together in your organization's search patterns."
  }
  return "Inferred from indexed sources, glossary terms, and agent activity. Confidence is a heuristic estimate, not an ML score."
}

function findNodeContext(workspace: RelationshipsWorkspaceState, nodeId: string) {
  if (nodeId.startsWith(CLUSTER_PREFIX)) {
    const cluster = detectAggregateClusters(workspace.filtered).find((c) => c.id === nodeId)
    if (cluster) {
      const typeLabel = entityTypeLabel(cluster.sourceEntityType)
      return {
        label: `${cluster.memberKeys.length} ${typeLabel}s`,
        entityType: cluster.sourceEntityType,
        entityId: nodeId,
        isSeeded: false,
        isCluster: true,
        clusterId: nodeId,
        clusterCount: cluster.memberKeys.length,
      }
    }
  }
  if (nodeId.startsWith("seed::")) {
    const knId = nodeId.slice("seed::".length)
    const node = workspace.nodes.find((n) => String(n.id) === knId)
    if (node) {
      return {
        label: String(node.name ?? knId),
        entityType: String(node.node_type ?? ""),
        entityId: knId,
        knowledgeNodeId: knId,
        isSeeded: true,
      }
    }
  }
  const [entityType, ...rest] = nodeId.split("::")
  const entityId = rest.join("::")
  const knowledgeMatch = workspace.nodes.find((n) => String(n.id) === entityId)
  if (knowledgeMatch) {
    return {
      label: String(knowledgeMatch.name ?? entityId),
      entityType: String(knowledgeMatch.node_type ?? entityType),
      entityId,
      knowledgeNodeId: String(knowledgeMatch.id),
      isSeeded: true,
    }
  }
  return {
    label: workspace.labelFor(entityType, entityId),
    entityType,
    entityId,
    isSeeded: false,
  }
}

function connectedRelationships(workspace: RelationshipsWorkspaceState, nodeId: string) {
  const ctx = findNodeContext(workspace, nodeId)
  const key = ctx.isSeeded ? entityKey(ctx.entityType, ctx.entityId) : entityKey(ctx.entityType, ctx.entityId)
  if (nodeId.startsWith("seed::")) {
    return workspace.filtered.filter((rel) => {
      const src = entityKey(rel.source_entity_type, rel.source_entity_id)
      const tgt = entityKey(rel.target_entity_type, rel.target_entity_id)
      return src === key || tgt === key || src === nodeId || tgt === nodeId
    })
  }
  return workspace.filtered.filter((rel) => {
    const src = entityKey(rel.source_entity_type, rel.source_entity_id)
    const tgt = entityKey(rel.target_entity_type, rel.target_entity_id)
    return src === key || tgt === key
  })
}

function SeededNodeEditor({
  workspace,
  nodeId,
}: {
  workspace: RelationshipsWorkspaceState
  nodeId: string
}) {
  const ctx = findNodeContext(workspace, nodeId)
  const knId = ctx.knowledgeNodeId
  const node = knId ? workspace.nodes.find((n) => String(n.id) === knId) : undefined
  const [editing, setEditing] = useState(false)
  const [name, setName] = useState(String(node?.name ?? ""))
  const [nodeType, setNodeType] = useState(String(node?.node_type ?? "company"))
  const [busy, setBusy] = useState(false)

  if (!ctx.isSeeded || !node || !knId) return null
  const resolvedKnId = knId

  async function save() {
    setBusy(true)
    const ok = await workspace.updateNode(resolvedKnId, nodeType, name)
    setBusy(false)
    if (ok) setEditing(false)
  }

  if (!editing) {
    return (
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="gap-1.5"
        data-testid="seeded-node-edit"
        onClick={() => setEditing(true)}
      >
        <PencilSimple className="h-4 w-4" weight="bold" aria-hidden />
        Edit
      </Button>
    )
  }

  return (
    <div className="space-y-2 rounded-md border border-divide p-3">
      <Input value={name} onChange={(e) => setName(e.target.value)} aria-label="Node name" />
      <Select value={nodeType} onValueChange={setNodeType}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {workspace.nodeTypes.map((t) => (
            <SelectItem key={t} value={t}>
              {knowledgeNodeTypeLabel(t)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <div className="flex gap-2">
        <Button type="button" size="sm" disabled={busy} onClick={() => void save()}>
          Save
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </div>
  )
}

function MultiHopPaths({
  workspace,
  entityType,
  entityId,
}: {
  workspace: RelationshipsWorkspaceState
  entityType: string
  entityId: string
}) {
  const { data, isLoading } = useSWR(
    workspace.enabled && entityType && entityId
      ? ["admin/intelligence/knowledge-graph/traverse", entityType, entityId]
      : null,
    () => intelligenceApi.knowledgeGraphTraverse({ entityType, entityId, maxHops: 2 }),
  )
  const paths = data?.paths ?? []
  if (isLoading) return <p className="text-xs text-[color:var(--g-text-muted)]">Loading extended paths…</p>
  if (paths.length === 0) return null

  return (
    <div>
      <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
        Extended connections (multi-hop)
      </p>
      <ul className="space-y-2">
        {paths.slice(0, 6).map((path, i) => (
          <li
            key={`${path.entityType}-${path.entityId}-${i}`}
            className="rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-2.5 py-2 text-xs"
          >
            <span className="font-medium">
              {entityTypeLabel(path.entityType)} · hop {path.hopDepth}
            </span>
            <p className="mt-0.5 text-[color:var(--g-text-muted)]">{path.pathSummary}</p>
            <p className="mt-0.5 tabular-nums text-[color:var(--g-text-muted)]">
              {relationshipTypeLabel(path.relationshipType)} · conf {path.confidence.toFixed(2)} est.
            </p>
          </li>
        ))}
      </ul>
      {data?.scope_note ? (
        <p className="mt-2 text-[10px] leading-relaxed text-[color:var(--g-text-muted)]">{data.scope_note}</p>
      ) : null}
    </div>
  )
}

export function RelationshipInspector({
  workspace,
  onClose,
}: {
  workspace: RelationshipsWorkspaceState
  onClose?: () => void
}) {
  const { selection, setArchived, busyId, removeNode, setSelection, filtered } = workspace

  if (!selection) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <p className="text-sm text-[color:var(--g-text-muted)]">
          Select a node or relationship on the graph to inspect details.
        </p>
      </div>
    )
  }

  if (selection.kind === "edge") {
    const rel = findRelationship(workspace, selection.edgeId)
    if (!rel) {
      return (
        <div className="p-4 text-sm text-[color:var(--g-text-muted)]">Relationship not found in current view.</div>
      )
    }
    const confidence = readNumber(rel.confidence)
    const id = String(rel.id ?? "")
    const archived = Boolean(rel.archived_at)
    const from = workspace.labelFor(rel.source_entity_type, rel.source_entity_id)
    const to = workspace.labelFor(rel.target_entity_type, rel.target_entity_id)
    const link = relationshipTypeLabel(String(rel.relationship_type ?? ""))
    const askHref = `/ai?prompt=${encodeURIComponent(buildAskPrompt("edge", `${from} ${link} ${to}`))}`
    const altPaths = findRelationshipPaths(
      filtered,
      String(rel.source_entity_type ?? ""),
      String(rel.source_entity_id ?? ""),
      String(rel.target_entity_type ?? ""),
      String(rel.target_entity_id ?? ""),
      3,
    ).filter((path) => path.length !== 1)

    return (
      <div className="flex h-full flex-col">
        <div className="flex items-start justify-between gap-2 border-b border-divide px-4 py-3">
          <div className="min-w-0">
            <p className="text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
              Learned relationship
            </p>
            <p className="mt-0.5 text-sm font-semibold text-[color:var(--g-text-primary)]">{link}</p>
          </div>
          {onClose ? (
            <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close inspector">
              <X className="h-4 w-4" aria-hidden />
            </Button>
          ) : null}
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          <div className="space-y-2 text-sm">
            <div>
              <p className="text-[11px] text-[color:var(--g-text-muted)]">From</p>
              <p className="font-medium">{entityTypeLabel(rel.source_entity_type)}</p>
              <p className="text-[color:var(--g-text-secondary)]">{from}</p>
            </div>
            <div>
              <p className="text-[11px] text-[color:var(--g-text-muted)]">To</p>
              <p className="font-medium">{entityTypeLabel(rel.target_entity_type)}</p>
              <p className="text-[color:var(--g-text-secondary)]">{to}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className="tabular-nums">
              {readNumber(rel.evidence_count)} sources
            </Badge>
            <Badge variant="outline" className={`tabular-nums ${confidenceTone(confidence)}`} title="Heuristic estimate">
              {confidenceLabel(confidence)} · {confidence.toFixed(2)} est.
            </Badge>
            {archived ? <Badge variant="secondary">Archived</Badge> : null}
          </div>
          {altPaths.length > 0 ? (
            <div>
              <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
                Indirect paths (loaded graph)
              </p>
              <ul className="space-y-2">
                {altPaths.slice(0, 3).map((path, i) => (
                  <li key={i} className="rounded-md border border-divide px-2.5 py-2 text-xs">
                    {path.map((step) => relationshipTypeLabel(step.relationshipType)).join(" → ")}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          <dl className="grid gap-2 text-sm">
            <div>
              <dt className="text-[11px] text-[color:var(--g-text-muted)]">Last observed</dt>
              <dd>{formatTime(rel.last_observed_at ?? rel.created_at)}</dd>
            </div>
            <div>
              <dt className="text-[11px] text-[color:var(--g-text-muted)]">How Gravitre learned this</dt>
              <dd className="space-y-2 leading-relaxed text-[color:var(--g-text-secondary)]">
                <TracePath
                  d={TRACE_PATH_HYBRID_BEAT}
                  tone="intelligence"
                  progress={1}
                  className="max-h-12"
                  label="Relationship learning path"
                />
                {relationshipLearnedCopy(String(rel.relationship_type ?? ""))}
              </dd>
            </div>
          </dl>
        </div>
        <div className="flex flex-col gap-2 border-t border-divide p-4">
          <Button type="button" variant="outline" size="sm" className="gap-2" asChild>
            <Link href={askHref}>
              <NucleoAgent className="h-4 w-4" aria-hidden />
              Ask Gravitre AI
            </Link>
          </Button>
          {id ? (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="gap-1.5"
              disabled={busyId === id}
              onClick={() => void setArchived(id, !archived)}
            >
              {archived ? (
                <>
                  <ArrowCounterClockwise className="h-4 w-4" weight="bold" aria-hidden />
                  Restore
                </>
              ) : (
                <>
                  <Archive className="h-4 w-4" weight="bold" aria-hidden />
                  Archive
                </>
              )}
            </Button>
          ) : null}
        </div>
      </div>
    )
  }

  const ctx = findNodeContext(workspace, selection.nodeId) as ReturnType<typeof findNodeContext> & {
    isCluster?: boolean
    clusterId?: string
    clusterCount?: number
  }
  const related = connectedRelationships(workspace, selection.nodeId)
  const askHref = `/ai?prompt=${encodeURIComponent(
    buildAskPrompt("node", `${entityTypeLabel(ctx.entityType)} ${ctx.label}`),
  )}`

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-2 border-b border-divide px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
            {ctx.isSeeded ? "Confirmed organization knowledge" : ctx.isCluster ? "Grouped entities" : entityTypeLabel(ctx.entityType)}
          </p>
          <p className="mt-0.5 truncate text-sm font-semibold text-[color:var(--g-text-primary)]">{ctx.label}</p>
          {!ctx.isSeeded && !ctx.isCluster && ctx.entityId ? (
            <p className="mt-0.5 font-mono text-[10px] text-[color:var(--g-text-muted)]">
              {truncateEntityId(ctx.entityId, 18)}
            </p>
          ) : null}
        </div>
        {onClose ? (
          <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close inspector">
            <X className="h-4 w-4" aria-hidden />
          </Button>
        ) : null}
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {ctx.isCluster && ctx.clusterId ? (
          <>
            <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
              {ctx.clusterCount} similar {entityTypeLabel(ctx.entityType).toLowerCase()} entities share the same learned
              relationship pattern. Expand to inspect individuals.
            </p>
            <Button type="button" size="sm" variant="outline" onClick={() => workspace.expandCluster(ctx.clusterId!)}>
              Expand group
            </Button>
          </>
        ) : null}
        {ctx.isSeeded ? (
          <>
            <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
              An entity your organization explicitly added. Gravitre uses it as a trusted anchor when resolving names.
            </p>
            <SeededNodeEditor workspace={workspace} nodeId={selection.nodeId} />
          </>
        ) : !ctx.isCluster ? (
          <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
            Appears in learned relationships from agent activity, indexed sources, and glossary terms.
          </p>
        ) : null}
        {related.length > 0 ? (
          <div>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
              Connected ({related.length})
            </p>
            <ul className="space-y-2">
              {related.slice(0, 8).map((rel) => {
                const edgeId = relationshipEdgeId(rel)
                return (
                  <li key={edgeId}>
                    <button
                      type="button"
                      className="w-full rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-2.5 py-2 text-left text-xs hover:bg-[color:var(--g-surface-2)]"
                      onClick={() => setSelection({ kind: "edge", edgeId })}
                    >
                      <span className="font-medium">{relationshipTypeLabel(String(rel.relationship_type ?? ""))}</span>
                      <span className="text-[color:var(--g-text-muted)]">
                        {" "}
                        · {readNumber(rel.evidence_count)} sources
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ) : null}
        {ctx.entityType && ctx.entityId && !ctx.isCluster ? (
          <MultiHopPaths workspace={workspace} entityType={ctx.entityType} entityId={ctx.entityId} />
        ) : null}
      </div>
      <div className="flex flex-col gap-2 border-t border-divide p-4">
        <Button type="button" variant="outline" size="sm" className="gap-2" asChild>
          <Link href={askHref}>
            <NucleoAgent className="h-4 w-4" aria-hidden />
            Ask Gravitre AI
          </Link>
        </Button>
        {ctx.isSeeded && ctx.knowledgeNodeId ? (
          <Button type="button" size="sm" variant="ghost" onClick={() => void removeNode(ctx.knowledgeNodeId!)}>
            Remove node
          </Button>
        ) : null}
      </div>
    </div>
  )
}
