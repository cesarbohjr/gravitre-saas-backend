"use client"

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

  const saved = Boolean(
    savesData?.saves?.some(
      (entry) => entry.asset?.slug === slug || (assetId && entry.assetId === assetId),
    ),
  )

  async function toggleSave(event: React.MouseEvent) {
    event.stopPropagation()
    event.preventDefault()
    try {
      if (saved) {
        await marketplaceApi.unsaveAsset(slug)
        toast.success("Removed from saved")
      } else {
        await marketplaceApi.saveAsset(slug)
        toast.success("Saved to your list")
      }
      await mutate()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update save")
    }
  }

  if (size === "icon") {
    return (
      <Button
        type="button"
        size="icon"
        variant={saved ? "secondary" : variant}
        className={cn("h-8 w-8 shrink-0", className)}
        aria-label={saved ? "Remove from saved" : "Save asset"}
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
      className={className}
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