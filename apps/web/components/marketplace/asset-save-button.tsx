"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { Bookmark, BookmarkCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { marketplaceApi } from "@/lib/api"
import { cn } from "@/lib/utils"
import { toast } from "sonner"

export function AssetSaveButton({
  slug,
  assetId,
  size = "sm",
  variant = "ghost",
  className,
}: {
  slug: string
  assetId?: string
  size?: "sm" | "icon"
  variant?: "ghost" | "outline"
  className?: string
}) {
  const { data: savesData, mutate } = useSWR("marketplace-saves", () =>
    marketplaceApi.listSaves({ limit: 200 }),
  )

  const serverSaved = Boolean(
    savesData?.saves?.some(
      (entry) => entry.asset?.slug === slug || (assetId && entry.assetId === assetId),
    ),
  )

  // Optimistic override so the button flips immediately on click and stays
  // highlighted, instead of waiting on (and depending on) a list re-fetch that
  // can lag or fail to match the new entry.
  const [optimistic, setOptimistic] = useState<boolean | null>(null)
  const [pending, setPending] = useState(false)

  // Once the server list catches up to our optimistic value, drop the override
  // so this stays in sync with other instances of the same asset.
  useEffect(() => {
    if (optimistic !== null && serverSaved === optimistic) {
      setOptimistic(null)
    }
  }, [optimistic, serverSaved])

  const saved = optimistic ?? serverSaved

  async function toggleSave(event: React.MouseEvent) {
    event.stopPropagation()
    event.preventDefault()
    if (pending) return

    const next = !saved
    setOptimistic(next)
    setPending(true)
    try {
      const result = next
        ? await marketplaceApi.saveAsset(slug)
        : await marketplaceApi.unsaveAsset(slug)
      // Trust the authoritative result from the API.
      setOptimistic(result.saved)
      toast.success(result.saved ? "Saved to your list" : "Removed from saved")
      await mutate()
    } catch (err) {
      setOptimistic(null)
      toast.error(err instanceof Error ? err.message : "Could not update save")
    } finally {
      setPending(false)
    }
  }

  if (size === "icon") {
    return (
      <Button
        type="button"
        size="icon"
        variant={saved ? "secondary" : variant}
        className={cn(
          "h-8 w-8 shrink-0",
          saved && "border-primary/30 bg-primary/10 text-primary hover:bg-primary/15",
          className,
        )}
        aria-label={saved ? "Remove from saved" : "Save asset"}
        aria-pressed={saved}
        onClick={toggleSave}
      >
        {saved ? (
          <BookmarkCheck className="h-4 w-4" aria-hidden />
        ) : (
          <Bookmark className="h-4 w-4" aria-hidden />
        )}
      </Button>
    )
  }

  return (
    <Button
      type="button"
      size="sm"
      variant={saved ? "secondary" : variant}
      className={cn(
        saved && "border-primary/30 bg-primary/10 text-primary hover:bg-primary/15",
        className,
      )}
      aria-pressed={saved}
      onClick={toggleSave}
    >
      {saved ? (
        <BookmarkCheck className="mr-1.5 h-3.5 w-3.5" aria-hidden />
      ) : (
        <Bookmark className="mr-1.5 h-3.5 w-3.5" aria-hidden />
      )}
      {saved ? "Saved" : "Save"}
    </Button>
  )
}
