"use client"

import { AppShell } from "@/components/gravitre/app-shell"
import { RelationshipsWorkspace } from "@/components/intelligence/relationships/relationships-workspace"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { ShotAuthProvider } from "../shot-auth"

/** Inline snapshot — list data comes from SHOT_FIXTURES fetch intercept. */
const SHOT_SNAPSHOT = {
  queryVolume: { totalLogged: 42, distinctNormalized: 38, failedSearchCount: 2 },
  recentFailedSearches: [] as Array<Record<string, unknown>>,
  clusters: [] as Array<Record<string, unknown>>,
  glossary: [
    { id: "term_northwind", term: "Northwind Logistics" },
    { id: "term_revops", term: "RevOps playbook" },
  ],
  knowledgeGaps: [] as Array<Record<string, unknown>>,
  entityRelationships: [] as Array<Record<string, unknown>>,
}

export default function RelationshipsShotPage() {
  const copy = SURFACE_COPY.learning
  return (
    <ShotAuthProvider>
      <AppShell title={copy.title}>
        <div className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
          <RelationshipsWorkspace data={SHOT_SNAPSHOT} isLoading={false} enabled />
        </div>
      </AppShell>
    </ShotAuthProvider>
  )
}
