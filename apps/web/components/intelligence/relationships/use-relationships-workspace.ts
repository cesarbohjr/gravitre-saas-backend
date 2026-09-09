"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import { intelligenceApi, type IntelligenceSnapshot } from "@/lib/api"
import {
  buildEntityLabelMap,
  collectRelationshipTypes,
  countNeedsReview,
  countNewThisWeek,
  entityKey,
  filterAndSortRelationships,
  makeLabelFor,
  readNumber,
} from "@/lib/relationships-graph/utils"
import type { AddNodeMode, RelationshipRow, Selection, SortKey, ViewMode } from "@/lib/relationships-graph/types"

const PAGE_SIZE = 20
const PRIMARY_NODE_TYPES = ["company", "employee", "customer", "vendor", "product"] as const

export function useRelationshipsWorkspace({
  data,
  isLoading,
  enabled,
}: {
  data: IntelligenceSnapshot | undefined
  isLoading: boolean
  enabled: boolean
}) {
  const [query, setQuery] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [sortKey, setSortKey] = useState<SortKey>("recent")
  const [page, setPage] = useState(0)
  const [showArchived, setShowArchived] = useState(false)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>("graph")
  const [selection, setSelection] = useState<Selection>(null)
  const [addNodeOpen, setAddNodeOpen] = useState(false)
  const [addNodeMode, setAddNodeMode] = useState<AddNodeMode>("entity")
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [showTestData, setShowTestData] = useState(false)
  const [perspective, setPerspective] = useState("all")
  const [expandedClusters, setExpandedClusters] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    if (typeof window === "undefined") return
    if (window.matchMedia("(max-width: 767px)").matches) {
      setViewMode("table")
    }
  }, [])

  useEffect(() => {
    if (selection) setInspectorOpen(true)
  }, [selection])

  const glossary = (data?.glossary ?? []) as RelationshipRow[]
  const glossaryById = useMemo(
    () => Object.fromEntries(glossary.map((term) => [String(term.id ?? ""), String(term.term ?? "")])),
    [glossary],
  )
  const listKey = enabled
    ? ["admin/intelligence/relationships-list", showArchived ? "archived" : "active"]
    : null
  const {
    data: listData,
    isLoading: listLoading,
    mutate: mutateList,
  } = useSWR(listKey, () =>
    intelligenceApi.relationships({
      includeArchived: showArchived,
      limit: 500,
    }),
  )

  const relationships = useMemo(() => {
    const fromApi = (listData?.relationships as RelationshipRow[] | undefined) ?? []
    if (fromApi.length > 0) return fromApi
    return ((data?.entityRelationships ?? []) as RelationshipRow[]).filter((r) =>
      showArchived ? true : !r.archived_at,
    )
  }, [listData, data?.entityRelationships, showArchived])

  const nodesKey = enabled ? ["admin/intelligence/knowledge-nodes"] : null
  const {
    data: nodesData,
    isLoading: nodesLoading,
    mutate: mutateNodes,
  } = useSWR(nodesKey, () => intelligenceApi.knowledgeNodes({ limit: 100 }))

  const graphKey = enabled ? "admin/intelligence/knowledge-graph" : null
  const { data: graphSummary, isLoading: graphSummaryLoading } = useSWR(graphKey, () =>
    intelligenceApi.knowledgeGraph(),
  )

  const nodes = (nodesData?.nodes ?? []) as RelationshipRow[]
  const nodeTypes = nodesData?.primaryNodeTypes?.length
    ? nodesData.primaryNodeTypes
    : [...PRIMARY_NODE_TYPES]

  const entityLabelMap = useMemo(() => buildEntityLabelMap(relationships), [relationships])

  const knowledgeNodeNames = useMemo(
    () =>
      Object.fromEntries(
        nodes.map((n) => [String(n.id ?? ""), String(n.name ?? "")]).filter(([id]) => id),
      ),
    [nodes],
  )

  const labelFor = useMemo(
    () => makeLabelFor(glossaryById, entityLabelMap, knowledgeNodeNames),
    [glossaryById, entityLabelMap, knowledgeNodeNames],
  )

  const relationshipTypes = useMemo(() => collectRelationshipTypes(relationships), [relationships])

  const filtered = useMemo(
    () =>
      filterAndSortRelationships(relationships, {
        query,
        typeFilter,
        sortKey,
        labelFor,
        showTestData,
        perspective,
      }),
    [relationships, query, typeFilter, sortKey, labelFor, showTestData, perspective],
  )

  function openAddNode(mode: AddNodeMode) {
    setAddNodeMode(mode)
    setAddNodeOpen(true)
  }

  function expandCluster(clusterId: string) {
    setExpandedClusters((prev) => new Set(prev).add(clusterId))
  }

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE)

  const activeRelationships = useMemo(
    () => relationships.filter((rel) => !rel.archived_at),
    [relationships],
  )

  const metrics = useMemo(
    () => ({
      seededNodes: nodes.length,
      learnedRelationships: activeRelationships.length,
      needsReview: countNeedsReview(activeRelationships),
      newThisWeek: countNewThisWeek(activeRelationships),
      avgConfidence: readNumber(graphSummary?.avg_relationship_confidence),
    }),
    [nodes.length, activeRelationships, graphSummary],
  )

  async function setArchived(id: string, archived: boolean) {
    setBusyId(id)
    try {
      const res = await intelligenceApi.setRelationshipArchived(id, archived)
      if (!res?.ok) {
        toast.error(archived ? "Could not archive relationship" : "Could not restore relationship")
        return
      }
      toast.success(archived ? "Relationship archived" : "Relationship restored")
      if (selection?.kind === "edge" && selection.edgeId === id && archived) {
        setSelection(null)
      }
      await mutateList()
    } catch {
      toast.error("Request failed. Try again.")
    } finally {
      setBusyId(null)
    }
  }

  function focusExistingEntity(entityType: string, entityId: string, _label?: string) {
    const nodeId = entityId.includes("::") ? entityId : entityKey(entityType, entityId)
    const seeded = nodes.find((n) => String(n.id) === entityId)
    setSelection({
      kind: "node",
      nodeId: seeded ? `seed::${entityId}` : nodeId,
    })
    setInspectorOpen(true)
    setViewMode("graph")
  }

  async function createNode(nodeType: string, nodeName: string): Promise<{ ok: boolean; nodeId?: string }> {
    const name = nodeName.trim()
    if (!name) {
      toast.error("Name is required")
      return { ok: false }
    }
    try {
      const res = await intelligenceApi.createKnowledgeNode({ nodeType, name })
      const nodeId = String(res?.node?.id ?? "")
      toast.success(
        addNodeMode === "first"
          ? "Entity added. Gravitre will use it as confirmed organization knowledge."
          : "Knowledge node created",
      )
      await mutateNodes()
      if (nodeId) {
        focusExistingEntity(nodeType, nodeId)
      }
      return { ok: true, nodeId: nodeId || undefined }
    } catch {
      toast.error("Could not create knowledge node")
      return { ok: false }
    }
  }

  async function removeNode(id: string) {
    try {
      await intelligenceApi.deleteKnowledgeNode(id)
      toast.success("Knowledge node removed")
      if (selection?.kind === "node") {
        const nodeId = selection.nodeId
        if (nodeId === `seed::${id}` || nodeId.endsWith(`::${id}`)) {
          setSelection(null)
          setInspectorOpen(false)
        }
      }
      await mutateNodes()
      return true
    } catch {
      toast.error("Could not delete knowledge node")
      return false
    }
  }

  async function updateNode(id: string, nodeType: string, nodeName: string) {
    const name = nodeName.trim()
    if (!name) {
      toast.error("Name is required")
      return false
    }
    try {
      await intelligenceApi.updateKnowledgeNode(id, { nodeType, name })
      toast.success("Knowledge node updated")
      await mutateNodes()
      return true
    } catch {
      toast.error("Could not update knowledge node")
      return false
    }
  }

  const loading = isLoading || listLoading

  return {
    glossary,
    glossaryById,
    labelFor,
    relationships,
    filtered,
    pageRows,
    pageCount,
    safePage,
    pageSize: PAGE_SIZE,
    nodes,
    nodeTypes,
    relationshipTypes,
    graphSummary,
    metrics,
    query,
    setQuery,
    typeFilter,
    setTypeFilter,
    sortKey,
    setSortKey,
    page,
    setPage,
    showArchived,
    setShowArchived,
    busyId,
    viewMode,
    setViewMode,
    selection,
    setSelection,
    addNodeOpen,
    setAddNodeOpen,
    addNodeMode,
    openAddNode,
    inspectorOpen,
    setInspectorOpen,
    showTestData,
    setShowTestData,
    perspective,
    setPerspective,
    expandedClusters,
    expandCluster,
    loading,
    nodesLoading,
    graphSummaryLoading,
    enabled,
    setArchived,
    createNode,
    focusExistingEntity,
    removeNode,
    updateNode,
  }
}

export type RelationshipsWorkspaceState = ReturnType<typeof useRelationshipsWorkspace>
