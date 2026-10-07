import type { SVGProps } from "react"
import { cn } from "@/lib/utils"

const BAR =
  "M6 160C1 160-2 156 1 152L59 72C91 27 138 0 186 0H628C636 0 640 6 635 13L576 94C543 137 498 160 450 160Z"

/** Gravitre two-bar mark without the app-icon tile, drawn in the brand green. */
export function GravitreMark({
  className,
  title = "Gravitre",
  ...props
}: SVGProps<SVGSVGElement> & { title?: string }) {
  return (
    <svg
      viewBox="0 0 640 367"
      fill="currentColor"
      role="img"
      aria-label={title}
      className={cn("h-6 w-auto shrink-0 text-[color:var(--brand)]", className)}
      {...props}
    >
      <path d={BAR} />
      <path d={BAR} transform="translate(0 207)" />
    </svg>
  )
}
