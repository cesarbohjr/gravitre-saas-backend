import Image from "next/image"
import { Lock, Puzzle } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Browser chrome mockup for the *extension* captures in /public/product.
 *
 * Why this exists separately from <ProductScreenshot />: that component
 * hardcodes width={2880} height={1800} because every webapp shot comes out of
 * the capture script at that size. The extension captures are narrow portrait
 * panels (720x714 popup, 760x2358 approval), so rendering them through the
 * webapp component stretches a phone-shaped panel across a 16:10 frame — which
 * is exactly why the extension page looked wrong.
 *
 * Here the panel keeps its natural aspect ratio and is composited into browser
 * chrome the way it actually appears: a popup hanging off the toolbar
 * extensions icon, or an overlay pinned to the right edge of the page. Tall
 * panels are top-aligned and clipped by the viewport, which is also what you
 * see in a real browser window.
 *
 * `caption` is optional; the page behind the panel is a neutral placeholder.
 */

/** "popup" hangs off the toolbar icon; "overlay" pins to the page's right edge. */
type PanelPlacement = "popup" | "overlay"

export interface BrowserFrameProps {
  /** Path shown in the address bar. Rendered as text, never linked. */
  url: string
  /** Tab label. */
  tabTitle: string
  panel: {
    /** Path under /public, e.g. "/product/extension-popup.png". */
    src: string
    /** Describe the panel state shown, not just "the extension". */
    alt: string
    /** Natural pixel width of the capture. */
    width: number
    /** Natural pixel height of the capture. */
    height: number
  }
  placement?: PanelPlacement
  /**
   * Which end of a tall overlay panel to keep in view when it overflows the
   * viewport. "bottom" is the equivalent of having scrolled the panel down —
   * use it when the payload is the confirm/CTA block at the end. Ignored for
   * "popup", which always fits whole.
   */
  panelAlign?: "top" | "bottom"
  /** Optional provenance note under the frame. */
  caption?: string
  priority?: boolean
  className?: string
}

/**
 * Neutral stand-in for the underlying web page. Deliberately abstract bars
 * rather than a mocked-up LinkedIn profile: inventing a plausible person's
 * name, headline, and employer would be fabricated product evidence, and the
 * panel is the subject here anyway.
 */
function PagePlaceholder() {
  return (
    <div aria-hidden="true" className="h-full w-full bg-muted/50 select-none">
      <div className="h-[22%] w-full bg-gradient-to-r from-muted via-muted to-muted" />
      <div className="px-[6%]">
        <div className="-mt-[7%] h-[14%] w-[14%] rounded-full border-4 border-white bg-muted" />
        <div className="mt-[3%] flex flex-col gap-2">
          <div className="h-3 w-[38%] rounded-full bg-muted" />
          <div className="h-2 w-[52%] rounded-full bg-muted" />
          <div className="h-2 w-[26%] rounded-full bg-muted" />
        </div>
        <div className="mt-[5%] flex flex-col gap-3 pb-[6%]">
          <div className="rounded-lg border border-border bg-card p-[3%]">
            <div className="h-2 w-[30%] rounded-full bg-muted" />
            <div className="mt-2 h-2 w-[74%] rounded-full bg-muted" />
            <div className="mt-2 h-2 w-[62%] rounded-full bg-muted" />
          </div>
          <div className="rounded-lg border border-border bg-card p-[3%]">
            <div className="h-2 w-[24%] rounded-full bg-muted" />
            <div className="mt-2 h-2 w-[68%] rounded-full bg-muted" />
            <div className="mt-2 h-2 w-[55%] rounded-full bg-muted" />
          </div>
          <div className="rounded-lg border border-border bg-card p-[3%]">
            <div className="h-2 w-[34%] rounded-full bg-muted" />
            <div className="mt-2 h-2 w-[70%] rounded-full bg-muted" />
            <div className="mt-2 h-2 w-[46%] rounded-full bg-muted" />
          </div>
        </div>
      </div>
    </div>
  )
}

