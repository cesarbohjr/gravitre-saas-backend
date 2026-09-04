import Image from "next/image"
import { cn } from "@/lib/utils"

/**
 * Real UI captures from scripts/capture-product-shots.mjs (2880x1800 @2x).
 *
 * Shots are rendered against seeded fixture data in
 * apps/web/lib/e2e-shot-fixtures.ts. Prefer a visible `caption` when the frame
 * could be mistaken for live customer metrics; some marketing surfaces omit it
 * by product request when surrounding copy already scopes the demo.
 */
export interface ProductScreenshotProps {
  /** Path under /public, e.g. "/product/app-approvals.png". */
  src: string
  /** Describe the UI state shown, not just the page name. */
  alt: string
  /** Optional provenance note under the frame. */
  caption?: string
  /** Set on the first shot above the fold only. */
  priority?: boolean
  /**
   * Window-chrome label. When provided, the shot is framed as an app window
   * with a title pill — the treatment the hand-built mockups on /features used
   * before real captures replaced them, kept so those sections still read as
   * "a screen" rather than a bare inline image.
   */
  chromeLabel?: string
  /** Soft colour wash behind the frame. Matches each section's accent. */
  glowClassName?: string
  className?: string
}

export function ProductScreenshot({
  src,
  alt,
  caption,
  priority = false,
  chromeLabel,
  glowClassName,
  className,
}: ProductScreenshotProps) {
  const image = (
    <Image
      src={src}
      alt={alt}
      width={2880}
      height={1800}
      priority={priority}
      sizes="(min-width: 1024px) 960px, 100vw"
      className="h-auto w-full"
    />
  )

  return (
    <figure className={cn("flex flex-col gap-3", className)}>
      <div className="relative">
        {glowClassName ? (
          <div
            aria-hidden="true"
            className={cn("absolute -inset-4 rounded-3xl blur-2xl", glowClassName)}
          />
        ) : null}

        {chromeLabel ? (
          <div className="relative overflow-hidden rounded-xl border border-border bg-card shadow-2xl">
            <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-3">
              <div className="flex gap-1.5">
                <span className="h-3 w-3 rounded-full bg-red-400" />
                <span className="h-3 w-3 rounded-full bg-amber-400" />
                <span className="h-3 w-3 rounded-full bg-emerald-400" />
              </div>
              <div className="flex flex-1 justify-center">
                <div className="rounded-md bg-muted px-3 py-1 text-[10px] text-muted-foreground">
                  {chromeLabel}
                </div>
              </div>
            </div>
            {image}
          </div>
        ) : (
          <div className="relative overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
            {image}
          </div>
        )}
      </div>
      {caption ? (
        <figcaption className="text-[10px] uppercase tracking-wide text-amber-600">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  )
}
