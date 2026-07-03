import { cn } from "@/lib/utils"
import { Skeleton } from "@/components/ui/skeleton"

export type RouteLoadingVariant = "dashboard" | "table" | "detail" | "chat"

type RouteLoadingProps = {
  variant?: RouteLoadingVariant
  className?: string
}

function ShimmerBlock({ className }: { className?: string }) {
  return (
    <div className={cn("relative overflow-hidden rounded-lg bg-muted", className)}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-background/40 to-transparent animate-shimmer"
      />
    </div>
  )
}

export function RouteLoading({ variant = "dashboard", className }: RouteLoadingProps) {
  if (variant === "chat") {
    return (
      <div className={cn("flex h-[calc(100vh-4rem)]", className)}>
        <div className="hidden w-64 shrink-0 border-r border-border p-3 md:block">
          <Skeleton className="mb-3 h-9 w-full" />
          {Array.from({ length: 6 }).map((_, index) => (
            <ShimmerBlock key={index} className="mb-2 h-10 w-full" />
          ))}
        </div>
        <div className="flex flex-1 flex-col">
          <ShimmerBlock className="h-14 w-full rounded-none" />
          <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
            {Array.from({ length: 4 }).map((_, index) => (
              <ShimmerBlock
                key={index}
                className={cn("h-16 w-full max-w-xl", index % 2 === 1 ? "ml-auto max-w-md" : "")}
              />
            ))}
          </div>
          <ShimmerBlock className="mx-4 mb-4 h-12 rounded-xl md:mx-6" />
        </div>
      </div>
    )
  }

  if (variant === "detail") {
    return (
      <div className={cn("space-y-6 p-4 md:p-6", className)}>
        <Skeleton className="h-4 w-32" />
        <div className="grid gap-6 lg:grid-cols-12">
          <div className="space-y-4 lg:col-span-4">
            <ShimmerBlock className="mx-auto h-32 w-32 rounded-full" />
            <Skeleton className="mx-auto h-6 w-40" />
            <Skeleton className="mx-auto h-4 w-56" />
          </div>
          <div className="space-y-4 lg:col-span-8">
            <div className="grid gap-3 sm:grid-cols-3">
              {Array.from({ length: 6 }).map((_, index) => (
                <ShimmerBlock key={index} className="h-20 w-full" />
              ))}
            </div>
            <ShimmerBlock className="h-40 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (variant === "table") {
    return (
      <div className={cn("space-y-6 p-4 md:p-6", className)}>
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-full max-w-2xl" />
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <ShimmerBlock key={index} className="h-9 w-full sm:w-36" />
          ))}
        </div>
        <ShimmerBlock className="h-64 w-full rounded-2xl" />
      </div>
    )
  }

  return (
    <div className={cn("space-y-6 p-4 md:p-6", className)}>
      <Skeleton className="h-8 w-56" />
      <Skeleton className="h-4 w-full max-w-2xl" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <ShimmerBlock key={index} className="h-24 w-full rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <ShimmerBlock className="h-48 w-full rounded-2xl" />
        <ShimmerBlock className="h-48 w-full rounded-2xl" />
      </div>
    </div>
  )
}
