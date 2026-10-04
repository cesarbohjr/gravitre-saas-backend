"use client"

import { useEffect, useId, useRef, useState } from "react"
import useSWR from "swr"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { AssetSaveButton } from "@/components/marketplace/asset-save-button"
import { MarketplaceDecisionDialog } from "@/components/marketplace/marketplace-decision-dialog"
import { marketplaceApi } from "@/lib/api"
import { Star } from "lucide-react"
import { toast } from "sonner"

type Props = {
  assetRef: string
  averageRating?: number | null
  reviewCount?: number
  onStatsChange?: () => void
}
export function AssetReviewsSection(props: Props) {
  return <ReviewSession key={props.assetRef} {...props} />
}
function ReviewSession({
  assetRef,
  averageRating,
  reviewCount,
  onStatsChange,
}: Props) {
  const { data, error, isLoading, mutate } = useSWR(
    ["marketplace-reviews", assetRef],
    () => marketplaceApi.listAssetReviews(assetRef, { limit: 20 }),
  )
  const [rating, setRating] = useState(0)
  const [title, setTitle] = useState("")
  const [body, setBody] = useState("")
  const [busy, setBusy] = useState(false)
  const [failure, setFailure] = useState<string | null>(null)
  const [removeOpen, setRemoveOpen] = useState(false)
  const dirty = useRef(false)
  const lock = useRef(false)
  const id = useId()
  const review = data?.myReview
  useEffect(() => {
    if (dirty.current || lock.current) return
    setRating(review?.rating ?? 0)
    setTitle(review?.title ?? "")
    setBody(review?.body ?? "")
  }, [review?.rating, review?.title, review?.body, review?.id])
  async function submit() {
    if (lock.current || !data) return
    if (rating < 1 || rating > 5) {
      setFailure("Select a rating from one to five stars.")
      return
    }
    lock.current = true
    setBusy(true)
    setFailure(null)
    try {
      const result = await marketplaceApi.upsertAssetReview(assetRef, {
        rating,
        title: title.trim() || undefined,
        body: body.trim() || undefined,
      })
      if (!result.review)
        throw new Error("The server did not return a saved review")
      dirty.current = false
      await mutate({ ...data, myReview: result.review }, { revalidate: false })
      toast.success("Review saved")
      onStatsChange?.()
      await Promise.allSettled([mutate()])
    } catch (err) {
      setFailure(
        err instanceof Error
          ? err.message
          : "Review could not be saved. Your edits are retained.",
      )
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  async function remove() {
    if (lock.current || !review)
      throw new Error("Another review update is pending")
    lock.current = true
    setBusy(true)
    try {
      const result = await marketplaceApi.deleteAssetReview(assetRef)
      if (!result.deleted)
        throw new Error("The server did not confirm review removal")
      dirty.current = false
      setRating(0)
      setTitle("")
      setBody("")
      await mutate(
        {
          ...data,
          myReview: null,
          reviews: data?.reviews.filter((row) => row.id !== review.id),
        },
        { revalidate: false },
      )
      toast.success("Review removed")
      onStatsChange?.()
      await Promise.allSettled([mutate()])
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  return (
    <section className="space-y-4 [&_[data-slot=button]]:min-h-11 [&_input]:min-h-11">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold">Reviews & saves</h3>
          <p className="text-xs text-muted-foreground">
            {averageRating == null
              ? "Average rating not reported"
              : `${averageRating.toFixed(1)} average`}
            {reviewCount == null
              ? " · Review count not reported"
              : ` · ${reviewCount} reviews`}
          </p>
        </div>
        <AssetSaveButton slug={assetRef} variant="outline" />
      </header>
      {error ? (
        <div role="alert" className="space-y-2 text-sm">
          <p>
            Could not refresh reviews. Loaded reviews and your draft remain
            available.
          </p>
          <Button variant="outline" onClick={() => void mutate()}>
            Retry reviews
          </Button>
        </div>
      ) : null}
      {isLoading && !data ? (
        <p role="status" className="text-sm">
          Loading reviews…
        </p>
      ) : null}
      {data ? (
        <details className="border-y border-[color:var(--g-border-subtle)] py-2">
          <summary className="min-h-11 cursor-pointer py-3 text-sm font-medium">
            {review ? "Edit your review" : "Share your experience"}
          </summary>
          <fieldset disabled={busy} className="min-w-0 space-y-3 py-3">
            <div
              role="group"
              aria-label="Your rating"
              className="flex flex-wrap gap-1"
            >
              {[1, 2, 3, 4, 5].map((star) => (
                <Button
                  key={star}
                  variant="ghost"
                  className="min-w-11 px-2"
                  aria-label={`Rate ${star} stars`}
                  aria-pressed={rating === star}
                  onClick={() => {
                    dirty.current = true
                    setRating(star)
                  }}
                >
                  <Star
                    className={
                      star <= rating
                        ? "size-5 fill-warning text-warning"
                        : "size-5 text-muted-foreground"
                    }
                    aria-hidden
                  />
                </Button>
              ))}
            </div>
            <label htmlFor={`${id}-title`} className="block text-sm">
              Review title (optional)
            </label>
            <Input
              id={`${id}-title`}
              value={title}
              onChange={(e) => {
                dirty.current = true
                setTitle(e.target.value)
              }}
            />
            <label htmlFor={`${id}-body`} className="block text-sm">
              Your experience (optional)
            </label>
            <Textarea
              id={`${id}-body`}
              value={body}
              onChange={(e) => {
                dirty.current = true
                setBody(e.target.value)
              }}
              rows={3}
            />
            {failure ? (
              <p role="alert" className="text-sm text-destructive">
                {failure}
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void submit()}>
                {busy ? "Saving…" : review ? "Update review" : "Submit review"}
              </Button>
              {review ? (
                <Button variant="ghost" onClick={() => setRemoveOpen(true)}>
                  Remove review
                </Button>
              ) : null}
            </div>
          </fieldset>
        </details>
      ) : null}
      {data?.reviews.length ? (
        <ul className="divide-y divide-border">
          {data.reviews.map((row) => (
            <li key={row.id} className="space-y-1 py-3 text-sm">
              <p className="text-xs text-muted-foreground">
                {row.rating} / 5 stars{row.mine ? " · Your review" : ""}
              </p>
              {row.title ? <p className="font-medium">{row.title}</p> : null}
              {row.body ? (
                <p className="whitespace-pre-wrap break-words text-muted-foreground">
                  {row.body}
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      ) : data ? (
        <p className="text-sm text-muted-foreground">No reviews returned.</p>
      ) : null}
      {removeOpen ? (
        <MarketplaceDecisionDialog
          title="Remove your review?"
          description="Your rating and review text will be removed from this asset."
          actionLabel="Confirm review removal"
          destructive
          onCancel={() => setRemoveOpen(false)}
          onConfirm={remove}
        />
      ) : null}
    </section>
  )
}
