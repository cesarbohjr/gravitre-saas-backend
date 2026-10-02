"use client"
import Link from "next/link"
import { useParams } from "next/navigation"
import useSWR from "swr"
import { AppShell } from "@/components/gravitre/app-shell"
import { DepartmentWorkspace } from "@/components/marketplace/department-workspace"
import { Button } from "@/components/ui/button"
import { marketplace3Api } from "@/lib/marketplace3"
import { useAuth } from "@/lib/auth-context"
import { useWorkspaceIdentity } from "@/components/gravitre/workspace-switcher"

export default function DepartmentPage() {
  const { slug } = useParams<{ slug: string }>()
  const { user } = useAuth()
  const { orgId } = useWorkspaceIdentity()
  const { data, error, isLoading, mutate } = useSWR(user && orgId && slug ? ["marketplace3-workspace", user.id, orgId, slug] : null, () => marketplace3Api.workspace(slug), { revalidateOnFocus: false })
  return <AppShell title="Department workspace"><div className="mx-auto max-w-7xl space-y-5 p-4 sm:p-6"><div className="flex flex-wrap justify-between gap-2"><Button variant="ghost" size="sm" asChild><Link href="/marketplace/installed">← Installed packs</Link></Button><Button variant="outline" size="sm" onClick={() => void mutate()} disabled={isLoading}>Refresh evidence</Button></div>{isLoading ? <div role="status" className="rounded-xl border p-8">Loading department workspace…</div> : error ? <div role="alert" className="space-y-3 rounded-xl border p-8"><h1 className="text-lg font-semibold">Department workspace unavailable</h1><p className="text-sm text-muted-foreground">{error instanceof Error ? error.message : "An active install is required in the selected workspace."}</p><div className="flex flex-wrap gap-2"><Button onClick={() => void mutate()} variant="outline">Retry</Button><Button asChild><Link href="/marketplace/assets?type=outcome_pack">Browse department packs</Link></Button></div></div> : data ? <DepartmentWorkspace workspace={data} /> : null}</div></AppShell>
}
