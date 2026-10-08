"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import type { FormEvent } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import {
  ShieldCheck,
  Package,
  GitBranch,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react"
import { WorkDecisionDialog } from "@/components/gravitre/work-decision-dialog"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { AppShell } from "@/components/gravitre/app-shell"
import {
  GravitreEmpty,
  GravitreMetric,
  GravitrePageHeader,
  GravitreSurface,
} from "@/components/gravitre/nodus-product"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { mcpAdminApi, portableCapabilitiesApi } from "@/lib/api"
import type { MCPAdminServer } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { toast } from "sonner"

function riskLabel(value?: string) {
  if (!value) return "Unknown"
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function packageHasMcp(inspection?: Record<string, unknown>) {
  const components = inspection?.components
  return (
    Array.isArray(components) &&
    components.some((component) => {
      if (!component || typeof component !== "object") return false
      return (component as Record<string, unknown>).kind === "mcp"
    })
  )
}

function canPublishPackage(item: {
  source_uri?: string | null
  source_commit_sha?: string | null
  content_digest?: string | null
  signature_status?: string
  publisher_trusted?: boolean
  publisher_verified?: boolean
}) {
  const gitPinned = Boolean(
    item.source_uri && item.source_commit_sha && item.content_digest,
  )
  const trustedSigned = Boolean(
    item.content_digest &&
    item.signature_status === "verified" &&
    (item.publisher_trusted || item.publisher_verified),
  )
  return gitPinned || trustedSigned
}

type CapabilityFilter =
  | "all"
  | "skills"
  | "plugins"
  | "mcp"
  | "connectors"
  | "agents"
  | "plays"
  | "templates"
  | "triggers"

function packageMatchesFilter(
  item: {
    package_format?: string
    inspection?: Record<string, unknown>
  },
  filter: CapabilityFilter,
) {
  if (filter === "all") return true
  const format = String(item.package_format ?? "").toLowerCase()
  const components = Array.isArray(item.inspection?.components)
    ? (item.inspection?.components as Array<Record<string, unknown>>)
    : []
  const kinds = new Set(
    components.map((row) => String(row.kind ?? "").toLowerCase()),
  )
  if (filter === "skills") return format === "agent_skill" || kinds.has("skill")
  if (filter === "plugins")
    return format.includes("plugin") || format === "gravitre"
  if (filter === "mcp") return format === "mcp" || kinds.has("mcp")
  if (filter === "connectors") return kinds.has("connector")
  if (filter === "agents") return kinds.has("agent")
  if (filter === "plays") return kinds.has("play")
  if (filter === "templates") return kinds.has("template")
  if (filter === "triggers") return kinds.has("trigger")
  return true
}

function nativeBindableComponents(item?: {
  inspection?: Record<string, unknown>
}) {
  const rows = Array.isArray(item?.inspection?.components)
    ? (item?.inspection?.components as Array<Record<string, unknown>>)
    : []
  return rows
    .map((row) => ({
      kind: String(row.kind ?? ""),
      name: String(row.name ?? ""),
    }))
    .filter(
      (
        row,
      ): row is {
        kind: "agent" | "play" | "template" | "trigger"
        name: string
      } =>
        ["agent", "play", "template", "trigger"].includes(row.kind) &&
        Boolean(row.name),
    )
}

function targetTypesForComponent(
  kind: "agent" | "play" | "template" | "trigger",
) {
  if (kind === "agent") return ["agent"] as const
  if (kind === "play") return ["play", "workflow"] as const
  if (kind === "template") return ["marketplace_asset"] as const
  return ["workflow_schedule"] as const
}

function securitySummary(scan?: {
  findings?: Array<{ severity?: string }>
  externalHosts?: string[]
  oauthScopes?: string[]
  requiredSecrets?: string[]
}) {
  const findings = scan?.findings ?? []
  const important = findings.filter(
    (row) => row.severity === "critical" || row.severity === "high",
  ).length
  return {
    important: scan?.findings ? important : "Not reported",
    hosts: scan?.externalHosts?.length ?? "Not reported",
    scopes: scan?.oauthScopes?.length ?? "Not reported",
    secrets: scan?.requiredSecrets?.length ?? "Not reported",
  }
}

export default function CapabilityMarketplacePage() {
  const { user } = useAuth()
  const { isAdmin, loading: adminLoading } = useOrgAdmin()
  const router = useRouter()
  const [name, setName] = useState("")
  const [repositoryUrl, setRepositoryUrl] = useState("")
  const [branch, setBranch] = useState("main")
  const [marketplaceRootPath, setMarketplaceRootPath] = useState("")
  const [marketplaceAutoSync, setMarketplaceAutoSync] = useState(false)
  const [busy, setBusy] = useState(false)
  const [packageBusy, setPackageBusy] = useState<string | null>(null)
  const [sourceBusy, setSourceBusy] = useState<string | null>(null)
  const [mcpCredentialInputs, setMcpCredentialInputs] = useState<
    Record<string, { secret: string; header: string }>
  >({})
  const [mcpBusy, setMcpBusy] = useState<string | null>(null)
  const [historyPackageId, setHistoryPackageId] = useState<string | null>(null)
  const [historyBusy, setHistoryBusy] = useState<string | null>(null)
  const [trustedPublisherName, setTrustedPublisherName] = useState("")
  const [trustedPublisherKey, setTrustedPublisherKey] = useState("")
  const [trustedPublisherMarketplaceSlug, setTrustedPublisherMarketplaceSlug] =
    useState("")
  const [trustBusy, setTrustBusy] = useState(false)
  const [zipFile, setZipFile] = useState<File | null>(null)
  const [zipSigningPublicKey, setZipSigningPublicKey] = useState("")
  const [zipSignature, setZipSignature] = useState("")
  const [zipBusy, setZipBusy] = useState(false)
  const [zipInspection, setZipInspection] = useState<Awaited<
    ReturnType<typeof portableCapabilitiesApi.inspectZip>
  > | null>(null)
  const [capabilityFilter, setCapabilityFilter] =
    useState<CapabilityFilter>("all")
  const [publishValidation, setPublishValidation] = useState<
    Record<
      string,
      Awaited<ReturnType<typeof portableCapabilitiesApi.validatePackage>>
    >
  >({})
  const [bindingPackageId, setBindingPackageId] = useState<string | null>(null)
  const [bindingComponentKey, setBindingComponentKey] = useState("")
  const [bindingTargetType, setBindingTargetType] = useState("")
  const [bindingTargetId, setBindingTargetId] = useState("")
  const [bindingBusy, setBindingBusy] = useState(false)
  const [communitySearch, setCommunitySearch] = useState("")
  const [communityBusy, setCommunityBusy] = useState<string | null>(null)

  const developerKit = useSWR(
    user && isAdmin ? "portable-capability-developer-kit" : null,
    () => portableCapabilitiesApi.developerKit(),
  )
  const communityCatalog = useSWR(
    user && isAdmin ? "portable-capability-community-catalog" : null,
    () => portableCapabilitiesApi.listCommunityCatalog(),
    { revalidateOnFocus: false },
  )
  const packages = useSWR(
    user && isAdmin ? "portable-capability-packages" : null,
    () => portableCapabilitiesApi.listPackages(),
  )
  const usage = useSWR(
    user && isAdmin ? "portable-capability-usage-30d" : null,
    () => portableCapabilitiesApi.usage(30),
  )
  const marketplaces = useSWR(
    user && isAdmin ? "portable-capability-marketplaces" : null,
    () => portableCapabilitiesApi.listMarketplaces(),
  )
  const trustedPublishers = useSWR(
    user && isAdmin ? "portable-capability-trusted-publishers" : null,
    () => portableCapabilitiesApi.listTrustedPublishers(),
  )
  const candidates = useSWR(
    user && isAdmin ? "portable-capability-marketplace-candidates" : null,
    () => portableCapabilitiesApi.listCandidates(),
  )
  const mcpServers = useSWR(
    user && isAdmin ? "portable-capability-mcp-servers" : null,
    () => mcpAdminApi.listServers(),
  )
  const mcpTools = useSWR(
    user && isAdmin ? "portable-capability-mcp-tools" : null,
    () => mcpAdminApi.listTools(),
  )
  const packageVersions = useSWR(
    user && isAdmin && historyPackageId
      ? ["portable-capability-versions", historyPackageId]
      : null,
    () => portableCapabilitiesApi.listVersions(historyPackageId!),
  )
  const nativeBindings = useSWR(
    user && isAdmin && bindingPackageId
      ? ["portable-capability-bindings", bindingPackageId]
      : null,
    () => portableCapabilitiesApi.listBindings(bindingPackageId!),
  )

  const packageRows = packages.data?.items ?? []
  const normalizedCommunitySearch = communitySearch.trim().toLowerCase()
  const communityItems = useMemo(() => {
    const rows = communityCatalog.data?.items ?? []
    if (!normalizedCommunitySearch) return rows
    return rows.filter(
      (item) =>
        item.name.toLowerCase().includes(normalizedCommunitySearch) ||
        item.publisher.toLowerCase().includes(normalizedCommunitySearch) ||
        item.packagePath.toLowerCase().includes(normalizedCommunitySearch),
    )
  }, [communityCatalog.data?.items, normalizedCommunitySearch])
  const filteredPackageRows = packageRows.filter((item) =>
    packageMatchesFilter(item, capabilityFilter),
  )
  const marketplaceRows = marketplaces.data?.items ?? []
  const candidateRows = candidates.data?.items ?? []
  const portableMcpServers = (mcpServers.data?.servers ?? []).filter((server) =>
    Boolean(server.source_capability_package_id),
  )
  const portableMcpTools = mcpTools.data?.tools ?? []
  const pendingCandidates = candidateRows.filter(
    (row) => row.status === "pending_review",
  )
  const quarantined = packageRows.filter(
    (row) => row.status === "quarantined",
  ).length
  const signed = packageRows.filter(
    (row) => row.signature_status === "verified",
  ).length
  const bindablePackages = packageRows.filter(
    (item) =>
      item.status === "installed" && nativeBindableComponents(item).length > 0,
  )
  const bindingPackage = packageRows.find(
    (item) => item.id === bindingPackageId,
  )
  const bindingComponents = nativeBindableComponents(bindingPackage)
  const selectedBindingComponent = bindingComponents.find(
    (row) => `${row.kind}:${row.name}` === bindingComponentKey,
  )
  const bindingTargetTypes = selectedBindingComponent
    ? targetTypesForComponent(selectedBindingComponent.kind)
    : []

  useEffect(() => {
    if (user && !adminLoading && !isAdmin) {
      router.replace("/marketplace/assets")
    }
  }, [adminLoading, isAdmin, router, user])

  const operationLocks = useRef<Record<string, boolean>>({})
  const [decision, setDecision] = useState<{
    title: string
    description: string
    actionLabel: string
    destructive?: boolean
    onConfirm: () => Promise<void>
  } | null>(null)

  async function stageCommunitySource(sourceKey: string) {
    if (operationLocks.current.community) return
    operationLocks.current.community = true
    setCommunityBusy(sourceKey)
    try {
      const result =
        await portableCapabilitiesApi.stageCommunityCatalog(sourceKey)
      toast.success("Official capability catalog staged", {
        description: `${result.sync.ingested} package${result.sync.ingested === 1 ? "" : "s"} added to the admin review queue. Nothing was installed automatically.`,
      })
      await Promise.allSettled([
        communityCatalog.mutate(),
        marketplaces.mutate(),
        candidates.mutate(),
      ])
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not stage official capability catalog",
      )
    } finally {
      operationLocks.current.community = false
      setCommunityBusy(null)
    }
  }

  async function createNativeBinding(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (
      !bindingPackageId ||
      !selectedBindingComponent ||
      !bindingTargetType ||
      !bindingTargetId.trim()
    )
      return
    if (operationLocks.current.binding) return
    operationLocks.current.binding = true
    setBindingBusy(true)
    try {
      const result = await portableCapabilitiesApi.createBinding(
        bindingPackageId,
        {
          componentKind: selectedBindingComponent.kind,
          componentName: selectedBindingComponent.name,
          targetType: bindingTargetType as
            | "agent"
            | "play"
            | "workflow"
            | "workflow_schedule"
            | "marketplace_asset",
          targetId: bindingTargetId.trim(),
        },
      )
      if (!result.binding?.id)
        throw new Error(
          "No binding was returned. Refresh bindings before trying again.",
        )
      toast.success("Native capability binding created")
      setBindingTargetId("")
      await Promise.allSettled([nativeBindings.mutate()])
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not create native binding",
      )
    } finally {
      operationLocks.current.binding = false
      setBindingBusy(false)
    }
  }

  async function deleteNativeBinding(bindingId: string) {
    if (!bindingPackageId) return
    if (operationLocks.current.binding)
      throw new Error(
        "Another operation is still pending. Try again when it finishes.",
      )
    operationLocks.current.binding = true
    setBindingBusy(true)
    try {
      const result = await portableCapabilitiesApi.deleteBinding(
        bindingPackageId,
        bindingId,
      )
      if (result.deleted !== true)
        throw new Error("The server did not confirm binding removal.")
      toast.success("Native capability binding removed")
      await Promise.allSettled([nativeBindings.mutate()])
    } finally {
      operationLocks.current.binding = false
      setBindingBusy(false)
    }
  }

  async function inspectZip() {
    if (!zipFile) return
    if (operationLocks.current.zip) return
    operationLocks.current.zip = true
    setZipBusy(true)
    try {
      const result = await portableCapabilitiesApi.inspectZip(zipFile)
      setZipInspection(result)
      if (result.installationAllowed) {
        toast.success("ZIP inspection complete")
      } else {
        toast.error("This package is blocked by capability policy")
      }
    } catch (error) {
      setZipInspection(null)
      toast.error(
        error instanceof Error ? error.message : "ZIP inspection failed",
      )
    } finally {
      operationLocks.current.zip = false
      setZipBusy(false)
    }
  }

  async function installZip() {
    if (!zipFile || !zipInspection?.installationAllowed || !isAdmin) return
    if (operationLocks.current.zip) return
    operationLocks.current.zip = true
    setZipBusy(true)
    try {
      const hasSignatureInputs = Boolean(
        zipSigningPublicKey.trim() || zipSignature.trim(),
      )
      if (
        hasSignatureInputs &&
        (!zipSigningPublicKey.trim() || !zipSignature.trim())
      ) {
        toast.error(
          "Provide both the publisher public key and signature, or leave both blank",
        )
        return
      }
      const result = await portableCapabilitiesApi.installZip(zipFile, {
        signingPublicKeyPem: zipSigningPublicKey.trim() || undefined,
        signature: zipSignature.trim() || undefined,
      })
      if (!result.package?.id)
        throw new Error(
          "No package was returned. Refresh packages before installing again.",
        )
      toast.success("Portable package stored", {
        description: `Returned status: ${result.package.status ?? "Not reported"}. Direct execution stays disabled.`,
      })
      setZipFile(null)
      setZipSigningPublicKey("")
      setZipSignature("")
      setZipInspection(null)
      await Promise.allSettled([packages.mutate()])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "ZIP install failed")
    } finally {
      operationLocks.current.zip = false
      setZipBusy(false)
    }
  }

  async function addTrustedPublisher(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trustedPublisherName.trim() || !trustedPublisherKey.trim()) return
    if (operationLocks.current.trust) return
    operationLocks.current.trust = true
    setTrustBusy(true)
    try {
      await portableCapabilitiesApi.addTrustedPublisher({
        publisherName: trustedPublisherName.trim(),
        publicKeyPem: trustedPublisherKey.trim(),
        marketplacePublisherSlug:
          trustedPublisherMarketplaceSlug.trim() || undefined,
      })
      toast.success("Publisher signing key trusted")
      setTrustedPublisherName("")
      setTrustedPublisherKey("")
      setTrustedPublisherMarketplaceSlug("")
      await trustedPublishers.mutate()
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not trust publisher key",
      )
    } finally {
      operationLocks.current.trust = false
      setTrustBusy(false)
    }
  }

  async function addMarketplace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || !repositoryUrl.trim()) return
    if (operationLocks.current.source) return
    operationLocks.current.source = true
    setBusy(true)
    try {
      await portableCapabilitiesApi.addMarketplace({
        name: name.trim(),
        repositoryUrl: repositoryUrl.trim(),
        branch: branch.trim() || "main",
        rootPath: marketplaceRootPath.trim() || undefined,
        autoSync: marketplaceAutoSync,
        approvalRequired: true,
      })
      toast.success("Private capability marketplace added")
      setName("")
      setRepositoryUrl("")
      setBranch("main")
      setMarketplaceRootPath("")
      setMarketplaceAutoSync(false)
      await Promise.allSettled([marketplaces.mutate()])
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not add marketplace",
      )
    } finally {
      operationLocks.current.source = false
      setBusy(false)
    }
  }

  async function reviewPackage(
    packageId: string,
    status: "installed" | "quarantined" | "disabled",
  ) {
    if (operationLocks.current.package)
      throw new Error(
        "Another operation is still pending. Try again when it finishes.",
      )
    operationLocks.current.package = true
    setPackageBusy(packageId)
    try {
      const result = await portableCapabilitiesApi.reviewPackage(packageId, {
        status,
      })
      if (result.reviewed !== true || result.package?.status !== status)
        throw new Error(
          "The server did not confirm the requested capability status.",
        )
      toast.success(
        status === "installed"
          ? "Capability approved"
          : status === "disabled"
            ? "Capability disabled"
            : "Capability quarantined",
      )
      await Promise.allSettled([packages.mutate()])
    } finally {
      operationLocks.current.package = false
      setPackageBusy(null)
    }
  }

  async function validatePackage(packageId: string) {
    if (operationLocks.current.package) return
    operationLocks.current.package = true
    setPackageBusy(packageId)
    try {
      const report = await portableCapabilitiesApi.validatePackage(packageId)
      setPublishValidation((current) => ({ ...current, [packageId]: report }))
      toast.success(
        report.readyForMarketplace
          ? "Capability passes Marketplace preflight"
          : "Capability needs changes before publishing",
        {
          description: report.readyForMarketplace
            ? report.warningCount
              ? `${report.warningCount} warning${report.warningCount === 1 ? "" : "s"} to review`
              : "All required static checks passed"
            : `${report.errorCount} blocking check${report.errorCount === 1 ? "" : "s"} failed`,
        },
      )
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Capability validation failed",
      )
    } finally {
      operationLocks.current.package = false
      setPackageBusy(null)
    }
  }

  async function prepareMcp(packageId: string) {
    if (operationLocks.current.package) return
    operationLocks.current.package = true
    setPackageBusy(packageId)
    try {
      const result = await portableCapabilitiesApi.prepareMcp(packageId)
      toast.success("MCP dependencies prepared", {
        description: `${result.prepared.length} server${result.prepared.length === 1 ? "" : "s"} pending review${result.blocked.length ? `; ${result.blocked.length} blocked by policy` : ""}`,
      })
      await Promise.allSettled([mcpServers.mutate(), mcpTools.mutate()])
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "MCP preparation failed",
      )
    } finally {
      operationLocks.current.package = false
      setPackageBusy(null)
    }
  }

  async function discoverMcp(serverId: string) {
    if (operationLocks.current.mcp) return
    operationLocks.current.mcp = true
    setMcpBusy(serverId)
    try {
      const result = await mcpAdminApi.discoverTools(serverId)
      toast.success("MCP tools discovered", {
        description: `${result.count} tool${result.count === 1 ? "" : "s"} found. Portable-package tools remain disabled until approved.`,
      })
      await Promise.allSettled([mcpTools.mutate()])
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "MCP discovery failed",
      )
    } finally {
      operationLocks.current.mcp = false
      setMcpBusy(null)
    }
  }

  async function saveMcpCredentials(server: MCPAdminServer) {
    const values = mcpCredentialInputs[server.id] ?? {
      secret: "",
      header: "X-API-Key",
    }
    if (server.auth_type !== "bearer" && server.auth_type !== "api_key") return
    if (!values.secret.trim()) {
      toast.error(
        server.auth_type === "bearer"
          ? "Enter a bearer token"
          : "Enter an API key",
      )
      return
    }
    if (operationLocks.current.mcp) return
    operationLocks.current.mcp = true
    setMcpBusy(server.id)
    try {
      const result = await mcpAdminApi.configureServerAuth(server.id, {
        authType: server.auth_type,
        authConfig:
          server.auth_type === "bearer"
            ? { bearer_token: values.secret.trim() }
            : {
                api_key: values.secret.trim(),
                header: values.header.trim() || "X-API-Key",
              },
      })
      if (result.credentialsStored !== true)
        throw new Error("The server did not confirm credential storage.")
      setMcpCredentialInputs((current) => ({
        ...current,
        [server.id]: { secret: "", header: values.header || "X-API-Key" },
      }))
      toast.success("MCP credentials stored securely")
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "MCP credential update failed",
      )
    } finally {
      operationLocks.current.mcp = false
      setMcpBusy(null)
    }
  }

  async function setMcpServerEnabled(serverId: string, enabled: boolean) {
    if (operationLocks.current.mcp)
      throw new Error(
        "Another operation is still pending. Try again when it finishes.",
      )
    operationLocks.current.mcp = true
    setMcpBusy(serverId)
    try {
      const result = await mcpAdminApi.patchServer(serverId, enabled)
      if (result.server?.enabled !== enabled)
        throw new Error("The server did not confirm this MCP server state.")
      toast.success(enabled ? "MCP server approved" : "MCP server disabled")
      await Promise.allSettled([mcpServers.mutate()])
    } finally {
      operationLocks.current.mcp = false
      setMcpBusy(null)
    }
  }

  async function setMcpToolEnabled(toolId: string, enabled: boolean) {
    if (operationLocks.current.mcp)
      throw new Error(
        "Another operation is still pending. Try again when it finishes.",
      )
    operationLocks.current.mcp = true
    setMcpBusy(toolId)
    try {
      const result = await mcpAdminApi.patchTool(toolId, enabled)
      if (result.tool?.enabled !== enabled)
        throw new Error("The server did not confirm this tool state.")
      toast.success(enabled ? "MCP tool enabled" : "MCP tool disabled")
      await Promise.allSettled([mcpTools.mutate()])
    } finally {
      operationLocks.current.mcp = false
      setMcpBusy(null)
    }
  }

  async function syncMarketplace(sourceId: string) {
    if (operationLocks.current.source) return
    operationLocks.current.source = true
    setSourceBusy(sourceId)
    try {
      const result = await portableCapabilitiesApi.syncMarketplace(sourceId)
      toast.success("Capability marketplace synced", {
        description: `${result.sync.ingested} package${result.sync.ingested === 1 ? "" : "s"} staged for review`,
      })
      await Promise.allSettled([
        marketplaces.mutate(),
        packages.mutate(),
        candidates.mutate(),
      ])
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Marketplace sync failed",
      )
    } finally {
      operationLocks.current.source = false
      setSourceBusy(null)
    }
  }

  async function decideCandidate(
    candidateId: string,
    decision: "approve" | "reject",
  ) {
    if (operationLocks.current.package) return
    operationLocks.current.package = true
    setPackageBusy(candidateId)
    try {
      await portableCapabilitiesApi.reviewCandidate(candidateId, { decision })
      toast.success(
        decision === "approve"
          ? "Capability candidate approved"
          : "Capability candidate rejected",
      )
      await candidates.mutate()
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Candidate review failed",
      )
    } finally {
      operationLocks.current.package = false
      setPackageBusy(null)
    }
  }

  async function installCandidate(candidateId: string) {
    if (operationLocks.current.package)
      throw new Error(
        "Another operation is still pending. Try again when it finishes.",
      )
    operationLocks.current.package = true
    setPackageBusy(candidateId)
    try {
      const result = await portableCapabilitiesApi.installCandidate(candidateId)
      if (!result.package?.id)
        throw new Error(
          "No installed package was returned. Refresh the package list before trying again.",
        )
      toast.success("Capability package created", {
        description: `Returned status: ${result.package.status ?? "Not reported"}`,
      })
      await Promise.allSettled([candidates.mutate(), packages.mutate()])
    } finally {
      operationLocks.current.package = false
      setPackageBusy(null)
    }
  }

  async function rollbackVersion(packageId: string, versionId: string) {
    if (operationLocks.current.history)
      throw new Error(
        "Another operation is still pending. Try again when it finishes.",
      )
    operationLocks.current.history = true
    setHistoryBusy(versionId)
    try {
      const result = await portableCapabilitiesApi.rollbackVersion(
        packageId,
        versionId,
      )
      toast.success("Capability version restored", {
        description: result.requiresReview
          ? "The restored package is quarantined and requires review before use."
          : `Returned status: ${result.package?.status ?? result.status ?? "Not reported"}`,
      })
      await Promise.allSettled([packages.mutate(), packageVersions.mutate()])
    } finally {
      operationLocks.current.history = false
      setHistoryBusy(null)
    }
  }
  async function createMarketplaceDraft(item: {
    id?: string
    name: string
    description?: string | null
    source_commit_sha?: string | null
    content_digest?: string | null
    source_uri?: string | null
  }) {
    if (!item.id) return
    const baseSlug =
      item.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 90) || "portable-capability"
    const suffix = item.id.replace(/-/g, "").slice(0, 6).toLowerCase()
    const slug = `${baseSlug}-${suffix}`
    setPackageBusy(item.id)
    try {
      const result = await portableCapabilitiesApi.createMarketplaceDraft(
        item.id,
        {
          slug,
          title: item.name,
          description: item.description || undefined,
        },
      )
      toast.success("Marketplace draft created", {
        description:
          "Review the listing, then submit it through Gravitre's existing publisher review flow.",
      })
      router.push(
        `/marketplace/assets/${encodeURIComponent(result.asset.slug)}`,
      )
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : "Could not create Marketplace draft",
      )
    } finally {
      setPackageBusy(null)
    }
  }

  if (adminLoading || !isAdmin) {
    return (
      <AppShell title="Capabilities">
        <div className="grid min-h-[50vh] place-items-center px-4 text-sm text-muted-foreground">
          {adminLoading
            ? "Checking administrator access…"
            : "Redirecting to Marketplace…"}
        </div>
        {decision ? (
          <WorkDecisionDialog
            {...decision}
            onCancel={() => setDecision(null)}
          />
        ) : null}
      </AppShell>
    )
  }

  return (
    <AppShell title="Capabilities">
      <div
        className="bg-[color:var(--g-canvas)] pb-24 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11"
        data-composition="manage"
      >
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Capabilities"
          description="Install and govern portable skills, plugins, and MCP capability packages while Gravitre retains execution, approval, and verification control."
          icon={<Package className="h-5 w-5" />}
        />

        <div className="mx-auto w-full max-w-6xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          {[
            { name: "Capability usage", result: usage },
            { name: "Marketplace sources", result: marketplaces },
            { name: "Trusted publishers", result: trustedPublishers },
            { name: "Review candidates", result: candidates },
            { name: "MCP servers", result: mcpServers },
            { name: "MCP tools", result: mcpTools },
            { name: "Native bindings", result: nativeBindings },
          ]
            .filter(({ result }) => result.error)
            .map(({ name, result }) => (
              <WorkSectionErrorCard
                key={name}
                title={`Could not refresh ${name.toLowerCase()}`}
                message="Loaded evidence remains available."
                onRetry={() => void result.mutate()}
              />
            ))}
          <section className="grid gap-[var(--np-kpi-gap)] sm:grid-cols-2 lg:grid-cols-4">
            <GravitreMetric
              label="Installed capabilities"
              value={packages.data ? packageRows.length : "Not reported"}
              icon={<Package className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Reasoning selections · 30d"
              value={usage.data?.reasoningSelections ?? "Not reported"}
              icon={<CheckCircle2 className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Signed packages"
              value={packages.data ? signed : "Not reported"}
              icon={<ShieldCheck className="h-4 w-4" />}
            />
            <GravitreMetric
              label="Quarantined"
              value={packages.data ? quarantined : "Not reported"}
              icon={<AlertTriangle className="h-4 w-4" />}
            />
          </section>

          <GravitreSurface>
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-sm font-medium text-foreground">
                      Official skills & plugins
                    </h2>
                    <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                      Admin only
                    </span>
                  </div>
                  <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
                    Browse compatible skills and plugins from official OpenAI
                    and Anthropic catalogs. Discovery is read-only; staging
                    sends packages through Gravitre security scanning and the
                    existing admin review queue before anything can be installed
                    or activated.
                  </p>
                </div>
                <div className="w-full lg:max-w-xs">
                  <Label
                    htmlFor="community-capability-search"
                    className="sr-only"
                  >
                    Search community skills
                  </Label>
                  <Input
                    id="community-capability-search"
                    value={communitySearch}
                    onChange={(event) => setCommunitySearch(event.target.value)}
                    placeholder="Search official skills & plugins…"
                    aria-label="Search official skills and plugins"
                  />
                </div>
              </div>

              {communityCatalog.error ? (
                <div className="rounded border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
                  Official catalog discovery is temporarily unavailable.
                  Installed and staged capabilities remain unaffected.
                </div>
              ) : (
                <>
                  <div className="grid gap-3 md:grid-cols-2">
                    {(communityCatalog.data?.sources ?? []).map((source) => {
                      const count = (communityCatalog.data?.items ?? []).filter(
                        (item) => item.sourceKey === source.key,
                      ).length
                      return (
                        <div
                          key={source.key}
                          className="min-w-0 rounded border border-divide p-3"
                        >
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-foreground">
                                {source.name}
                              </p>
                              <p className="mt-1 text-xs text-muted-foreground">
                                {source.publisher} · {count} discovered{" "}
                                {source.kind === "plugin" ? "plugin" : "skill"}
                                {count === 1 ? "" : "s"} · official source
                              </p>
                            </div>
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              disabled={communityBusy === source.key}
                              onClick={() =>
                                void stageCommunitySource(source.key)
                              }
                            >
                              {communityBusy === source.key
                                ? "Staging…"
                                : "Stage for review"}
                            </Button>
                          </div>
                        </div>
                      )
                    })}
                  </div>

                  {communityCatalog.isLoading ? (
                    <p className="text-xs text-muted-foreground">
                      Loading official capability catalogs…
                    </p>
                  ) : communityItems.length === 0 ? (
                    <GravitreEmpty
                      icon={<Package className="h-5 w-5" />}
                      title={
                        normalizedCommunitySearch
                          ? "No official skills or plugins match your search"
                          : "No official skills or plugins discovered"
                      }
                      hint="Catalog availability is independent from installed capabilities. Retry discovery or add a private Git catalog below."
                    />
                  ) : (
                    <div className="max-h-[420px] overflow-y-auto rounded border border-divide">
                      <ul className="divide-y divide-divide">
                        {communityItems.slice(0, 200).map((item) => (
                          <li
                            key={item.id}
                            className="flex min-w-0 flex-col gap-1 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                          >
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="truncate text-sm font-medium text-foreground">
                                  {item.name}
                                </p>
                                <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                  {item.kind}
                                </span>
                                <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] text-muted-foreground">
                                  {item.publisher}
                                </span>
                              </div>
                              <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                                {item.packagePath}
                              </p>
                            </div>
                            <span className="shrink-0 text-[11px] text-muted-foreground">
                              Review required
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {(communityCatalog.data?.errors ?? []).length ? (
                    <p className="text-[11px] text-amber-700 dark:text-amber-300">
                      Some official sources could not be refreshed. Gravitre did
                      not substitute unverified community sources.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </GravitreSurface>

          <GravitreSurface>
            <details>
              <summary className="cursor-pointer text-sm font-medium text-foreground">
                Build portable capabilities for Gravitre
              </summary>
              <p className="mt-2 text-xs text-muted-foreground">
                Use the same open package model Gravitre consumes: Agent Skills,
                MCP declarations, and Gravitre plugin manifests.
              </p>
              {developerKit.data ? (
                <div className="mt-3 grid gap-3 lg:grid-cols-3">
                  <div className="rounded border border-divide p-3">
                    <p className="text-xs font-medium text-foreground">
                      Manifest
                    </p>
                    <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                      {developerKit.data.manifestSchema} · v
                      {developerKit.data.schemaVersion}
                    </p>
                  </div>
                  <div className="rounded border border-divide p-3">
                    <p className="text-xs font-medium text-foreground">
                      Native activation
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {Object.entries(
                        developerKit.data.supportedPortableActivation,
                      )
                        .map(([key, value]) => `${key}: ${value}`)
                        .join(" · ")}
                    </p>
                  </div>
                  <div className="rounded border border-divide p-3">
                    <p className="text-xs font-medium text-foreground">
                      Distribution
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {Object.entries(developerKit.data.distribution)
                        .filter(([, enabled]) => enabled)
                        .map(([key]) => key)
                        .join(" · ")}
                    </p>
                  </div>
                </div>
              ) : null}
            </details>
          </GravitreSurface>

          {usage.data?.topCapabilities?.length ? (
            <GravitreSurface>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h2 className="text-sm font-medium text-foreground">
                    Capability usage · last 30 days
                  </h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Privacy-minimized adoption telemetry. Prompt and skill
                    contents are not stored.
                  </p>
                </div>
                <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                  {usage.data.topCapabilities.slice(0, 5).map((item) => (
                    <span
                      key={item.packageId}
                      className="rounded border border-divide px-2 py-1"
                    >
                      {item.name}: {item.events}
                    </span>
                  ))}
                </div>
              </div>
            </GravitreSurface>
          ) : null}

          <GravitreSurface>
            <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
              <div>
                <h2 className="text-sm font-medium text-foreground">
                  Import a skill or plugin ZIP
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Gravitre inspects the package before installation. Scripts
                  remain inert and cannot bypass approvals or verified
                  execution.
                </p>
                <div className="mt-3 max-w-xl">
                  <Label htmlFor="portable-capability-zip">Package ZIP</Label>
                  <Input
                    id="portable-capability-zip"
                    className="mt-1.5"
                    type="file"
                    accept=".zip,application/zip"
                    onChange={(event) => {
                      setZipFile(event.target.files?.[0] ?? null)
                      setZipInspection(null)
                    }}
                  />
                </div>
                <details className="mt-3 max-w-xl rounded border border-divide p-3">
                  <summary className="cursor-pointer text-xs font-medium text-foreground">
                    Signed package verification (optional)
                  </summary>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Provide both values to verify the ZIP at install time. A
                    valid signature proves package integrity; publisher trust is
                    evaluated separately.
                  </p>
                  <div className="mt-3 space-y-3">
                    <div>
                      <Label htmlFor="portable-capability-signing-key">
                        Publisher public key (PEM)
                      </Label>
                      <Textarea
                        id="portable-capability-signing-key"
                        className="mt-1.5 min-h-24 font-mono text-xs"
                        value={zipSigningPublicKey}
                        onChange={(event) =>
                          setZipSigningPublicKey(event.target.value)
                        }
                        placeholder="-----BEGIN PUBLIC KEY-----"
                      />
                    </div>
                    <div>
                      <Label htmlFor="portable-capability-signature">
                        Signature
                      </Label>
                      <Textarea
                        id="portable-capability-signature"
                        className="mt-1.5 min-h-20 font-mono text-xs"
                        value={zipSignature}
                        onChange={(event) =>
                          setZipSignature(event.target.value)
                        }
                        placeholder="Base64 signature"
                      />
                    </div>
                  </div>
                </details>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  disabled={!zipFile || zipBusy}
                  onClick={() => void inspectZip()}
                >
                  {zipBusy ? "Inspecting…" : "Inspect"}
                </Button>
                {isAdmin && zipInspection?.installationAllowed ? (
                  <Button
                    type="button"
                    disabled={!zipFile || zipBusy}
                    onClick={() => void installZip()}
                  >
                    {zipBusy ? "Installing…" : "Install"}
                  </Button>
                ) : null}
              </div>
            </div>
            {zipInspection ? (
              <div className="mt-4 rounded border border-divide p-3 text-xs text-muted-foreground">
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  <span>
                    Format:{" "}
                    {String(
                      zipInspection.inspection.format ?? "unknown",
                    ).replace(/_/g, " ")}
                  </span>
                  <span>
                    License:{" "}
                    {String(
                      zipInspection.inspection.license ?? "Review required",
                    )}
                  </span>
                  <span>
                    Risk:{" "}
                    {riskLabel(
                      String(zipInspection.inspection.risk ?? "unknown"),
                    )}
                  </span>
                  <span>
                    Security:{" "}
                    {riskLabel(
                      String(zipInspection.securityScan?.risk ?? "unknown"),
                    )}
                  </span>
                  <span>{zipInspection.resources.length} resources</span>
                </div>
                <p className="mt-2">
                  {zipInspection.installationAllowed
                    ? "Policy check passed. Installation still remains subject to Gravitre runtime permissions and verification."
                    : "Installation is blocked by the current license or security policy."}
                </p>
              </div>
            ) : null}
          </GravitreSurface>

          <section className="grid gap-6 lg:grid-cols-[1.45fr_0.85fr]">
            <GravitreSurface className="p-0">
              <div className="border-b border-divide px-4 py-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 className="text-sm font-medium text-foreground">
                      Installed portable capabilities
                    </h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Agent Skills, Claude/OpenAI-style plugins, MCP packages,
                      connectors, agents, plays, templates, and event triggers.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(
                      [
                        "all",
                        "skills",
                        "plugins",
                        "mcp",
                        "connectors",
                        "agents",
                        "plays",
                        "templates",
                        "triggers",
                      ] as CapabilityFilter[]
                    ).map((filter) => (
                      <Button
                        key={filter}
                        type="button"
                        size="sm"
                        variant={
                          capabilityFilter === filter ? "default" : "outline"
                        }
                        onClick={() => setCapabilityFilter(filter)}
                      >
                        {filter === "mcp"
                          ? "MCP"
                          : filter.charAt(0).toUpperCase() + filter.slice(1)}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
              {packages.error ? (
                <div className="p-4 text-sm text-destructive">
                  Could not load installed capabilities.
                </div>
              ) : packageRows.length === 0 ? (
                <div className="p-4">
                  <GravitreEmpty
                    icon={<Package className="h-5 w-5" />}
                    title="No portable capabilities installed"
                    hint="Inspect a package first, then install only what passes your organization policy."
                  />
                </div>
              ) : filteredPackageRows.length === 0 ? (
                <div className="p-4">
                  <GravitreEmpty
                    icon={<Package className="h-5 w-5" />}
                    title="No matching capabilities"
                    hint="Try another capability type filter."
                  />
                </div>
              ) : (
                <ul className="divide-y divide-divide">
                  {filteredPackageRows.map((item) => (
                    <li
                      key={item.id ?? `${item.name}:${item.version ?? ""}`}
                      className="flex min-w-0 flex-col gap-3 px-4 py-3 lg:flex-row lg:items-start lg:justify-between"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex min-w-0 flex-wrap items-center gap-2">
                          <p
                            className="min-w-0 truncate text-sm font-medium text-foreground"
                            title={item.name}
                          >
                            {item.name}
                          </p>
                          <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] text-muted-foreground">
                            {(item.package_format ?? "package").replace(
                              /_/g,
                              " ",
                            )}
                          </span>
                          {item.publisher_verified ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <CheckCircle2
                                className="h-3.5 w-3.5"
                                aria-hidden
                              />
                              Verified Marketplace publisher
                            </span>
                          ) : item.publisher_trusted ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <ShieldCheck
                                className="h-3.5 w-3.5"
                                aria-hidden
                              />
                              Org-trusted publisher
                            </span>
                          ) : item.signature_status === "verified" ? (
                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                              <ShieldCheck
                                className="h-3.5 w-3.5"
                                aria-hidden
                              />
                              Signed package
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {item.description || "No description provided."}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          License: {item.license ?? "Review required"} · Risk:{" "}
                          {riskLabel(item.risk_level)} · Status:{" "}
                          {item.status ?? "installed"}
                        </p>
                        {item.security_scan
                          ? (() => {
                              const summary = securitySummary(
                                item.security_scan,
                              )
                              return (
                                <p className="mt-1 text-[11px] text-muted-foreground">
                                  Security scan: {summary.important}{" "}
                                  high/critical findings · {summary.hosts}{" "}
                                  external hosts · {summary.scopes} scopes ·{" "}
                                  {summary.secrets} secret requirements
                                </p>
                              )
                            })()
                          : null}
                        {item.id && publishValidation[item.id] ? (
                          <div className="mt-2 rounded border border-divide p-2 text-[11px] text-muted-foreground">
                            <p className="font-medium text-foreground">
                              Marketplace preflight:{" "}
                              {publishValidation[item.id].readyForMarketplace
                                ? "ready"
                                : "changes required"}
                            </p>
                            <p className="mt-0.5">
                              {publishValidation[item.id].errorCount} errors ·{" "}
                              {publishValidation[item.id].warningCount} warnings
                              · no package code executed
                            </p>
                            {publishValidation[item.id].checks.some(
                              (check) => !check.passed,
                            ) ? (
                              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                                {publishValidation[item.id].checks
                                  .filter((check) => !check.passed)
                                  .map((check) => (
                                    <li key={check.key}>{check.message}</li>
                                  ))}
                              </ul>
                            ) : null}
                          </div>
                        ) : null}
                      </div>
                      <div className="flex min-w-0 flex-col gap-2 lg:max-w-[min(100%,20rem)] lg:shrink-0 lg:items-end">
                        {item.publisher_name ? (
                          <p className="max-w-full truncate text-[11px] text-muted-foreground">
                            {item.publisher_name}
                          </p>
                        ) : null}
                        {item.content_digest ? (
                          <p className="max-w-full truncate font-mono text-[11px] text-muted-foreground">
                            {item.content_digest}
                          </p>
                        ) : null}
                        {isAdmin && item.id ? (
                          <div className="flex flex-wrap justify-start gap-1 lg:justify-end">
                            {item.status !== "installed" ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={
                                  packageBusy === item.id ||
                                  item.license_policy === "block" ||
                                  item.risk_level === "blocked"
                                }
                                onClick={() =>
                                  setDecision({
                                    title: "Approve this capability?",
                                    description: `${item.name} will become available for native use. Existing license and risk checks still apply.`,
                                    actionLabel: "Approve capability",
                                    onConfirm: () =>
                                      reviewPackage(item.id!, "installed"),
                                  })
                                }
                              >
                                Approve
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={Boolean(packageBusy)}
                                onClick={() =>
                                  setDecision({
                                    title: "Quarantine this capability?",
                                    description: `${item.name} will be marked quarantined. Review linked agents and workflows before changing availability.`,
                                    actionLabel: "Quarantine capability",
                                    destructive: true,
                                    onConfirm: () =>
                                      reviewPackage(item.id!, "quarantined"),
                                  })
                                }
                              >
                                Quarantine
                              </Button>
                            )}
                            {item.status === "installed" ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={Boolean(packageBusy)}
                                onClick={() => void validatePackage(item.id!)}
                              >
                                Validate
                              </Button>
                            ) : null}
                            {item.status === "installed" &&
                            packageHasMcp(item.inspection) ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={Boolean(packageBusy)}
                                onClick={() => void prepareMcp(item.id!)}
                              >
                                Prepare MCP
                              </Button>
                            ) : null}
                            {item.status === "installed" &&
                            canPublishPackage(item) ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={
                                  packageBusy === item.id ||
                                  !publishValidation[item.id]
                                    ?.readyForMarketplace
                                }
                                title={
                                  publishValidation[item.id]
                                    ?.readyForMarketplace
                                    ? "Create a canonical Marketplace draft"
                                    : "Run Validate and resolve all blocking preflight checks first"
                                }
                                onClick={() =>
                                  void createMarketplaceDraft(item)
                                }
                              >
                                Publish draft
                              </Button>
                            ) : null}
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={Boolean(packageBusy)}
                              onClick={() =>
                                setHistoryPackageId(
                                  historyPackageId === item.id
                                    ? null
                                    : item.id!,
                                )
                              }
                            >
                              {historyPackageId === item.id
                                ? "Hide history"
                                : "History"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={Boolean(packageBusy)}
                              onClick={() =>
                                setDecision({
                                  title: "Disable this capability?",
                                  description: `${item.name} will be marked disabled. Review linked agents and workflows before changing availability.`,
                                  actionLabel: "Disable capability",
                                  destructive: true,
                                  onConfirm: () =>
                                    reviewPackage(item.id!, "disabled"),
                                })
                              }
                            >
                              Disable
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </GravitreSurface>

            <GravitreSurface>
              <div className="mb-4">
                <h2 className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <GitBranch className="h-4 w-4" aria-hidden />
                  Private Git marketplace
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Add an organization-owned GitHub capability catalog. New
                  packages remain approval-gated.
                </p>
              </div>
              <form className="space-y-3" onSubmit={addMarketplace}>
                <div className="space-y-1.5">
                  <Label htmlFor="capability-marketplace-name">Name</Label>
                  <Input
                    id="capability-marketplace-name"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Acme capability catalog"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="capability-marketplace-repo">
                    GitHub repository
                  </Label>
                  <Input
                    id="capability-marketplace-repo"
                    value={repositoryUrl}
                    onChange={(event) => setRepositoryUrl(event.target.value)}
                    placeholder="https://github.com/acme/gravitre-capabilities"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="capability-marketplace-branch">Branch</Label>
                  <Input
                    id="capability-marketplace-branch"
                    value={branch}
                    onChange={(event) => setBranch(event.target.value)}
                    placeholder="main"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="capability-marketplace-root">
                    Root path (optional)
                  </Label>
                  <Input
                    id="capability-marketplace-root"
                    value={marketplaceRootPath}
                    onChange={(event) =>
                      setMarketplaceRootPath(event.target.value)
                    }
                    placeholder="capabilities/"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Limit discovery to a folder in the repository.
                  </p>
                </div>
                <label className="flex cursor-pointer items-start gap-2 rounded border border-divide p-2.5">
                  <input
                    className="mt-0.5 h-4 w-4"
                    type="checkbox"
                    checked={marketplaceAutoSync}
                    onChange={(event) =>
                      setMarketplaceAutoSync(event.target.checked)
                    }
                  />
                  <span>
                    <span className="block text-xs font-medium text-foreground">
                      Auto-sync catalog
                    </span>
                    <span className="block text-[11px] text-muted-foreground">
                      Periodically discover changes. New packages are still
                      staged for review before installation.
                    </span>
                  </span>
                </label>
                <Button
                  type="submit"
                  disabled={busy || !name.trim() || !repositoryUrl.trim()}
                >
                  {busy ? "Adding…" : "Add marketplace"}
                </Button>
              </form>

              {marketplaceRows.length ? (
                <div className="mt-5 border-t border-divide pt-4">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">
                    Connected catalogs
                  </p>
                  <ul className="space-y-2">
                    {marketplaceRows.map((source) => (
                      <li
                        key={source.id ?? source.repository_url}
                        className="rounded border border-divide p-2.5"
                      >
                        <p className="text-sm font-medium text-foreground">
                          {source.name}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          {source.repository_url}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {source.branch || "main"} · approval{" "}
                          {source.approval_required === false
                            ? "optional"
                            : "required"}{" "}
                          · {source.status || "active"}
                        </p>
                        {source.last_sync_status ? (
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Last sync: {source.last_sync_status}
                          </p>
                        ) : null}
                        {isAdmin && source.id ? (
                          <Button
                            className="mt-2"
                            size="sm"
                            variant="outline"
                            disabled={sourceBusy === source.id}
                            onClick={() => void syncMarketplace(source.id!)}
                          >
                            {sourceBusy === source.id ? "Syncing…" : "Sync now"}
                          </Button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="mt-5 border-t border-divide pt-4">
                <h3 className="text-xs font-medium text-foreground">
                  Trusted publisher keys
                </h3>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Trust a publisher&apos;s public signing key for this
                  organization. Optionally link the key to an existing
                  Marketplace publisher slug so Gravitre can distinguish org
                  trust from platform verification.
                </p>
                {isAdmin ? (
                  <form
                    className="mt-3 space-y-2"
                    onSubmit={addTrustedPublisher}
                  >
                    <Input
                      value={trustedPublisherName}
                      onChange={(event) =>
                        setTrustedPublisherName(event.target.value)
                      }
                      placeholder="Publisher name"
                      aria-label="Publisher name"
                    />
                    <Textarea
                      value={trustedPublisherKey}
                      onChange={(event) =>
                        setTrustedPublisherKey(event.target.value)
                      }
                      placeholder="-----BEGIN PUBLIC KEY-----"
                      aria-label="Publisher public signing key"
                      rows={4}
                    />
                    <Input
                      value={trustedPublisherMarketplaceSlug}
                      onChange={(event) =>
                        setTrustedPublisherMarketplaceSlug(event.target.value)
                      }
                      placeholder="Marketplace publisher slug (optional)"
                      aria-label="Marketplace publisher slug"
                    />
                    <Button
                      type="submit"
                      size="sm"
                      variant="outline"
                      disabled={
                        trustBusy ||
                        !trustedPublisherName.trim() ||
                        !trustedPublisherKey.trim()
                      }
                    >
                      {trustBusy ? "Trusting…" : "Trust key"}
                    </Button>
                  </form>
                ) : null}
                {(trustedPublishers.data?.items ?? []).length ? (
                  <ul className="mt-3 space-y-2">
                    {(trustedPublishers.data?.items ?? []).map((publisher) => (
                      <li
                        key={publisher.id}
                        className="rounded border border-divide p-2"
                      >
                        <p className="text-xs font-medium text-foreground">
                          {publisher.publisher_name}
                        </p>
                        <p className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
                          {publisher.key_fingerprint}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </GravitreSurface>
          </section>

          <GravitreSurface>
            <div className="flex flex-col gap-1">
              <h2 className="text-sm font-medium text-foreground">
                Native component bindings
              </h2>
              <p className="text-xs text-muted-foreground">
                Bind declared package agents, plays, templates, and triggers to
                existing Gravitre entities. Bindings never create or execute
                targets.
              </p>
            </div>
            {bindablePackages.length === 0 ? (
              <div className="mt-4">
                <GravitreEmpty
                  icon={<Package className="h-5 w-5" />}
                  title="No native-bindable declarations"
                  hint="Installed packages with agent, play, template, or trigger declarations will appear here."
                />
              </div>
            ) : (
              <form
                className="mt-4 grid gap-3 lg:grid-cols-4"
                onSubmit={createNativeBinding}
              >
                <div className="space-y-1.5">
                  <Label htmlFor="native-binding-package">Package</Label>
                  <select
                    id="native-binding-package"
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={bindingPackageId ?? ""}
                    onChange={(event) => {
                      const value = event.target.value || null
                      setBindingPackageId(value)
                      setBindingComponentKey("")
                      setBindingTargetType("")
                      setBindingTargetId("")
                    }}
                  >
                    <option value="">Select package</option>
                    {bindablePackages.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="native-binding-component">Component</Label>
                  <select
                    id="native-binding-component"
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={bindingComponentKey}
                    disabled={!bindingPackageId}
                    onChange={(event) => {
                      const value = event.target.value
                      setBindingComponentKey(value)
                      const selected = bindingComponents.find(
                        (row) => `${row.kind}:${row.name}` === value,
                      )
                      setBindingTargetType(
                        selected
                          ? targetTypesForComponent(selected.kind)[0]
                          : "",
                      )
                    }}
                  >
                    <option value="">Select declaration</option>
                    {bindingComponents.map((row) => (
                      <option
                        key={`${row.kind}:${row.name}`}
                        value={`${row.kind}:${row.name}`}
                      >
                        {row.kind} · {row.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="native-binding-target-type">
                    Target type
                  </Label>
                  <select
                    id="native-binding-target-type"
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={bindingTargetType}
                    disabled={!selectedBindingComponent}
                    onChange={(event) =>
                      setBindingTargetType(event.target.value)
                    }
                  >
                    <option value="">Select target</option>
                    {bindingTargetTypes.map((target) => (
                      <option key={target} value={target}>
                        {target.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="native-binding-target-id">
                    Existing target ID / key
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      id="native-binding-target-id"
                      value={bindingTargetId}
                      onChange={(event) =>
                        setBindingTargetId(event.target.value)
                      }
                      placeholder="Existing Gravitre ID or Play key"
                      disabled={!bindingTargetType}
                    />
                    {isAdmin ? (
                      <Button
                        type="submit"
                        disabled={
                          bindingBusy ||
                          !bindingPackageId ||
                          !selectedBindingComponent ||
                          !bindingTargetType ||
                          !bindingTargetId.trim()
                        }
                      >
                        Bind
                      </Button>
                    ) : null}
                  </div>
                </div>
              </form>
            )}
            {bindingPackageId && (nativeBindings.data?.items ?? []).length ? (
              <div className="mt-4 border-t border-divide pt-3">
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  Current bindings
                </p>
                <ul className="space-y-2">
                  {(nativeBindings.data?.items ?? []).map((binding) => (
                    <li
                      key={binding.id}
                      className="flex flex-col gap-2 rounded border border-divide p-2.5 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="text-xs">
                        <p className="font-medium text-foreground">
                          {binding.component_kind} · {binding.component_name}
                        </p>
                        <p className="mt-0.5 text-muted-foreground">
                          {binding.target_type.replace(/_/g, " ")} ·{" "}
                          {binding.target_id} ·{" "}
                          {binding.enabled ? "active" : "disabled"}
                        </p>
                      </div>
                      {isAdmin ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={bindingBusy}
                          onClick={() =>
                            setDecision({
                              title: "Remove this native binding?",
                              description: `Remove binding ${binding.id} from this package. The target entity is retained.`,
                              actionLabel: "Remove binding",
                              destructive: true,
                              onConfirm: () => deleteNativeBinding(binding.id),
                            })
                          }
                        >
                          Remove
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </GravitreSurface>

          {historyPackageId ? (
            <GravitreSurface className="p-0">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-divide px-4 py-3">
                <div>
                  <h2 className="text-sm font-medium text-foreground">
                    Capability version history
                  </h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Immutable package snapshots. Rollback restores the selected
                    package content and inert resources.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setHistoryPackageId(null)}
                >
                  Close
                </Button>
              </div>
              {packageVersions.error ? (
                <div className="p-4 text-sm text-destructive">
                  Could not load capability versions.
                </div>
              ) : (packageVersions.data?.items ?? []).length === 0 ? (
                <div className="p-4">
                  <GravitreEmpty
                    icon={<Package className="h-5 w-5" />}
                    title="No version snapshots yet"
                    hint="A snapshot is recorded when this capability is installed or updated."
                  />
                </div>
              ) : (
                <ul className="divide-y divide-divide">
                  {(packageVersions.data?.items ?? []).map((version) => (
                    <li
                      key={version.id}
                      className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground">
                          {version.package_version || "Unversioned package"}
                        </p>
                        <p className="mt-0.5 max-w-2xl truncate font-mono text-[11px] text-muted-foreground">
                          {version.content_digest ||
                            "No content digest recorded"}
                        </p>
                        {version.recorded_at ? (
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Recorded{" "}
                            {new Date(version.recorded_at).toLocaleString()}
                          </p>
                        ) : null}
                      </div>
                      {isAdmin ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={historyBusy === version.id}
                          onClick={() =>
                            setDecision({
                              title: "Restore this package version?",
                              description: `Restore version ${version.id}. The returned review policy determines whether it can be used immediately.`,
                              actionLabel: "Restore version",
                              onConfirm: () =>
                                rollbackVersion(historyPackageId, version.id),
                            })
                          }
                        >
                          {historyBusy === version.id
                            ? "Restoring…"
                            : "Rollback"}
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </GravitreSurface>
          ) : null}

          {isAdmin ? (
            <GravitreSurface className="p-0">
              <div className="border-b border-divide px-4 py-3">
                <h2 className="text-sm font-medium text-foreground">
                  Portable MCP review
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Capability-declared MCP servers are prepared disabled.
                  Discover tools first, then explicitly enable the server and
                  only the tools you approve.
                </p>
              </div>
              {portableMcpServers.length === 0 ? (
                <div className="p-4">
                  <GravitreEmpty
                    icon={<ShieldCheck className="h-5 w-5" />}
                    title="No prepared MCP dependencies"
                    hint="Use Prepare MCP on an installed capability that declares remote MCP servers."
                  />
                </div>
              ) : (
                <ul className="divide-y divide-divide">
                  {portableMcpServers.map((server) => {
                    const serverTools = portableMcpTools.filter(
                      (tool) => tool.server_id === server.id,
                    )
                    return (
                      <li key={server.id} className="space-y-3 px-4 py-3">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <p
                              className="truncate text-sm font-medium text-foreground"
                              title={server.server_name}
                            >
                              {server.server_name}
                            </p>
                            <p className="mt-1 truncate text-xs text-muted-foreground">
                              {server.server_url}
                            </p>
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              {server.transport} ·{" "}
                              {server.activation_state ?? "pending review"} ·{" "}
                              {server.enabled
                                ? "server enabled"
                                : "server disabled"}
                            </p>
                            {server.auth_type !== "none" ? (
                              <div className="mt-2 grid max-w-xl gap-2 sm:grid-cols-[1fr_auto_auto]">
                                <Input
                                  type="password"
                                  autoComplete="off"
                                  value={
                                    mcpCredentialInputs[server.id]?.secret ?? ""
                                  }
                                  onChange={(event) =>
                                    setMcpCredentialInputs((current) => ({
                                      ...current,
                                      [server.id]: {
                                        secret: event.target.value,
                                        header:
                                          current[server.id]?.header ??
                                          "X-API-Key",
                                      },
                                    }))
                                  }
                                  placeholder={
                                    server.auth_type === "bearer"
                                      ? "Bearer token"
                                      : "API key"
                                  }
                                  aria-label={
                                    server.auth_type === "bearer"
                                      ? "MCP bearer token"
                                      : "MCP API key"
                                  }
                                />
                                {server.auth_type === "api_key" ? (
                                  <Input
                                    value={
                                      mcpCredentialInputs[server.id]?.header ??
                                      "X-API-Key"
                                    }
                                    onChange={(event) =>
                                      setMcpCredentialInputs((current) => ({
                                        ...current,
                                        [server.id]: {
                                          secret:
                                            current[server.id]?.secret ?? "",
                                          header: event.target.value,
                                        },
                                      }))
                                    }
                                    placeholder="Header"
                                    aria-label="MCP API key header"
                                  />
                                ) : null}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={
                                    mcpBusy === server.id ||
                                    !(
                                      mcpCredentialInputs[server.id]?.secret ??
                                      ""
                                    ).trim()
                                  }
                                  onClick={() =>
                                    void saveMcpCredentials(server)
                                  }
                                >
                                  Save credentials
                                </Button>
                              </div>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 flex-wrap gap-1.5">
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={Boolean(mcpBusy)}
                              onClick={() => void discoverMcp(server.id)}
                            >
                              {mcpBusy === server.id
                                ? "Checking…"
                                : "Discover tools"}
                            </Button>
                            <Button
                              size="sm"
                              variant={server.enabled ? "ghost" : "outline"}
                              disabled={
                                mcpBusy === server.id ||
                                (!server.enabled && serverTools.length === 0)
                              }
                              onClick={() =>
                                setDecision({
                                  title: server.enabled
                                    ? "Disable this MCP server?"
                                    : "Approve this MCP server?",
                                  description:
                                    "This changes server availability. Tool enablement and write approval policies remain separate controls.",
                                  actionLabel: server.enabled
                                    ? "Disable server"
                                    : "Approve server",
                                  destructive: server.enabled,
                                  onConfirm: () =>
                                    setMcpServerEnabled(
                                      server.id,
                                      !server.enabled,
                                    ),
                                })
                              }
                            >
                              {server.enabled
                                ? "Disable server"
                                : "Approve server"}
                            </Button>
                          </div>
                        </div>
                        {serverTools.length ? (
                          <div className="rounded border border-divide">
                            <ul className="divide-y divide-divide">
                              {serverTools.map((tool) => (
                                <li
                                  key={tool.id}
                                  className="flex min-w-0 flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
                                >
                                  <div className="min-w-0">
                                    <p
                                      className="truncate text-xs font-medium text-foreground"
                                      title={tool.tool_name}
                                    >
                                      {tool.tool_name}
                                    </p>
                                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                                      {tool.capability_tier} ·{" "}
                                      {tool.requires_approval === true
                                        ? "approval required"
                                        : tool.requires_approval === false
                                          ? "no write approval required"
                                          : "approval policy not reported"}{" "}
                                      · {tool.risk_level ?? "unrated"} risk
                                    </p>
                                  </div>
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    disabled={
                                      mcpBusy === tool.id ||
                                      (!server.enabled && !tool.enabled)
                                    }
                                    onClick={() =>
                                      setDecision({
                                        title: tool.enabled
                                          ? "Disable this tool?"
                                          : "Enable this tool?",
                                        description: `${tool.tool_name} will be ${tool.enabled ? "disabled" : "enabled"}. Server availability and backend approval policy also govern execution.`,
                                        actionLabel: tool.enabled
                                          ? "Disable tool"
                                          : "Enable tool",
                                        destructive: tool.enabled,
                                        onConfirm: () =>
                                          setMcpToolEnabled(
                                            tool.id,
                                            !tool.enabled,
                                          ),
                                      })
                                    }
                                  >
                                    {tool.enabled ? "Disable" : "Enable"}
                                  </Button>
                                </li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                      </li>
                    )
                  })}
                </ul>
              )}
            </GravitreSurface>
          ) : null}

          <GravitreSurface className="p-0">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-divide px-4 py-3">
              <div>
                <h2 className="text-sm font-medium text-foreground">
                  Marketplace review queue
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Repository sync only discovers packages. Review is required
                  before installation.
                </p>
              </div>
              <span className="text-xs text-muted-foreground">
                {pendingCandidates.length} pending
              </span>
            </div>
            {candidateRows.length === 0 ? (
              <div className="p-4">
                <GravitreEmpty
                  icon={<ShieldCheck className="h-5 w-5" />}
                  title="No capability candidates"
                  hint="Sync a Git marketplace to discover skills and plugins for review."
                />
              </div>
            ) : (
              <ul className="divide-y divide-divide">
                {candidateRows.map((candidate) => (
                  <li
                    key={candidate.id}
                    className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-start sm:justify-between"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-foreground">
                          {candidate.name}
                        </p>
                        <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {candidate.package_format.replace(/_/g, " ")}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {candidate.status.replace(/_/g, " ")}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {candidate.description || candidate.package_path}
                      </p>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        License: {candidate.license ?? "Review required"} ·
                        Risk: {riskLabel(candidate.risk_level)}
                      </p>
                      {candidate.security_scan
                        ? (() => {
                            const summary = securitySummary(
                              candidate.security_scan,
                            )
                            return (
                              <p className="mt-1 text-[11px] text-muted-foreground">
                                Security scan: {summary.important} high/critical
                                findings · {summary.hosts} external hosts ·{" "}
                                {summary.scopes} scopes · {summary.secrets}{" "}
                                secret requirements
                              </p>
                            )
                          })()
                        : null}
                    </div>
                    {isAdmin ? (
                      <div className="flex shrink-0 flex-wrap gap-1.5">
                        {candidate.status === "pending_review" ? (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={
                                packageBusy === candidate.id ||
                                candidate.license_policy === "block" ||
                                candidate.risk_level === "blocked"
                              }
                              onClick={() =>
                                void decideCandidate(candidate.id, "approve")
                              }
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={packageBusy === candidate.id}
                              onClick={() =>
                                void decideCandidate(candidate.id, "reject")
                              }
                            >
                              Reject
                            </Button>
                          </>
                        ) : null}
                        {candidate.status === "approved" ? (
                          <Button
                            size="sm"
                            disabled={packageBusy === candidate.id}
                            onClick={() =>
                              setDecision({
                                title: "Install this capability candidate?",
                                description:
                                  "Create a package from this reviewed candidate. Package status, binding and MCP enablement are separate steps.",
                                actionLabel: "Install candidate",
                                onConfirm: () => installCandidate(candidate.id),
                              })
                            }
                          >
                            {packageBusy === candidate.id
                              ? "Installing…"
                              : "Install"}
                          </Button>
                        ) : null}
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </GravitreSurface>
        </div>
      </div>
      {decision ? (
        <WorkDecisionDialog {...decision} onCancel={() => setDecision(null)} />
      ) : null}
    </AppShell>
  )
}
