"use client"

import { useState } from "react"
import useSWR from "swr"
import { FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { WorkSectionErrorCard } from "@/components/gravitre/work-section-error-card"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"

export default function LiteDeliverablesPage() {
  const { user, loading } = useAuth()
  const { data, isLoading, error, mutate } = useSWR(
    user ? ["lite-deliverables", user.id] : null,
    () => liteApi.listDeliverables(),
    { revalidateOnFocus: false, refreshInterval: 15000 },
  )
  const [downloadingId, setDownloadingId] = useState<string | null>(null)

  const handleDownload = async (id: string, name: string) => {
    setDownloadingId(id)
    try {
      const response = await liteApi.downloadDeliverable(id)
      if (!response.ok) {
        throw new Error("Download failed")
      }
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = name || "deliverable.json"
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
      toast.success("Download started")
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Unable to download")
    } finally {
      setDownloadingId(null)
    }
  }

  if (!loading && !isLoading && !user) {
    return (
      <LitePageShell title="Deliverables" description="Sign in to continue." icon={FileText}>
        <p className="text-sm text-muted-foreground">Sign in required.</p>
      </LitePageShell>
    )
  }

  const deliverables = data?.deliverables ?? []

  return (
    <LitePageShell
      title="Deliverables"
      description="Outputs ready to download from your team."
      icon={FileText}
      loading={loading || isLoading}
      loadingLabel="Loading deliverables"
    >
      {error ? <WorkSectionErrorCard title="Could not load deliverables" message={error instanceof Error ? error.message : "Try again to retrieve the latest data."} onRetry={() => void mutate()} /> : null}
      <div className="divide-y divide-divide border-y border-divide">
        {deliverables.map((item) => (
          <div key={item.id} className="py-4">
            <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex-1">
                <p className="break-words font-medium">{item.name}</p>
                <p className="break-words text-xs text-muted-foreground">{item.task_name || item.task_id}</p>
                <div className="mt-1 flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {item.type}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {item.size_bytes == null ? "Size not reported" : `${Math.round(item.size_bytes / 1024)} KB`}
                  </span>
                </div>
              </div>
              <Button
                className="min-h-11 shrink-0 gap-2"
                onClick={() => handleDownload(item.id, item.name)}
                disabled={Boolean(downloadingId)}
              >
                <Icon
                  name="download"
                  size="sm"
                  className={cn(downloadingId === item.id && "animate-pulse motion-reduce:animate-none")}
                />
                {downloadingId === item.id ? "Downloading..." : "Download"}
              </Button>
            </div>
          </div>
        ))}
        {!error && !deliverables.length ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No deliverables yet.
          </div>
        ) : null}
      </div>
    </LitePageShell>
  )
}
