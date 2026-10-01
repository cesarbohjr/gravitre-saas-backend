"use client"

import { useState } from "react"
import type { FormEvent } from "react"
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
import { portableCapabilitiesApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { toast } from "sonner"

function riskLabel(value?: string) {
  if (!value) return "Unknown"
  return value.charAt(0).toUpperCase() + value.slice(1)
}

function hasMcpDependency(inspection?: Record<string, unknown>) {
  const components = inspection?.components
  return Array.isArray(components) && components.some(
    (component) => component && typeof component === "object" && (component as { kind?: unknown }).kind === "mcp",
  )
}

export default function CapabilityMarketplacePage() {
  const { user } = useAuth()
  const { isAdmin } = useOrgAdmin()
  const [name, setName] = useState("")
  const [repositoryUrl, setRepositoryUrl] = useState("")
  const [branch, setBranch] = useState("main")
  const [busy, setBusy] = useState(false)
  const [packageBusy, setPackageBusy] = useState<string | null>(null)
  const [sourceBusy, setSourceBusy] = useState<string | null>(null)
  const [zipFile, setZipFile] = useState<File | null>(null)
  const [zipBusy, setZipBusy] = useState(false)
  const [zipInspection, setZipInspection] = useState<Awaited<ReturnType<typeof portableCapabilitiesApi.inspectZip>> | null>(null)

  const packages = useSWR(
    user ? "portable-capability-packages" : null,
    () => portableCapabilitiesApi.listPackages(),
  )
  const marketplaces = useSWR(
    user ? "portable-capability-marketplaces" : null,
    () => portableCapabilitiesApi.listMarketplaces(),
  )
  const candidates = useSWR(
    user ? "portable-capability-marketplace-candidates" : null,
    () => portableCapabilitiesApi.listCandidates(),
  )

  const packageRows = packages.data?.items ?? []
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

  async function syncMarketplace(sourceId: string) {
    setSourceBusy(sourceId)
    try {
      const result = await portableCapabilitiesApi.syncMarketplace(sourceId)
      toast.success("Capability marketplace synced", {
        description: `${result.sync.ingested} package${result.sync.ingested === 1 ? "" : "s"} ingested`,
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

  async function prepareMcp(packageId: string) {
    setPackageBusy(packageId)
    try {
      const result = await portableCapabilitiesApi.prepareMcp(packageId)
      toast.success("MCP dependencies prepared", {
        description: `${result.prepared.length} server${result.prepared.length === 1 ? "" : "s"} added disabled for review`,
      })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "MCP preparation failed")
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
                <h2 className="text-sm font-medium text-foreground">Installed portable capabilities</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Agent Skills, Claude/OpenAI-style plugins, MCP packages, and Gravitre-native capabilities.
                </p>
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
              ) : (
                <ul className="divide-y divide-divide">
                  {packageRows.map((item) => (
                    <li key={item.id ?? `${item.name}:${item.version ?? ""}`} className="flex items-start justify-between gap-4 px-4 py-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-medium text-foreground">{item.name}</p>
                          <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                            {(item.package_format ?? "package").replace(/_/g, " ")}
                          </span>
                          {item.publisher_verified ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
                              <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
                              Trusted publisher
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
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={packageBusy === item.id}
                              onClick={() => void reviewPackage(item.id!, "disabled")}
                            >
                              Disable
                            </Button>
                            {item.status === "installed" && hasMcpDependency(item.inspection) ? (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={packageBusy === item.id}
                                onClick={() => void prepareMcp(item.id!)}
                              >
                                Prepare MCP
                              </Button>
                            ) : null}
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
            </GravitreSurface>
          </section>

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
                        <span className="rounded border border-divide px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
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
