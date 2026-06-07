"use client"

import { useState } from "react"
import { Check, Loader2, Save, Upload } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { enterpriseApi } from "@/lib/api"
import { BrandingPreview } from "./branding-preview"
import { DnsRecordRow } from "./dns-record-row"
import type { DnsInstructions, DomainVerifyResult } from "./types"

interface BrandingTabProps {
  isAdmin: boolean
  isLoading: boolean
  logoUrl: string
  primaryColor: string
  customDomain: string
  domainVerified: boolean
  hidePoweredBy: boolean
  emailFromName: string
  onLogoUrlChange: (v: string) => void
  onPrimaryColorChange: (v: string) => void
  onCustomDomainChange: (v: string) => void
  onHidePoweredByChange: (v: boolean) => void
  onEmailFromNameChange: (v: string) => void
  onSaved: () => Promise<void>
}

type DomainStep = 1 | 2 | 3

export function BrandingTab({
  isAdmin,
  isLoading,
  logoUrl,
  primaryColor,
  customDomain,
  domainVerified,
  hidePoweredBy,
  emailFromName,
  onLogoUrlChange,
  onPrimaryColorChange,
  onCustomDomainChange,
  onHidePoweredByChange,
  onEmailFromNameChange,
  onSaved,
}: BrandingTabProps) {
  const [saving, setSaving] = useState(false)
  const [domainStep, setDomainStep] = useState<DomainStep>(1)
  const [instructions, setInstructions] = useState<DnsInstructions | null>(null)
  const [verifyChecks, setVerifyChecks] = useState<DomainVerifyResult["checks"] | null>(null)

  const handleSave = async () => {
    if (!isAdmin) return
    setSaving(true)
    try {
      await enterpriseApi.updateBranding({
        logoUrl: logoUrl || undefined,
        primaryColor,
        customDomain: customDomain || undefined,
        hidePoweredBy,
        emailFromName: emailFromName || undefined,
      })
      toast.success("Branding updated")
      await onSaved()
      setInstructions(null)
      setVerifyChecks(null)
      if (customDomain) setDomainStep(2)
    } catch {
      toast.error("Failed to update branding")
    } finally {
      setSaving(false)
    }
  }

  const loadInstructions = async () => {
    try {
      const data = await enterpriseApi.getDomainInstructions()
      setInstructions(data as DnsInstructions)
      setDomainStep(2)
    } catch {
      toast.error("Save domain first, then load DNS records")
    }
  }

  const verifyDomain = async () => {
    setSaving(true)
    setVerifyChecks(null)
    try {
      const result = (await enterpriseApi.verifyDomain()) as DomainVerifyResult
      if (result.verified) {
        toast.success("Domain verified")
        setDomainStep(3)
        await onSaved()
      } else {
        setVerifyChecks(result.checks ?? null)
        toast.error("DNS records not detected yet")
      }
    } catch {
      toast.error("Verification failed")
    } finally {
      setSaving(false)
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-6 lg:grid-cols-2">
        <Skeleton className="h-96 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  const cname = instructions?.cnameRecord
  const txt = instructions?.txtRecord

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr,min(320px,100%)]">
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">White-label branding</CardTitle>
            <CardDescription>Customize the app shell and transactional email sender name.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <Label htmlFor="logo-url">Logo URL</Label>
              <div className="mt-1 flex gap-2">
                <Input id="logo-url" value={logoUrl} disabled={!isAdmin} onChange={(e) => onLogoUrlChange(e.target.value)} placeholder="https://..." />
                <Button type="button" variant="outline" size="icon" disabled title="URL upload only">
                  <Upload className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div>
              <Label htmlFor="primary-color">Primary color</Label>
              <div className="mt-1 flex gap-2">
                <Input id="primary-color" type="color" value={primaryColor} disabled={!isAdmin} onChange={(e) => onPrimaryColorChange(e.target.value)} className="h-10 w-14 cursor-pointer p-1" />
                <Input value={primaryColor} disabled={!isAdmin} onChange={(e) => onPrimaryColorChange(e.target.value)} className="font-mono" />
              </div>
            </div>
            <div>
              <Label htmlFor="email-from">Email from name</Label>
              <Input id="email-from" value={emailFromName} disabled={!isAdmin} onChange={(e) => onEmailFromNameChange(e.target.value)} className="mt-1" />
            </div>
            <div className="flex items-center justify-between rounded-lg border border-border p-3">
              <div>
                <p className="text-sm font-medium">Hide &quot;Powered by Gravitre&quot;</p>
                <p className="text-xs text-muted-foreground">Remove footer attribution in the app shell</p>
              </div>
              <Switch checked={hidePoweredBy} disabled={!isAdmin} onCheckedChange={onHidePoweredByChange} />
            </div>
            <Button size="sm" className="gap-2" disabled={!isAdmin || saving} onClick={handleSave}>
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              Save branding
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Custom domain</CardTitle>
            <CardDescription>Verify ownership via CNAME or TXT record.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {([1, 2, 3] as DomainStep[]).map((step) => (
                <Badge
                  key={step}
                  variant={domainStep >= step || (step === 3 && domainVerified) ? "default" : "outline"}
                  className={cn(step === 3 && domainVerified && "bg-emerald-600 hover:bg-emerald-600")}
                >
                  {step === 1 && "1. Enter domain"}
                  {step === 2 && "2. DNS records"}
                  {step === 3 && (domainVerified ? "Verified" : "3. Verify")}
                </Badge>
              ))}
            </div>

            <div>
              <Label htmlFor="custom-domain">Domain</Label>
              <Input
                id="custom-domain"
                value={customDomain}
                disabled={!isAdmin}
                onChange={(e) => {
                  onCustomDomainChange(e.target.value)
                  setDomainStep(1)
                  setInstructions(null)
                }}
                placeholder="app.example.com"
                className="mt-1"
              />
            </div>

            {customDomain && domainStep >= 2 && (
              <>
                <Separator />
                {cname && txt ? (
                  <div className="space-y-3">
                    <DnsRecordRow label="CNAME" type={cname.type} host={cname.host} value={cname.value} />
                    <DnsRecordRow label="TXT" type={txt.type} host={txt.host} value={txt.value} />
                  </div>
                ) : (
                  <Button type="button" size="sm" variant="outline" disabled={!isAdmin || saving} onClick={loadInstructions}>
                    Show DNS records
                  </Button>
                )}
                <div className="flex flex-wrap gap-2">
                  {!instructions && (
                    <Button type="button" size="sm" variant="outline" disabled={!isAdmin || saving} onClick={loadInstructions}>
                      Load DNS records
                    </Button>
                  )}
                  <Button type="button" size="sm" disabled={!isAdmin || saving || domainVerified} onClick={verifyDomain}>
                    {domainVerified ? (
                      <>
                        <Check className="mr-1 h-3.5 w-3.5" /> Verified
                      </>
                    ) : (
                      "Verify domain"
                    )}
                  </Button>
                </div>
                {verifyChecks && !domainVerified && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground space-y-1">
                    <p className="font-medium text-amber-700 dark:text-amber-400">DNS checks failed</p>
                    {verifyChecks.cname && (
                      <p>CNAME: expected <code>{verifyChecks.cname.expected}</code>, found {verifyChecks.cname.found?.length ? verifyChecks.cname.found.join(", ") : "none"}</p>
                    )}
                    {verifyChecks.txt && (
                      <p>TXT: expected <code>{verifyChecks.txt.expected}</code>, found {verifyChecks.txt.found?.length ? verifyChecks.txt.found.join(", ") : "none"}</p>
                    )}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="lg:sticky lg:top-4 lg:self-start">
        <BrandingPreview
          logoUrl={logoUrl}
          primaryColor={primaryColor}
          hidePoweredBy={hidePoweredBy}
          emailFromName={emailFromName}
        />
      </div>
    </div>
  )
}
