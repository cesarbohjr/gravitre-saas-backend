"use client"

import { useState, type ChangeEvent } from "react"
import useSWR from "swr"
import { toast } from "@/components/agents/overlays/toast"
import { CheckCircle2, HardDrive, Info, Lock, PlugZap, Trash2, XCircle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { cn } from "@/lib/utils"
import { storageApi, type ByoStorageStatus, type ByoStorageTarget } from "@/lib/api"
import { TabSkeleton } from "./enterprise-skeletons"

export const BYO_STORAGE_SWR_KEY = "settings-storage-byo"

const STATUS_COPY: Record<ByoStorageTarget["status"], { label: string; tone: string }> = {
  untested: { label: "Not tested yet", tone: "text-muted-foreground" },
  verified: { label: "Connected", tone: "text-success" },
  failed: { label: "Connection failed", tone: "text-destructive" },
}

type FormState = {
  endpointUrl: string
  region: string
  bucket: string
  pathPrefix: string
  accessKeyId: string
  secretAccessKey: string
}

const EMPTY_FORM: FormState = {
  endpointUrl: "",
  region: "",
  bucket: "",
  pathPrefix: "",
  accessKeyId: "",
  secretAccessKey: "",
}

/** Enterprise: keep uploaded files in the organization's own S3-compatible bucket. */
export function FileStorageTab({ isAdmin }: { isAdmin: boolean }) {
  const { data, isLoading, mutate } = useSWR<ByoStorageStatus>(BYO_STORAGE_SWR_KEY, () => storageApi.getByo(), {
    revalidateOnFocus: false,
  })
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [seed, setSeed] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [removing, setRemoving] = useState(false)

  const target = data?.target ?? null
  const targetSeed = target ? `${target.bucket}|${target.region}|${target.updatedAt ?? ""}` : "none"
  if (data && targetSeed !== seed) {
    setSeed(targetSeed)
    setForm({
      endpointUrl: target?.endpointUrl ?? "",
      region: target?.region ?? "",
      bucket: target?.bucket ?? "",
      pathPrefix: target?.pathPrefix ?? "",
      accessKeyId: "",
      secretAccessKey: "",
    })
  }

  if (isLoading) return <TabSkeleton rows={3} />
  if (!data?.available) return null

  const set = (key: keyof FormState) => (e: ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }))

  const handleSave = async () => {
    setSaving(true)
    try {
      const saved = await storageApi.saveByo({
        endpointUrl: form.endpointUrl.trim() || undefined,
        region: form.region.trim(),
        bucket: form.bucket.trim(),
        pathPrefix: form.pathPrefix.trim() || undefined,
        // Blank keeps the saved keys when updating.
        accessKeyId: form.accessKeyId.trim() || undefined,
        secretAccessKey: form.secretAccessKey || undefined,
      })
      await mutate({ ...data, target: saved.target }, { revalidate: false })
      toast.success("Saved. Run a connection test before files are sent there.")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not save the storage settings")
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async () => {
    setTesting(true)
    try {
      const result = await storageApi.testByo()
      await mutate({ ...data, target: result.target }, { revalidate: false })
      if (result.ok) toast.success("Connection works. New files will be stored in your bucket.")
      else toast.error(result.error ?? "The connection test failed")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "The connection test failed")
    } finally {
      setTesting(false)
    }
  }

  const handleRemove = async () => {
    setRemoving(true)
    try {
      await storageApi.removeByo()
      await mutate({ ...data, target: null }, { revalidate: false })
      toast.success("Removed. New files will be stored with Gravitre again.")
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not remove the storage settings")
    } finally {
      setRemoving(false)
    }
  }

  const status = target ? STATUS_COPY[target.status] : null
  const canSave = isAdmin && form.region.trim() && form.bucket.trim() && (target || (form.accessKeyId && form.secretAccessKey))

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <HardDrive className="h-4 w-4 text-primary" aria-hidden="true" />
            <CardTitle className="text-base">Your own file storage</CardTitle>
          </div>
          <CardDescription>
            Store the files your team uploads, and the documents Gravitre creates for you, in a bucket your organization
            owns. Any storage service that works like Amazon S3 can be used.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Alert>
            <Info className="h-4 w-4" />
            <AlertTitle>What moves, and what stays</AlertTitle>
            <AlertDescription>
              {data.scope} Files saved before you connect a bucket stay where they are and keep working.
            </AlertDescription>
          </Alert>

          {status ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {target?.status === "verified" ? (
                <CheckCircle2 className="h-4 w-4 text-success" aria-hidden="true" />
              ) : target?.status === "failed" ? (
                <XCircle className="h-4 w-4 text-destructive" aria-hidden="true" />
              ) : (
                <PlugZap className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              )}
              <span className={cn("font-medium", status.tone)}>{status.label}</span>
              {target?.lastTestedAt ? (
                <span className="text-xs text-muted-foreground">
                  Last tested {new Date(target.lastTestedAt).toLocaleString()}
                </span>
              ) : null}
              {target?.status !== "verified" ? (
                <Badge variant="secondary" className="text-[10px]">
                  Files go to Gravitre until a test passes
                </Badge>
              ) : null}
            </div>
          ) : null}
          {target?.lastTestError ? <p className="text-xs text-destructive">{target.lastTestError}</p> : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="byo-endpoint">Server address (optional)</Label>
              <Input
                id="byo-endpoint"
                placeholder="https://s3.example.com"
                value={form.endpointUrl}
                onChange={set("endpointUrl")}
                disabled={!isAdmin}
                autoComplete="off"
              />
              <p className="text-xs text-muted-foreground">Leave empty for Amazon S3. Must start with https://.</p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="byo-region">Region</Label>
              <Input id="byo-region" placeholder="us-east-1" value={form.region} onChange={set("region")} disabled={!isAdmin} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="byo-bucket">Bucket name</Label>
              <Input id="byo-bucket" placeholder="acme-gravitre-files" value={form.bucket} onChange={set("bucket")} disabled={!isAdmin} />
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="byo-prefix">Folder inside the bucket (optional)</Label>
              <Input id="byo-prefix" placeholder="gravitre/" value={form.pathPrefix} onChange={set("pathPrefix")} disabled={!isAdmin} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="byo-access-key">Access key ID</Label>
              <Input
                id="byo-access-key"
                placeholder={target?.accessKeyHint ? `Saved (ends in ${target.accessKeyHint})` : "Access key ID"}
                value={form.accessKeyId}
                onChange={set("accessKeyId")}
                disabled={!isAdmin}
                autoComplete="off"
                className="font-mono text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="byo-secret">Secret access key</Label>
              <Input
                id="byo-secret"
                type="password"
                placeholder={target ? "Saved — enter a new one to replace it" : "Secret access key"}
                value={form.secretAccessKey}
                onChange={set("secretAccessKey")}
                disabled={!isAdmin}
                autoComplete="new-password"
                className="font-mono text-sm"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Keys are encrypted before they are stored and are never shown again. Give them permission to add, read and
            delete objects in this bucket only.
          </p>

          {!isAdmin ? (
            <Alert>
              <Lock className="h-4 w-4" />
              <AlertTitle>Read-only</AlertTitle>
              <AlertDescription>Only organization admins can change where files are stored.</AlertDescription>
            </Alert>
          ) : (
            <div className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-col gap-2 sm:flex-row">
                <Button variant="outline" onClick={handleTest} disabled={!target || testing} className="gap-1.5">
                  <PlugZap className={cn("h-3.5 w-3.5", testing && "animate-pulse")} />
                  {testing ? "Testing…" : "Test connection"}
                </Button>
                {target ? (
                  <Button
                    variant="ghost"
                    onClick={handleRemove}
                    disabled={removing}
                    className="gap-1.5 text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {removing ? "Removing…" : "Remove"}
                  </Button>
                ) : null}
              </div>
              <Button onClick={handleSave} disabled={!canSave || saving}>
                {saving ? "Saving…" : "Save"}
              </Button>
            </div>
          )}
          {target ? (
            <p className="text-xs text-muted-foreground">
              Removing stops new files going to your bucket. Files already there stay in your bucket and can no longer
              be opened from Gravitre.
            </p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}
