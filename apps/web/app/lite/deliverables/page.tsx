"use client"

import { useState } from "react"
import useSWR from "swr"
import { FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Icon } from "@/lib/icons"
import { cn } from "@/lib/utils"
import { liteApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { toast } from "sonner"
import { LitePageShell } from "@/components/gravitre/lite-page-shell"

export default function LiteDeliverablesPage() {
  const { user, loading } = useAuth()
  const { data, isLoading } = useSWR(
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
      <div className="space-y-3">
        {deliverables.map((item) => (
          <Card key={item.id} className="border-border/50 p-4">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium">{item.name}</p>
                <p className="text-xs text-muted-foreground">{item.task_name || item.task_id}</p>
                <div className="mt-1 flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {item.type}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(item.size_bytes / 1024)} KB
                  </span>
                </div>
              </div>
              <Button
                className="gap-2"
                onClick={() => handleDownload(item.id, item.name)}
                disabled={downloadingId === item.id}
              >
                <Icon
                  name="download"
                  size="sm"
                  className={cn(downloadingId === item.id && "animate-pulse")}
                />
                {downloadingId === item.id ? "Downloading..." : "Download"}
              </Button>
            </div>
          </Card>
        ))}
        {!deliverables.length ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            No deliverables yet.
          </Card>
        ) : null}
      </div>
    </LitePageShell>
  )
}
