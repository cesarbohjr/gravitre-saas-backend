import Image from "next/image"
import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

/**
 * Animated image card from the Gravitre illustration library ("Editorial with
 * texture"): a grained scene on the dotted gradient backdrop that animates
 * itself (the SVG carries its own keyframes and stops under Reduce Motion), an
 * optional status pill in the corner, and the card's copy underneath. Wide
 * scenes pass `aspect` (e.g. "aspect-[32/11]") so nothing is cropped. Used
 * for page-header cards on marketing pages.
 */
export function ArtCard({
  src,
  alt,
  status,
  aspect = "aspect-[4/3]",
  children,
  className,
}: {
  src: string
  alt: string
  status?: string
  aspect?: string
  children?: ReactNode
  className?: string
}) {
  return (
    <figure
      className={cn(
        "border-divide group relative m-0 flex flex-col overflow-hidden rounded-3xl border bg-[color:var(--g-marketing-surface)]",
        "transition-[translate,box-shadow] duration-300 ease-out hover:-translate-y-0.5 hover:shadow-[0_14px_30px_-18px_rgba(20,22,21,0.35)] motion-reduce:transition-none motion-reduce:hover:translate-y-0",
        className,
      )}
    >
      <div className={cn("border-divide relative overflow-hidden border-b bg-[#ebdfc8]", aspect)}>
        {status ? (
          <span className="absolute top-3 right-3 z-10 inline-flex items-center gap-1.5 rounded-full border border-[#e4e4df] bg-white/90 px-2.5 py-1 text-[11px] font-medium text-[#3e3f39]">
            <span aria-hidden className="size-[7px] rounded-full bg-[#19c37d]" />
            {status}
          </span>
        ) : null}
        <Image
          unoptimized
          priority
          src={src}
          alt={alt}
          fill
          sizes="(min-width: 768px) 50vw, 100vw"
          className="object-cover transition-transform duration-700 ease-out group-hover:scale-[1.025] motion-reduce:transition-none motion-reduce:group-hover:scale-100"
        />
      </div>
      {children ? <figcaption className="p-8 md:p-10">{children}</figcaption> : null}
    </figure>
  )
}
