"use client"

import { PAGE_FRAME } from "@/lib/design-system"
import { AppShell } from "@/components/gravitre/app-shell"
import { EmptyState } from "@/components/gravitre/empty-state"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceShell } from "@/components/intelligence/shell"
import { ModelStudioStage } from "@/components/intelligence/pages/model-studio-stage"
import { AskGravitreSummonButton } from "@/components/intelligence/ask-gravitre-summon-button"
import { useAuth } from "@/lib/auth-context"

export default function ModelStudioPage() {
  const { user } = useAuth()

  if (!user) {
    return (
      <AppShell title="Model Studio">
        <EmptyState title="Sign in required" description="Log in to create and train models." />
      </AppShell>
    )
  }

  return (
    <AppShell title="Model Studio">
      <div className={PAGE_FRAME}>
        <GravitrePageHeader
          title="Model Studio"
          description="Create, train, evaluate, and deploy models for your business, and review every run."
          actions={<AskGravitreSummonButton />}
        />
        <IntelligenceShell activeTab="model-studio" loadState="READY">
          <ModelStudioStage enabled={Boolean(user)} />
        </IntelligenceShell>
      </div>
    </AppShell>
  )
}
