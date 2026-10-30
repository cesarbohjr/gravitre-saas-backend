import { cn } from "@/lib/utils"

/**
 * The Nodus dot grid that sits behind the home page skeletons (How it works,
 * Native Tools, Benefits), faded out radially. Drop it as the first child of a
 * `relative` container so animated visuals elsewhere share the same backdrop.
 */
export function NodusDotField({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "pointer-events-none absolute inset-0 bg-[radial-gradient(var(--color-dots)_1px,transparent_1px)] mask-radial-from-10% [background-size:10px_10px]",
        className,
      )}
    />
  )
}
