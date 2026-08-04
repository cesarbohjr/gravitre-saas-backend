import { Sidebar } from "@/components/gravitre/sidebar"
import { SidebarNavLink } from "@/components/gravitre/sidebar-nav-link"
import { SIDEBAR_SECTION_COLORS } from "@/components/gravitre/sidebar-nav-config"

/**
 * TEMPORARY visual-review harness for the app shell retheme.
 * Delete once the sidebar accent pass has been reviewed.
 */
export default async function PreviewShellPage({
  searchParams,
}: {
  searchParams: Promise<{ expanded?: string }>
}) {
  const params = await searchParams
  const expanded = params.expanded !== "0"

  return (
    <div className="flex h-screen bg-background">
      <Sidebar navExpanded={expanded} />
      <main className="flex-1 p-6">
        <h1 className="text-lg font-semibold text-foreground">Shell preview</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {expanded ? "Expanded rail" : "Collapsed rail"}
        </p>

        <div className="mt-6 max-w-60 rounded-lg border border-sidebar-border bg-sidebar p-2">
          <p className="px-2 pb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            Active vs inactive
          </p>
          <SidebarNavLink
            href="#"
            name="Activity"
            icon="checkCircle"
            isActive
            colors={SIDEBAR_SECTION_COLORS.ACTIVITY}
          />
          <SidebarNavLink
            href="#"
            name="Intelligence"
            icon="sparkles"
            isActive
            badge="Explain"
            colors={SIDEBAR_SECTION_COLORS.INSIGHTS}
          />
          <SidebarNavLink
            href="#"
            name="Schedules"
            icon="calendar"
            isActive={false}
            colors={SIDEBAR_SECTION_COLORS.ACTIVITY}
          />
          <SidebarNavLink
            href="#"
            name="Approvals"
            icon="clipboardCheck"
            isActive={false}
            badge="3"
            colors={SIDEBAR_SECTION_COLORS.ACTIVITY}
          />
        </div>
      </main>
    </div>
  )
}
