"use client"

import { Suspense } from "react"
import { AppShell } from "@/components/gravitre/app-shell"
import { NewAssignmentPageContent } from "@/components/assignments/assignment-create-workspace"

export default function NewAssignmentPage() {
  return (
    <Suspense
      fallback={
        <AppShell title="New assignment">
          <p className="p-6 text-sm text-muted-foreground">
            Loading assignment creation…
          </p>
        </AppShell>
      }
    >
      <NewAssignmentPageContent />
    </Suspense>
  )
}
