"use client"

import { useParams } from "next/navigation"
import { DepartmentWorkspace } from "@/components/marketplace/department-workspace"
import type { DepartmentWorkspace as Workspace } from "@/lib/marketplace3"
import fixtures from "../fixtures.json"

// The enclosing screenshot layout gates this route out of production.
export default function DepartmentShot() {
  const { slug } = useParams<{ slug: string }>()
  const workspace = (fixtures as unknown as Record<string, Workspace>)[slug]
  return <main className="mx-auto max-w-7xl p-4 sm:p-6"><p className="mb-4 text-sm text-muted-foreground">Screenshot fixture · no tenant data or live results</p>{workspace ? <DepartmentWorkspace workspace={workspace} preview /> : <p>Unknown department</p>}</main>
}
