"use client"

import { useState } from "react"
import type { FormEvent } from "react"
import { useRouter } from "next/navigation"
import useSWR from "swr"
import { ShieldCheck, Package, GitBranch, AlertTriangle, CheckCircle2 } from "lucide-react"
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
import { portableCapabilitiesApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { toast } from "sonner"

function riskLabel(value?: string) {
  if (!value) return "Unknown"
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function packageHasMcp(inspection?: Record<string, unknown>) {
  const components = inspection?.components
  return Array.isArray(components) && components.some((component) => {
    if (!component || typeof component !== "object") return false
    return (component as Record<string, unknown>).kind === "mcp"
  })
}

function canPublishPackage(item: {
  source_uri?: string | null
  source_commit_sha?: string | null
  content_digest?: string | null
  signature_status?: string
  publisher_trusted?: boolean
  publisher_verified?: boolean
}) {
  const gitPinned = Boolean(item.source_uri && item.source_commit_sha && item.content_digest)
  const trustedSigned = Boolean(
    item.content_digest &&
    item.signature_status === "verified" &&
    (item.publisher_trusted || item.publisher_verified),
  )
  return gitPinned || trustedSigned
}

type CapabilityFilter = "all" | "skills" | "plugins" | "mcp" | "agents" | "plays" | "templates"

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
    ? item.inspection?.components as Array<Record<string, unknown>>
    : []
  const kinds = new Set(components.map((row) => String(row.kind ?? "").toLowerCase()))
  if (filter === "skills") return format === "agent_skill" || kinds.has("skill")
  if (filter === "plugins") return format.includes("plugin") || format === "gravitre"
  if (filter === "mcp") return format === "mcp" || kinds.has("mcp")
  if (filter === "agents") return kinds.has("agent")
  if (filter === "plays") return kinds.has("play")
  if (filter === "templates") return kinds.has("template")
  return true
}

function securitySummary(scan?: {
  findings?: Array<{ severity?: string }>
  externalHosts?: string[]
  oauthScopes?: string[]
  requiredSecrets?: string[]
}) {
  const findings = scan?.findings ?? []
  const important = findings.filter((row) => row.severity === "critical" || row.severity === "high").length
  return {
    important,
    hosts: scan?.externalHosts?.length ?? 0,
    scopes: scan?.oauthScopes?.length ?? 0,
    secrets: scan?.requiredSecrets?.length ?? 0,
  }
}

export default function CapabilityMarketplacePage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const router = useRouter()
  const [name, setName] = useState("")
  const [repositoryUrl, setRepositoryUrl] = useState("")
  const [branch, setBranch] = useState("main")
  const [busy, setBusy] = useState(false)
  const [packageBusy, setPackageBusy] = useState<string | null>(null)
  const [sourceBusy, setSourceBusy] = useState<string | null>(null)
  const [historyPackageId, setHistoryPackageId] = useState<string | null>(null)
  const [historyBusy, setHistoryBusy] = useState<string | null>(null)
  const [trustedPublisherName, setTrustedPublisherName] = useState("")
  const [trustedPublisherKey, setTrustedPublisherKey] = useState("")
  const [trustedPublisherMarketplaceSlug, setTrustedPublisherMarketplaceSlug] = useState("")
  const [trustBusy, setTrustBusy] = useState(false)
  const [zipFile, setZipFile] = useState<File | null>(null)
  const [zipBusy, setZipBusy] = useState(false)
  const [zipInspection, setZipInspection] = useState<Awaited<ReturnType<typeof portableCapabilitiesApi.inspectZip>> | null>(null)
  const [capabilityFilter, setCapabilityFilter] = useState<CapabilityFilter>("all")

  const packages = useSWR(
    user ? "portable-capability-packages" : null,
    () => portableCapabilitiesApi.listPackages(),
  )
  const marketplaces = useSWR(
    user ? "portable-capability-marketplaces" : null,
    () => portableCapabilitiesApi.listMarketplaces(),
  )
  const trustedPublishers = useSWR(
    user ? "portable-capability-trusted-publishers" : null,
    () => portableCapabilitiesApi.listTrustedPublishers(),
  )
  const candidates = useSWR(
    user ? "portable-capability-marketplace-candidates" : null,
    () => portableCapabilitiesApi.listCandidates(),
  )
  const packageVersions = useSWR(
    user && historyPackageId ? ["portable-capability-versions", historyPackageId] : null,
    () => portableCapabilitiesApi.listVersions(historyPackageId!),
  )

  const packageRows = packages.data?.items ?? []
  const filteredPackageRows = packageRows.filter((item) => packageMatchesFilter(item, capabilityFilter))
  const marketplaceRows = marketplaces.data?.items ?? []
  const candidateRows = candidates.data?.items ?? []
  const pendingCandidates = candidateRows.filter((row) => row.status === "pending_review")
  const quarantined = packageRows.filter((row) => row.status === "quarantined").length
  const signed = packageRows.filter((row) => row.signature_status === "verified").length

  async function inspectZip() {
    if (!zipFile) return
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
      toast.error(error instanceof Error ? error.message : "ZIP inspection failed")
    } finally {
      setZipBusy(false)
    }
  }

  async function installZip() {
    if (!zipFile || !zipInspection?.installationAllowed || !isAdmin) return
    setZipBusy(true)
    try {
      await portableCapabilitiesApi.installZip(zipFile)
      toast.success("Portable capability installed")
      setZipFile(null)
      setZipInspection(null)
      await packages.mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "ZIP install failed")
    } finally {
      setZipBusy(false)
    }
  }

  async function addTrustedPublisher(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trustedPublisherName.trim() || !trustedPublisherKey.trim()) return
    setTrustBusy(true)
    try {
      await portableCapabilitiesApi.addTrustedPublisher({
        publisherName: trustedPublisherName.trim(),
        publicKeyPem: trustedPublisherKey.trim(),
        marketplacePublisherSlug: trustedPublisherMarketplaceSlug.trim() || undefined,
      })
      toast.success("Publisher signing key trusted")
      setTrustedPublisherName("")
      setTrustedPublisherKey("")
      setTrustedPublisherMarketplaceSlug("")
      await trustedPublishers.mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not trust publisher key")
    } finally {
      setTrustBusy(false)
    }
  }

  async function addMarketplace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || !repositoryUrl.trim()) return
    setBusy(true)
    try {
      await portableCapabilitiesApi.addMarketplace({
        name: name.trim(),
        repositoryUrl: repositoryUrl.trim(),
        branch: branch.trim() || "main",
        approvalRequired: true,
      })
      toast.success("Private capability marketplace added")
      setName("")
      setRepositoryUrl("")
      setBranch("main")
      await marketplaces.mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not add marketplace")
    } finally {
      setBusy(false)
    }
  }


  async function reviewPackage(packageId: string, status: "installed" | "quarantined" | "disabled") {
    setPackageBusy(packageId)
    try {
      await portableCapabilitiesApi.reviewPackage(packageId, { status })
      toast.success(status === "installed" ? "Capability approved" : status === "disabled" ? "Capability disabled" : "Capability quarantined")
      await packages.mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Capability review failed")
    } finally {
      setPackageBusy(null)
    }
  }

  async function prepareMcp(packageId: string) {
    setPackageBusy(packageId)
    try {
      const result = await portableCapabilitiesApi.prepareMcp(packageId)
      toast.success("MCP dependencies prepared", {
        description: `${result.prepared.length} server${result.prepared.length === 1 ? "" : "s"} pending review${result.blocked.length ? `; ${result.blocked.length} blocked by policy` : ""}`,
      })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "MCP preparation failed")
    } finally {
      setPackageBusy(null)
    }
  }

  async function syncMarketplace(sourceId: string) {
    setSourceBusy(sourceId)
    try {
      const result = await portableCapabilitiesApi.syncMarketplace(sourceId)
      toast.success("Capability marketplace synced", {
        description: `${result.sync.ingested} package${result.sync.ingested === 1 ? "" : "s"} staged for review`,
      })
      await Promise.all([marketplaces.mutate(), packages.mutate(), candidates.mutate()])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Marketplace sync failed")
    } finally {
      setSourceBusy(null)
    }
  }

  async function decideCandidate(candidateId: string, decision: "approve" | "reject") {
    setPackageBusy(candidateId)
    try {
      await portableCapabilitiesApi.reviewCandidate(candidateId, { decision })
      toast.success(decision === "approve" ? "Capability candidate approved" : "Capability candidate rejected")
      await candidates.mutate()
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Candidate review failed")
    } finally {
      setPackageBusy(null)
    }
  }

  async function installCandidate(candidateId: string) {
    setPackageBusy(candidateId)
    try {
      await portableCapabilitiesApi.installCandidate(candidateId)
      toast.success("Capability installed")
      await Promise.all([candidates.mutate(), packages.mutate()])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Capability install failed")
    } finally {
      setPackageBusy(null)
    }
  }

  async function rollbackVersion(packageId: string, versionId: string) {
    setHistoryBusy(versionId)
    try {
      const result = await portableCapabilitiesApi.rollbackVersion(packageId, versionId)
      toast.success("Capability version restored", {
        description: result.requiresReview
          ? "The restored package is quarantined and requires review before use."
          : "The restored package is active.",
      })
      await Promise.all([packages.mutate(), packageVersions.mutate()])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Capability rollback failed")
    } finally {
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
      const result = await portableCapabilitiesApi.createMarketplaceDraft(item.id, {
        slug,
        title: item.name,
        description: item.description || undefined,
      })
      toast.success("Marketplace draft created", {
        description: "Review the listing, then submit it through Gravitre's existing publisher review flow.",
      })
      router.push(`/marketplace/assets/${encodeURIComponent(result.asset.slug)}`)
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create Marketplace draft")
    } finally {
      setPackageBusy(null)
    }
  }


  return (
    <AppShell title="Capabilities">
      <div className="bg-[color:var(--g-canvas)]">
        <GravitrePageHeader
          eyebrow="Gravitre Marketplace"
          title="Capabilities"
          description="Install and govern portable skills, plugins, and MCP capability packages while Gravitre retains execution, approval, and verification control."
          icon={<Package className="h-5 w-5" />}
        />

        <div className="mx-auto w-full max-w-6xl space-y-6 px-[var(--np-page-pad-sm)] py-4 sm:px-[var(--np-page-pad)] sm:py-5">
          <section className="grid gap-[var(--np-kpi-gap)] sm:grid-cols-3">
            <GravitreMetric label="Installed capabilities" value={packageRows.length} icon={<Package className="h-4 w-4" />} />
            <GravitreMetric label="Signed packages" value={signed} icon={<ShieldCheck className="h-4 w-4" />} />
            <GravitreMetric label="Quarantined" value={quarantined} icon={<AlertTriangle className="h-4 w-4" />} />
          </section>

          <GravitreSurface>
            <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
              <div>
                <h2 className="text-sm font-medium text-foreground">Import a skill or plugin ZIP</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Gravitre inspects the package before installation. Scripts remain inert and cannot bypass approvals or verified execution.
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
                    Format: {String(zipInspection.inspection.format ?? "unknown").replace(/_/g, " ")}
                  </span>
                  <span>License: {String(zipInspection.inspection.license ?? "Review required")}</span>
                  <span>Risk: {riskLabel(String(zipInspection.inspection.risk ?? "unknown"))}</span>
                  <span>Security: {riskLabel(String(zipInspection.securityScan?.risk ?? "unknown"))}</span>
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
                    <h2 className="text-sm font-medium text-foreground">Installed portable capabilities</h2>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Agent Skills, Claude/OpenAI-style plugins, MCP packages, agents, plays, and templates.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(["all", "skills", "plugins", "mcp", "agents", "plays", "templates"] as CapabilityFilter[]).map((filter) => (
                      <Button
                        key={filter}
                        type="button"
                        size="sm"
                        variant={capabilityFilter === filter ? "default" : "outline"}
                        onClick={() => setCapabilityFilter(filter)}
                      >
                        {filter === "mcp" ? "MCP" : filter.charAt(0).toUpperCase() + filter.slice(1)}
                      </Button>
                    ))}
                  </div>
                </div>
              </div>
              {packages.error ? (
                <div className="p-4 text-sm text-destructive">Could not load installed capabilities.</div>
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
                    <li key={item.id ?? `${item.name}:${item.version ?? ""}`} className="flex items-start justify-between gap-4 px-4 py-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-foreground">{item.name}</p>
                          <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] text-muted-foreground">
                            {(item.package_format ?? "package").replace(/_/g, " ")}
                          </span>
                          {item.publisher_verified ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                              Verified Marketplace publisher
                            </span>
                          ) : item.publisher_trusted ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                              Org-trusted publisher
                            </span>
                          ) : item.signature_status === "verified" ? (
                            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                              <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
                              Signed package
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {item.description || "No description provided."}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          License: {item.license ?? "Review required"} · Risk: {riskLabel(item.risk_level)} · Status: {item.status ?? "installed"}
                        </p>
                        {item.security_scan ? (() => {
                          const summary = securitySummary(item.security_scan)
                          return (
                            <p className="mt-1 text-[11px] text-muted-foreground">
                              Security scan: {summary.important} high/critical findings · {summary.hosts} external hosts · {summary.scopes} scopes · {summary.secrets} secret requirements
                            </p>
                          )
                        })() : null}
                      </div>
                      <div className="shrink-0 space-y-2 text-right text-[11px] text-muted-foreground">
                        {item.publisher_name ? <p>{item.publisher_name}</p> : null}
                        {item.content_digest ? <p className="max-w-[150px] truncate font-mono">{item.content_digest}</p> : null}
                        {isAdmin && item.id ? (
                          <div className="flex justify-end gap-1">
                            {item.status !== "installed" ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={packageBusy === item.id || item.license_policy === "block" || item.risk_level === "blocked"}
                                onClick={() => void reviewPackage(item.id!, "installed")}
                              >
                                Approve
                              </Button>
                            ) : (
                              <Button
                                size="sm"
                                variant="ghost"
                                disabled={packageBusy === item.id}
                                onClick={() => void reviewPackage(item.id!, "quarantined")}
                              >
                                Quarantine
                              </Button>
                            )}
                            {item.status === "installed" && packageHasMcp(item.inspection) ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={packageBusy === item.id}
                                onClick={() => void prepareMcp(item.id!)}
                              >
                                Prepare MCP
                              </Button>
                            ) : null}
                            {item.status === "installed" && canPublishPackage(item) ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={packageBusy === item.id}
                                onClick={() => void createMarketplaceDraft(item)}
                              >
                                Publish draft
                              </Button>
                            ) : null}
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={packageBusy === item.id}
                              onClick={() => setHistoryPackageId(historyPackageId === item.id ? null : item.id!)}
                            >
                              {historyPackageId === item.id ? "Hide history" : "History"}
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={packageBusy === item.id}
                              onClick={() => void reviewPackage(item.id!, "disabled")}
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
                  Add an organization-owned GitHub capability catalog. New packages remain approval-gated.
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
                  <Label htmlFor="capability-marketplace-repo">GitHub repository</Label>
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
                <Button type="submit" disabled={busy || !name.trim() || !repositoryUrl.trim()}>
                  {busy ? "Adding…" : "Add marketplace"}
                </Button>
              </form>

              {marketplaceRows.length ? (
                <div className="mt-5 border-t border-divide pt-4">
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Connected catalogs</p>
                  <ul className="space-y-2">
                    {marketplaceRows.map((source) => (
                      <li key={source.id ?? source.repository_url} className="rounded border border-divide p-2.5">
                        <p className="text-sm font-medium text-foreground">{source.name}</p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">{source.repository_url}</p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          {source.branch || "main"} · approval {source.approval_required === false ? "optional" : "required"} · {source.status || "active"}
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
                <h3 className="text-xs font-medium text-foreground">Trusted publisher keys</h3>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Trust a publisher&apos;s public signing key for this organization. Optionally link the key to an existing Marketplace publisher slug so Gravitre can distinguish org trust from platform verification.
                </p>
                {isAdmin ? (
                  <form className="mt-3 space-y-2" onSubmit={addTrustedPublisher}>
                    <Input
                      value={trustedPublisherName}
                      onChange={(event) => setTrustedPublisherName(event.target.value)}
                      placeholder="Publisher name"
                      aria-label="Publisher name"
                    />
                    <Textarea
                      value={trustedPublisherKey}
                      onChange={(event) => setTrustedPublisherKey(event.target.value)}
                      placeholder="-----BEGIN PUBLIC KEY-----"
                      aria-label="Publisher public signing key"
                      rows={4}
                    />
                    <Input
                      value={trustedPublisherMarketplaceSlug}
                      onChange={(event) => setTrustedPublisherMarketplaceSlug(event.target.value)}
                      placeholder="Marketplace publisher slug (optional)"
                      aria-label="Marketplace publisher slug"
                    />
                    <Button
                      type="submit"
                      size="sm"
                      variant="outline"
                      disabled={trustBusy || !trustedPublisherName.trim() || !trustedPublisherKey.trim()}
                    >
                      {trustBusy ? "Trusting…" : "Trust key"}
                    </Button>
                  </form>
                ) : null}
                {(trustedPublishers.data?.items ?? []).length ? (
                  <ul className="mt-3 space-y-2">
                    {(trustedPublishers.data?.items ?? []).map((publisher) => (
                      <li key={publisher.id} className="rounded border border-divide p-2">
                        <p className="text-xs font-medium text-foreground">{publisher.publisher_name}</p>
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

          {historyPackageId ? (
            <GravitreSurface className="p-0">
              <div className="flex items-start justify-between gap-4 border-b border-divide px-4 py-3">
                <div>
                  <h2 className="text-sm font-medium text-foreground">Capability version history</h2>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Immutable package snapshots. Rollback restores the selected package content and inert resources.
                  </p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setHistoryPackageId(null)}>
                  Close
                </Button>
              </div>
              {packageVersions.error ? (
                <div className="p-4 text-sm text-destructive">Could not load capability versions.</div>
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
                    <li key={version.id} className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground">
                          {version.package_version || "Unversioned package"}
                        </p>
                        <p className="mt-0.5 max-w-2xl truncate font-mono text-[11px] text-muted-foreground">
                          {version.content_digest || "No content digest recorded"}
                        </p>
                        {version.recorded_at ? (
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Recorded {new Date(version.recorded_at).toLocaleString()}
                          </p>
                        ) : null}
                      </div>
                      {isAdmin ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={historyBusy === version.id}
                          onClick={() => void rollbackVersion(historyPackageId, version.id)}
                        >
                          {historyBusy === version.id ? "Restoring…" : "Rollback"}
                        </Button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </GravitreSurface>
          ) : null}

          <GravitreSurface className="p-0">
            <div className="flex items-start justify-between gap-4 border-b border-divide px-4 py-3">
              <div>
                <h2 className="text-sm font-medium text-foreground">Marketplace review queue</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Repository sync only discovers packages. Review is required before installation.
                </p>
              </div>
              <span className="text-xs text-muted-foreground">{pendingCandidates.length} pending</span>
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
                  <li key={candidate.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-foreground">{candidate.name}</p>
                        <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          {candidate.package_format.replace(/_/g, " ")}
                        </span>
                        <span className="text-xs text-muted-foreground">{candidate.status.replace(/_/g, " ")}</span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {candidate.description || candidate.package_path}
                      </p>
                      <p className="mt-1 text-[11px] text-muted-foreground">
                        License: {candidate.license ?? "Review required"} · Risk: {riskLabel(candidate.risk_level)}
                      </p>
                      {candidate.security_scan ? (() => {
                        const summary = securitySummary(candidate.security_scan)
                        return (
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Security scan: {summary.important} high/critical findings · {summary.hosts} external hosts · {summary.scopes} scopes · {summary.secrets} secret requirements
                          </p>
                        )
                      })() : null}
                    </div>
                    {isAdmin ? (
                      <div className="flex shrink-0 flex-wrap gap-1.5">
                        {candidate.status === "pending_review" ? (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={packageBusy === candidate.id || candidate.license_policy === "block" || candidate.risk_level === "blocked"}
                              onClick={() => void decideCandidate(candidate.id, "approve")}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={packageBusy === candidate.id}
                              onClick={() => void decideCandidate(candidate.id, "reject")}
                            >
                              Reject
                            </Button>
                          </>
                        ) : null}
                        {candidate.status === "approved" ? (
                          <Button
                            size="sm"
                            disabled={packageBusy === candidate.id}
                            onClick={() => void installCandidate(candidate.id)}
                          >
                            {packageBusy === candidate.id ? "Installing…" : "Install"}
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
    </AppShell>
  )
}
