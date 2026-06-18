"use client"

import { useEffect, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { marketplaceApi } from "@/lib/api"
import { cn } from "@/lib/utils"
import { Bookmark, BookmarkCheck, Loader2, Star, Trash2 } from "lucide-react"
import { toast } from "sonner"
import type { MarketplaceReview } from "@/types/api"

function StarPicker({
  value,
  onChange,
  disabled,
}: {
  value: number
  onChange: (rating: number) => void
  disabled?: boolean
}) {
  return (
    <div className="flex gap-1" role="group" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          disabled={disabled}
          aria-label={`Rate ${star} stars`}
          onClick={() => onChange(star)}
          className={cn(
            "rounded p-0.5 transition-colors disabled:opacity-50",
            star <= value ? "text-warning" : "text-muted-foreground/40 hover:text-warning/70",
          )}
        >
          <Star className={cn("h-5 w-5", star <= value && "fill-current")} aria-hidden />
        </button>
      ))}
    </div>
  )
}

function ReviewRow({ review }: { review: MarketplaceReview }) {
  return (
    <li className="rounded-lg border border-border/60 bg-muted/10 p-3 text-sm">
      <div className="mb-1 flex items-center justify-between gap-2">
        <StarPicker value={review.rating} onChange={() => {}} disabled />
        {review.mine ? (
          <span className="text-[10px] font-medium uppercase tracking-wider text-primary">Your review</span>
        ) : null}
      </div>
      {review.title ? <p className="font-medium text-foreground">{review.title}</p> : null}
      {review.body ? <p className="mt-1 text-muted-foreground">{review.body}</p> : null}
    </li>
  )
}

export function AssetReviewsSection({
  assetRef,
  averageRating,
  reviewCount,
  onStatsChange,
}: {
  assetRef: string
  averageRating?: number | null
  reviewCount?: number
  onStatsChange?: () => void
}) {
  const { data, isLoading, mutate } = useSWR(["marketplace-reviews", assetRef], () =>
    marketplaceApi.listAssetReviews(assetRef, { limit: 20 }),
  )
  const { data: savesData, mutate: mutateSaves } = useSWR("marketplace-saves", () =>
    marketplaceApi.listSaves({ limit: 100 }),
  )

  const saved = Boolean(
    savesData?.saves?.some((entry) => entry.asset?.slug === assetRef || entry.assetId === data?.assetId),
  )

  const myReview = data?.myReview
  const [rating, setRating] = useState(0)
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    setRating(myReview?.rating ?? 0)
    setTitle(myReview?.title ?? "")
    setBody(myReview?.body ?? "")
  }, [myReview?.rating, myReview?.title, myReview?.body, myReview?.id])

  const syncForm = (review: MarketplaceReview | null | undefined) => {
    setRating(review?.rating ?? 0)
    setTitle(review?.title ?? "")
    setBody(review?.body ?? "")
  }

  const handleSaveToggle = async () => {
    setBusy("save")
    try {
      if (saved) {
        await marketplaceApi.unsaveAsset(assetRef)
        toast.success("Removed from saved")
      } else {
        await marketplaceApi.saveAsset(assetRef)
        toast.success("Saved to your list")
      }
      await mutateSaves()
      onStatsChange?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not update save")
    } finally {
      setBusy(null)
    }
  }

  const handleSubmitReview = async () => {
    if (rating < 1) {
      toast.error("Select a star rating")
      return
    }
    setBusy("review")
    try {
      await marketplaceApi.upsertAssetReview(assetRef, {
        rating,
        title: title.trim() || undefined,
        body: body.trim() || undefined,
      })
      toast.success(myReview ? "Review updated" : "Review submitted")
      await mutate()
      onStatsChange?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not submit review")
    } finally {
      setBusy(null)
    }
  }

  const handleDeleteReview = async () => {
    setBusy("delete")
    try {
      await marketplaceApi.deleteAssetReview(assetRef)
      syncForm(null)
      toast.success("Review removed")
      await mutate()
      onStatsChange?.()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not delete review")
    } finally {
      setBusy(null)
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">Reviews & saves</h3>
          <p className="text-xs text-muted-foreground">
            {averageRating != null ? `${averageRating.toFixed(1)} average` : "No ratings yet"}
            {reviewCount != null ? ` · ${reviewCount} review${reviewCount === 1 ? "" : "s"}` : null}
          </p>
        </div>
        <Button
          size="sm"
          variant={saved ? "secondary" : "outline"}
          disabled={Boolean(busy)}
          onClick={handleSaveToggle}
        >
          {busy === "save" ? (
            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
          ) : saved ? (
            <BookmarkCheck className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          ) : (
            <Bookmark className="mr-1.5 h-3.5 w-3.5" aria-hidden />
          )}
          {saved ? "Saved" : "Save"}
        </Button>
      </div>

      <div className="rounded-lg border bg-muted/10 p-4 space-y-3">
        <StarPicker value={rating || myReview?.rating || 0} onChange={setRating} disabled={busy === "review"} />
        <Input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Review title (optional)"
          disabled={Boolean(busy)}
        />
        <Textarea
          value={body}
          onChange={(event) => setBody(event.target.value)}
          placeholder="Share how this asset helped your team…"
          rows={3}
          disabled={Boolean(busy)}
        />
        <div className="flex flex-wrap gap-2">
          <Button size="sm" disabled={Boolean(busy)} onClick={handleSubmitReview}>
            {busy === "review" ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : null}
            {myReview ? "Update review" : "Submit review"}
          </Button>
          {myReview ? (
            <Button size="sm" variant="ghost" disabled={Boolean(busy)} onClick={handleDeleteReview}>
              {busy === "delete" ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Trash2 className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              )}
              Remove
            </Button>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading reviews…</p>
      ) : data?.reviews?.length ? (
        <ul className="space-y-2">
          {data.reviews.map((review) => (
            <ReviewRow key={review.id} review={review} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">No reviews yet — be the first.</p>
      )}
    </section>
  )
}
