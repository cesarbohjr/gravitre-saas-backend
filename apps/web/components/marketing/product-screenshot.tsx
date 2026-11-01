import type React from "react"
import Image from "next/image"
import { cn } from "@/lib/utils"
import { AppWindow } from "@/components/marketing/nodus/app-window"

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
  /** Intrinsic size of the capture; defaults to the 2880x1800 web shots. */
  width?: number
  height?: number
  /** Live layer drawn over the capture, positioned in % of the image. */
  overlay?: React.ReactNode
  /** Set on the first shot above the fold only. */
  priority?: boolean
  /** Title pill in the macOS window outline every shot is framed in. */
  chromeLabel?: string
  /** Soft colour wash behind the frame. Matches each section's accent. */
  glowClassName?: string
  className?: string
}

export function ProductScreenshot({
  src,
  alt,
  caption,
  width = 2880,
  height = 1800,
  priority = false,
  overlay,
  chromeLabel,
  glowClassName,
  className,
}: ProductScreenshotProps) {
  const image = (
    <Image
      src={src}
      alt={alt}
      width={width}
      height={height}
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

        <AppWindow title={chromeLabel ?? "Gravitre"} className="relative">
          {overlay ? (
            <div className="relative">
              {image}
              {overlay}
            </div>
          ) : (
            image
          )}
        </AppWindow>
      </div>
      {caption ? (
        <figcaption className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  )
}
