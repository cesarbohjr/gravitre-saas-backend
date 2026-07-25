"use client"

import { useState } from "react"
import { BookOpen, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { knowledgeSyncApi } from "@/lib/api"
import { useOrgAdmin } from "@/lib/use-org-admin"
import { cn } from "@/lib/utils"

const KNOWLEDGE_CONNECTOR_TYPES = new Set(["notion", "confluence", "hubspot", "zendesk"])

type KnowledgeSyncButtonProps = {
  connectorId: string
  connectorType?: string | null
  connectorStatus?: string | null
  className?: string
  size?: "sm" | "default"
}

export function KnowledgeSyncButton({
  connectorId,
  connectorType,
  connectorStatus,
  className,
  size = "sm",
}: KnowledgeSyncButtonProps) {
  const { isAdmin } = useOrgAdmin()
  const [loading, setLoading] = useState(false)

  const normalizedType = String(connectorType ?? "").toLowerCase()
  const isKnowledgeConnector = KNOWLEDGE_CONNECTOR_TYPES.has(normalizedType)
  const isActive = String(connectorStatus ?? "").toLowerCase() === "active"

  if (!isKnowledgeConnector || !isActive || !isAdmin) {
    return null
  }

  const runSync = async () => {
    setLoading(true)
    try {
      await knowledgeSyncApi.triggerConnectorSync(connectorId, { fullSync: false })
      toast.success("Knowledge sync queued", {
        description: isAdmin
          ? "Incremental sync started. Use Enterprise → Knowledge Sync for full sync."
          : "Your connector content will be ingested into the knowledge base.",
      })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start knowledge sync")
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button
      type="button"
      variant="outline"
      size={size}
      className={cn("gap-2", className)}
      disabled={loading}
      onClick={() => void runSync()}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <BookOpen className="h-4 w-4" aria-hidden />
      )}
      Sync knowledge
    </Button>
  )
}
