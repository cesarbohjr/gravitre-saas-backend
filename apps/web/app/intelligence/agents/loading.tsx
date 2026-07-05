import { AppShell } from "@/components/gravitre/app-shell"
import { Skeleton } from "@/components/ui/skeleton"
import { SURFACE_COPY } from "@/lib/surface-copy"

export default function Loading() {
  return (
    <AppShell title={SURFACE_COPY.hubLinks.agents.title}>
      <div className="space-y-6 p-4 md:p-6">
        <Skeleton className="h-6 w-1/3" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      </div>
    </AppShell>
  )
}