export function BrowserFrame({
  url,
  tabTitle,
  panel,
  placement = "overlay",
  panelAlign = "top",
  caption,
  priority = false,
  className,
}: BrowserFrameProps) {
  return (
    <figure className={cn("flex flex-col gap-3", className)}>
      <div className="overflow-hidden rounded-2xl border border-border bg-muted shadow-xl shadow-foreground/5">
        {/* Tab strip */}
        <div className="flex items-end gap-2 px-3 pt-3">
          <div className="flex items-center gap-1.5 pb-2.5 pr-1">
            <span className="h-2.5 w-2.5 rounded-full bg-muted" />
            <span className="h-2.5 w-2.5 rounded-full bg-muted" />
            <span className="h-2.5 w-2.5 rounded-full bg-muted" />
          </div>
          <div className="flex min-w-0 max-w-[240px] flex-1 items-center gap-2 rounded-t-lg bg-card px-3 py-2">
            <span className="h-3 w-3 shrink-0 rounded-sm bg-muted" />
            <span className="truncate text-[11px] font-medium text-muted-foreground">
              {tabTitle}
            </span>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 bg-card px-3 py-2">
          <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full bg-muted px-3 py-1.5">
            <Lock className="h-3 w-3 shrink-0 text-muted-foreground" />
            <span className="truncate text-[11px] text-muted-foreground">{url}</span>
          </div>
          {/* Anchor for the popup: this is the extensions button a real popup
              drops out of. */}
          <div
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
              placement === "popup"
                ? "bg-primary/15 ring-2 ring-primary"
                : "bg-muted",
            )}
          >
            <Puzzle
              className={cn(
                "h-3.5 w-3.5",
                placement === "popup" ? "text-primary" : "text-muted-foreground",
              )}
            />
          </div>
        </div>

        {/* Viewport. A popup is short, so a 16:10 stage leaves dead space
            under it; the tall overlay panels want the extra height.
            Narrow screens get a taller stage on purpose: the panel is a bigger
            share of a small frame, so a landscape stage would only reveal a
            sliver of it and a bottom-anchored panel would scroll clean past
            the confirm block. */}
        <div
          className={cn(
            "relative w-full overflow-hidden bg-card",
            placement === "popup"
              ? "aspect-square sm:aspect-[16/8]"
              : // lg is where these frames often sit two-up in a grid, so the
                // stage narrows; a taller ratio keeps enough of the panel in
                // view that a bottom anchor still includes its heading.
                "aspect-[3/4] sm:aspect-[16/10] lg:aspect-[16/13]",
          )}
        >
          <PagePlaceholder />
          {/* Fades the placeholder back so the real capture carries the eye. */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-l from-foreground/10 via-transparent to-transparent" />

          <div
            className={cn(
              "absolute overflow-hidden rounded-xl border border-border bg-card shadow-2xl shadow-foreground/25",
              // Width is deliberately a large fraction of the frame and
              // larger still on small screens. These captures are 720-760px
              // wide natively, so a narrow render shrinks the UI text past
              // readability and the proof degrades into decoration.
              placement === "popup"
                ? // Hangs from the toolbar, like a real popup.
                  "right-2 top-0 w-[68%] sm:w-[46%] max-w-[290px]"
                : // Pinned to the page's right edge, clipped by the viewport.
                  "bottom-0 right-3 top-3 w-[70%] sm:w-[58%] max-w-[300px]",
            )}
          >
            {/* Inner absolute wrapper is what lets a taller-than-viewport
                panel be anchored to either end. The image always keeps its
                natural aspect ratio; only the clipped end changes. */}
            <div
              className={cn(
                placement === "popup"
                  ? // Stays in flow: the popup container has no fixed height,
                    // so the image is what gives it one.
                    "relative"
                  : cn(
                      "absolute inset-x-0",
                      panelAlign === "bottom" ? "bottom-0" : "top-0",
                    ),
              )}
            >
              <Image
                src={panel.src}
                alt={panel.alt}
                width={panel.width}
                height={panel.height}
                priority={priority}
                sizes="(min-width: 640px) 300px, 70vw"
                className="h-auto w-full"
              />
            </div>
          </div>
        </div>
      </div>
      {caption ? (
        <figcaption className="text-[10px] uppercase tracking-wide text-amber-600">
          {caption}
        </figcaption>
      ) : null}
    </figure>
  )
}
