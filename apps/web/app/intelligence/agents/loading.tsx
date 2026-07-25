import { AppShell } from "@/components/gravitre/app-shell"
import { RouteLoading } from "@/components/gravitre/route-loading"
import { SURFACE_COPY } from "@/lib/surface-copy"

export default function Loading() {
  return (
    <AppShell title={SURFACE_COPY.hubLinks.agents.title}>
      <RouteLoading label="Loading agents…" />
    </AppShell>
  )
}
