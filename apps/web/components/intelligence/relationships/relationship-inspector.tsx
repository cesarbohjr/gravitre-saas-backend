"use client"

import Link from "next/link"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { NucleoAgent } from "@/components/icons/nucleo/semantic"
import { entityTypeLabel, relationshipTypeLabel } from "@/lib/learning-ui-copy"
import {
  confidenceLabel,
  confidenceTone,
  entityKey,
  readNumber,
  relationshipEdgeId,
} from "@/lib/relationships-graph/utils"
import type { RelationshipRow } from "@/lib/relationships-graph/types"
import { formatTime } from "@/app/admin/intelligence/_components/shared"
import { Archive, ArrowCounterClockwise, X } from "@phosphor-icons/react"
import type { RelationshipsWorkspaceState } from "./use-relationships-workspace"

function buildAskPrompt(kind: "node" | "edge", detail: string): string {
  return `Help me understand this ${kind === "node" ? "entity" : "relationship"} in our organization knowledge graph: ${detail}. What does Gravitre know about it and how was it learned?`
}

function findRelationship(workspace: RelationshipsWorkspaceState, edgeId: string): RelationshipRow | undefined {
  return workspace.filtered.find((rel) => relationshipEdgeId(rel) === edgeId)
}

function findNodeContext(workspace: RelationshipsWorkspaceState, nodeId: string) {
  if (nodeId.startsWith("seed::")) {
    const knId = nodeId.slice("seed::".length)
    const node = workspace.nodes.find((n) => String(n.id) === knId)
    if (node) {
      return {
        label: String(node.name ?? knId),
        entityType: String(node.node_type ?? ""),
        knowledgeNodeId: knId,
        isSeeded: true,
      }
    }
  }
  const [entityType, ...rest] = nodeId.split("::")
  const entityId = rest.join("::")
  return {
    label: workspace.labelFor(entityType, entityId),
    entityType,
    entityId,
    isSeeded: false,
  }
}

function connectedRelationships(workspace: RelationshipsWorkspaceState, nodeId: string) {
  let entityType = ""
  let entityId = ""
  if (nodeId.startsWith("seed::")) {
    const knId = nodeId.slice("seed::".length)
    const node = workspace.nodes.find((n) => String(n.id) === knId)
    if (!node) return []
    entityType = String(node.node_type ?? "")
    entityId = knId
  } else {
    const parts = nodeId.split("::")
    entityType = parts[0] ?? ""
    entityId = parts.slice(1).join("::")
  }
  const key = entityKey(entityType, entityId)
  return workspace.filtered.filter((rel) => {
    const src = entityKey(rel.source_entity_type, rel.source_entity_id)
    const tgt = entityKey(rel.target_entity_type, rel.target_entity_id)
    return src === key || tgt === key
  })
}

export function RelationshipInspector({
  workspace,
  onClose,
}: {
  workspace: RelationshipsWorkspaceState
  onClose?: () => void
}) {
  const { selection, setArchived, busyId, removeNode } = workspace

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
          <dl className="grid gap-2 text-sm">
            <div>
              <dt className="text-[11px] text-[color:var(--g-text-muted)]">Last observed</dt>
              <dd>{formatTime(rel.last_observed_at ?? rel.created_at)}</dd>
            </div>
            <div>
              <dt className="text-[11px] text-[color:var(--g-text-muted)]">How Gravitre learned this</dt>
              <dd className="leading-relaxed text-[color:var(--g-text-secondary)]">
                Inferred from indexed sources and glossary terms. Confidence is a heuristic estimate, not an ML score.
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

  const ctx = findNodeContext(workspace, selection.nodeId)
  const related = connectedRelationships(workspace, selection.nodeId)
  const askHref = `/ai?prompt=${encodeURIComponent(
    buildAskPrompt("node", `${entityTypeLabel(ctx.entityType)} ${ctx.label}`),
  )}`

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-start justify-between gap-2 border-b border-divide px-4 py-3">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
            {ctx.isSeeded ? "Organization knowledge" : entityTypeLabel(ctx.entityType)}
          </p>
          <p className="mt-0.5 truncate text-sm font-semibold text-[color:var(--g-text-primary)]">{ctx.label}</p>
        </div>
        {onClose ? (
          <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close inspector">
            <X className="h-4 w-4" aria-hidden />
          </Button>
        ) : null}
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {ctx.isSeeded ? (
          <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
            Seeded entity your team added. Agents use it to resolve names in your org.
          </p>
        ) : (
          <p className="text-sm leading-relaxed text-[color:var(--g-text-secondary)]">
            Appears in learned relationships from indexed sources and glossary terms.
          </p>
        )}
        {related.length > 0 ? (
          <div>
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-[color:var(--g-text-muted)]">
              Connected ({related.length})
            </p>
            <ul className="space-y-2">
              {related.slice(0, 8).map((rel) => (
                <li
                  key={relationshipEdgeId(rel)}
                  className="rounded-md border border-divide bg-[color:var(--g-surface-2)]/50 px-2.5 py-2 text-xs"
                >
                  <span className="font-medium">{relationshipTypeLabel(String(rel.relationship_type ?? ""))}</span>
                  <span className="text-[color:var(--g-text-muted)]">
                    {" "}
                    · {readNumber(rel.evidence_count)} sources
                  </span>
                </li>
              ))}
            </ul>
          </div>
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
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => void removeNode(ctx.knowledgeNodeId!)}
          >
            Remove node
          </Button>
        ) : null}
      </div>
    </div>
  )
}
