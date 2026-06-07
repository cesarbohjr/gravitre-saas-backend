"use client"

import { useEffect, useMemo, useState } from "react"
import useSWR from "swr"
import { toast } from "sonner"
import {
  Palette,
  Check,
  Copy,
  Globe,
  ShieldCheck,
  ArrowRight,
  RotateCw,
  AlertTriangle,
  ImageIcon,
  Home,
  Lock,
} from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import { useEnterpriseBranding } from "@/lib/enterprise-branding-context"
import type {
  EnterpriseBranding,
  EnterpriseDnsRecord,
  EnterpriseDomainInstructions,
  EnterpriseDomainVerifyResult,
} from "@/types/api"
import { TabSkeleton } from "./enterprise-skeletons"

const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/
const DEFAULT_COLOR = "#0091FF"

function DnsRow({ record }: { record: EnterpriseDnsRecord }) {
  const [copied, setCopied] = useState<"host" | "value" | null>(null)
  const copy = async (text: string, which: "host" | "value") => {
    await navigator.clipboard.writeText(text)
    setCopied(which)
    setTimeout(() => setCopied(null), 1500)
  }
  return (
    <div className="rounded-lg border border-border bg-secondary/30 p-3">
      <div className="mb-2 flex items-center gap-2">
        <Badge variant="outline" className="font-mono text-[10px]">
          {record.type}
        </Badge>
        {record.ttl ? (
          <span className="text-[11px] text-muted-foreground">TTL {record.ttl}</span>
        ) : null}
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="space-y-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Host / Name
          </span>
          <div className="flex items-center gap-1.5">
            <code className="flex-1 truncate rounded border border-border bg-background px-2 py-1 font-mono text-xs">
              {record.host}
            </code>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={() => copy(record.host, "host")}
              aria-label="Copy host"
            >
              {copied === "host" ? (
                <Check className="h-3.5 w-3.5 text-success" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        </div>
        <div className="space-y-1">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Value
          </span>
          <div className="flex items-center gap-1.5">
            <code className="flex-1 truncate rounded border border-border bg-background px-2 py-1 font-mono text-xs">
              {record.value}
            </code>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0"
              onClick={() => copy(record.value, "value")}
              aria-label="Copy value"
            >
              {copied === "value" ? (
                <Check className="h-3.5 w-3.5 text-success" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

function LivePreview({
  logoUrl,
  primaryColor,
  hidePoweredBy,
}: {
  logoUrl: string | null
  primaryColor: string | null
  hidePoweredBy: boolean
}) {
  const color = primaryColor && HEX_RE.test(primaryColor) ? primaryColor : DEFAULT_COLOR
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-background shadow-sm">
      <div className="flex h-[320px]">
        {/* Mini sidebar */}
        <div className="flex w-40 shrink-0 flex-col border-r border-border bg-secondary/30 p-3">
          <div className="flex h-9 items-center">
            {logoUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={logoUrl || "/placeholder.svg"}
                alt="Preview logo"
                className="max-h-7 max-w-[110px] object-contain"
                crossOrigin="anonymous"
              />
            ) : (
              <span className="text-sm font-semibold text-foreground">Gravitre</span>
            )}
          </div>
          <div className="mt-4 space-y-1">
            <div
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium"
              style={{ backgroundColor: `${color}1a`, color }}
            >
              <Home className="h-3.5 w-3.5" />
              Dashboard
            </div>
            {["Agents", "Automations", "Approvals"].map((item) => (
              <div
                key={item}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground"
              >
                <span className="h-3.5 w-3.5 rounded-sm bg-muted" />
                {item}
              </div>
            ))}
          </div>
        </div>
        {/* Mini content */}
        <div className="flex flex-1 flex-col p-4">
          <div className="mb-3 flex items-center justify-between">
            <div className="h-4 w-24 rounded bg-muted" />
            <div
              className="rounded-md px-3 py-1.5 text-xs font-medium"
              style={{ backgroundColor: color, color: "#fff" }}
            >
              New run
            </div>
          </div>
          <div className="space-y-2">
            <div className="h-3 w-full rounded bg-muted/70" />
            <div className="h-3 w-4/5 rounded bg-muted/70" />
            <div className="h-3 w-3/5 rounded bg-muted/70" />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <div className="rounded-lg border border-border p-3">
              <div className="h-2.5 w-10 rounded bg-muted" />
              <div className="mt-2 text-lg font-semibold" style={{ color }}>
                128
              </div>
            </div>
            <div className="rounded-lg border border-border p-3">
              <div className="h-2.5 w-10 rounded bg-muted" />
              <div className="mt-2 text-lg font-semibold text-foreground">98%</div>
            </div>
          </div>
          <div className="mt-auto flex items-center justify-between pt-3">
            <div className="flex gap-2">
              <span
                className="inline-flex h-2 w-2 rounded-full"
                style={{ backgroundColor: color }}
                aria-hidden
              />
              <span className="text-[10px] text-muted-foreground">Live preview</span>
            </div>
            {!hidePoweredBy && (
              <span className="text-[10px] text-muted-foreground/60">Powered by Gravitre</span>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export function BrandingTab({ isAdmin }: { isAdmin: boolean }) {
  const { setPreview, refresh } = useEnterpriseBranding()
  const { data, isLoading, mutate } = useSWR<EnterpriseBranding>(
    "enterprise-branding-tab",
    () => enterpriseApi.getBranding(),
    { revalidateOnFocus: false },
  )

  const [logoUrl, setLogoUrl] = useState("")
  const [primaryColor, setPrimaryColor] = useState(DEFAULT_COLOR)
  const [hidePoweredBy, setHidePoweredBy] = useState(false)
  const [emailFromName, setEmailFromName] = useState("")
  const [domain, setDomain] = useState("")
  const [saving, setSaving] = useState(false)

  // DNS verification state
  const [instructions, setInstructions] = useState<EnterpriseDomainInstructions | null>(null)
  const [loadingDns, setLoadingDns] = useState(false)
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState<EnterpriseDomainVerifyResult | null>(null)

  // Seed local form state from fetched data
  useEffect(() => {
    if (!data) return
    setLogoUrl(data.logoUrl ?? "")
    setPrimaryColor(data.primaryColor && HEX_RE.test(data.primaryColor) ? data.primaryColor : DEFAULT_COLOR)
    setHidePoweredBy(Boolean(data.hidePoweredBy))
    setEmailFromName(data.emailFromName ?? "")
    setDomain(data.customDomain ?? "")
  }, [data])

  // Push live preview to the global provider; clear on unmount.
  useEffect(() => {
    setPreview({
      logoUrl: logoUrl.trim() || null,
      primaryColor: HEX_RE.test(primaryColor) ? primaryColor : null,
      hidePoweredBy,
    })
    return () => setPreview(null)
  }, [logoUrl, primaryColor, hidePoweredBy, setPreview])

  const colorValid = HEX_RE.test(primaryColor)
  const domainVerified = data?.customDomainVerified ?? false

  const currentStep = useMemo(() => {
    if (domainVerified) return 3
    if (instructions) return 2
    return 1
  }, [domainVerified, instructions])

  if (isLoading) return <TabSkeleton rows={4} />

  const handleSave = async () => {
    if (!isAdmin) return
    if (!colorValid) {
      toast.error("Enter a valid hex color (e.g. #0091FF)")
      return
    }
    setSaving(true)
    try {
      const updated = await enterpriseApi.updateBranding({
        logoUrl: logoUrl.trim() || null,
        primaryColor,
        hidePoweredBy,
        emailFromName: emailFromName.trim() || null,
        customDomain: domain.trim() || null,
      })
      await mutate(updated, { revalidate: false })
      refresh()
      toast.success("Branding saved")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save branding")
    } finally {
      setSaving(false)
    }
  }

  const loadDnsInstructions = async () => {
    if (!domain.trim()) {
      toast.error("Enter a domain first")
      return
    }
    setLoadingDns(true)
    setVerifyResult(null)
    try {
      // Persist the domain so the backend can issue records for it.
      await enterpriseApi.updateBranding({ customDomain: domain.trim() })
      const result = await enterpriseApi.getDomainInstructions()
      setInstructions(result)
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load DNS records")
    } finally {
      setLoadingDns(false)
    }
  }

  const handleVerify = async () => {
    setVerifying(true)
    try {
      const result = await enterpriseApi.verifyDomain()
      setVerifyResult(result)
      if (result.verified) {
        toast.success("Domain verified")
        await mutate()
        refresh()
      } else {
        toast.error("Verification failed — check your DNS records")
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Verification failed")
    } finally {
      setVerifying(false)
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_minmax(320px,420px)]">
      {/* Form column */}
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Palette className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">Brand elements</CardTitle>
            </div>
            <CardDescription>
              Customize the logo and primary color applied across dashboards for your organization.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="logo-url">Logo URL</Label>
              <div className="flex items-center gap-2">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-secondary/50">
                  <ImageIcon className="h-4 w-4 text-muted-foreground" />
                </span>
                <Input
                  id="logo-url"
                  placeholder="https://cdn.example.com/logo.svg"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  disabled={!isAdmin}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Paste a hosted image URL. Direct upload is coming soon.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="primary-color">Primary color</Label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  aria-label="Pick primary color"
                  value={colorValid ? primaryColor : DEFAULT_COLOR}
                  onChange={(e) => setPrimaryColor(e.target.value.toUpperCase())}
                  disabled={!isAdmin}
                  className="h-9 w-12 shrink-0 cursor-pointer rounded-md border border-border bg-transparent p-1 disabled:cursor-not-allowed"
                />
                <Input
                  id="primary-color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value.toUpperCase())}
                  disabled={!isAdmin}
                  className={cn("font-mono", !colorValid && "border-destructive")}
                  aria-invalid={!colorValid}
                />
              </div>
              {!colorValid && (
                <p className="text-xs text-destructive">Enter a valid hex color, e.g. #0091FF</p>
              )}
            </div>

            <Separator />

            <div className="flex items-center justify-between gap-4">
              <div className="space-y-0.5">
                <Label htmlFor="hide-powered-by">Hide &ldquo;Powered by Gravitre&rdquo;</Label>
                <p className="text-xs text-muted-foreground">
                  Removes the Gravitre attribution footer from the app shell.
                </p>
              </div>
              <Switch
                id="hide-powered-by"
                checked={hidePoweredBy}
                onCheckedChange={setHidePoweredBy}
                disabled={!isAdmin}
              />
            </div>

            <Separator />

            <div className="space-y-2">
              <Label htmlFor="email-from">Email sender name</Label>
              <Input
                id="email-from"
                placeholder="Acme Operations"
                value={emailFromName}
                onChange={(e) => setEmailFromName(e.target.value)}
                disabled={!isAdmin}
              />
              <p className="text-xs text-muted-foreground">
                Used as the &ldquo;From&rdquo; name on notification emails.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Custom domain stepper */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-primary" />
              <CardTitle className="text-base">Custom domain</CardTitle>
              {domainVerified && (
                <Badge className="gap-1 bg-success/15 text-success hover:bg-success/15">
                  <ShieldCheck className="h-3 w-3" /> Verified
                </Badge>
              )}
            </div>
            <CardDescription>
              Serve the dashboard from your own domain. Verification is DNS-based.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Stepper indicator */}
            <ol className="flex items-center gap-2">
              {[
                { n: 1, label: "Domain" },
                { n: 2, label: "DNS records" },
                { n: 3, label: "Verify" },
              ].map((step, i) => (
                <li key={step.n} className="flex flex-1 items-center gap-2">
                  <span
                    className={cn(
                      "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
                      currentStep > step.n
                        ? "bg-success text-white"
                        : currentStep === step.n
                          ? "bg-primary text-primary-foreground"
                          : "bg-secondary text-muted-foreground",
                    )}
                  >
                    {currentStep > step.n ? <Check className="h-3.5 w-3.5" /> : step.n}
                  </span>
                  <span
                    className={cn(
                      "text-xs font-medium",
                      currentStep >= step.n ? "text-foreground" : "text-muted-foreground",
                    )}
                  >
                    {step.label}
                  </span>
                  {i < 2 && <span className="h-px flex-1 bg-border" />}
                </li>
              ))}
            </ol>

            <Separator />

            {/* Step 1: domain entry */}
            <div className="space-y-2">
              <Label htmlFor="custom-domain">Domain</Label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  id="custom-domain"
                  placeholder="app.yourcompany.com"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  disabled={!isAdmin || domainVerified}
                />
                <Button
                  variant="outline"
                  onClick={loadDnsInstructions}
                  disabled={!isAdmin || loadingDns || domainVerified || !domain.trim()}
                  className="shrink-0 gap-1.5"
                >
                  {loadingDns ? "Loading…" : "Get DNS records"}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>

            {/* Step 2: DNS records */}
            {instructions && instructions.records.length > 0 && !domainVerified && (
              <div className="space-y-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Add these records at your DNS provider
                </span>
                {instructions.records.map((record, i) => (
                  <DnsRow key={`${record.type}-${i}`} record={record} />
                ))}
              </div>
            )}

            {/* Step 3: verify + actionable errors */}
            {instructions && !domainVerified && (
              <div className="space-y-3">
                <Button onClick={handleVerify} disabled={verifying} className="gap-1.5">
                  <RotateCw className={cn("h-3.5 w-3.5", verifying && "animate-spin")} />
                  {verifying ? "Verifying…" : "Verify domain"}
                </Button>

                {verifyResult && !verifyResult.verified && (
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertTitle>Verification incomplete</AlertTitle>
                    <AlertDescription className="space-y-1">
                      {verifyResult.checks.cname && !verifyResult.checks.cname.ok && (
                        <p className="text-xs">
                          <strong>CNAME:</strong>{" "}
                          {verifyResult.checks.cname.message ||
                            `Expected ${verifyResult.checks.cname.expected ?? "record"}${
                              verifyResult.checks.cname.found
                                ? `, found ${verifyResult.checks.cname.found}`
                                : " (not found)"
                            }`}
                        </p>
                      )}
                      {verifyResult.checks.txt && !verifyResult.checks.txt.ok && (
                        <p className="text-xs">
                          <strong>TXT:</strong>{" "}
                          {verifyResult.checks.txt.message ||
                            `Expected ${verifyResult.checks.txt.expected ?? "record"}${
                              verifyResult.checks.txt.found
                                ? `, found ${verifyResult.checks.txt.found}`
                                : " (not found)"
                            }`}
                        </p>
                      )}
                      <p className="pt-1 text-xs text-muted-foreground">
                        DNS changes can take a few minutes to propagate. Try again shortly.
                      </p>
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}

            {domainVerified && (
              <Alert>
                <ShieldCheck className="h-4 w-4 text-success" />
                <AlertTitle>Domain verified</AlertTitle>
                <AlertDescription>
                  {data?.customDomain} is verified and serving your dashboard.
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {!isAdmin && (
          <Alert>
            <Lock className="h-4 w-4" />
            <AlertTitle>Read-only</AlertTitle>
            <AlertDescription>
              Only organization admins can edit branding. You can preview current settings here.
            </AlertDescription>
          </Alert>
        )}

        {isAdmin && (
          <div className="flex items-center justify-end gap-2">
            <Button onClick={handleSave} disabled={saving || !colorValid} className="gap-1.5">
              {saving ? "Saving…" : "Save branding"}
            </Button>
          </div>
        )}
      </div>

      {/* Preview column (stacks below on mobile) */}
      <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Live preview
        </span>
        <LivePreview
          logoUrl={logoUrl.trim() || null}
          primaryColor={colorValid ? primaryColor : null}
          hidePoweredBy={hidePoweredBy}
        />
        <p className="text-xs text-muted-foreground">
          Preview reflects unsaved changes. Save to apply across the workspace.
        </p>
      </div>
    </div>
  )
}
