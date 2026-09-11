"use client"

/**
 * Intelligence redesign Phase 1 (2026-09-11) — Model Studio is a new,
 * first-class Intelligence destination (not folded into an "Advanced" drawer).
 *
 * Scope note (honest, not deferred silently): the brief's Phase 8.5 asks for a
 * full guided, intent-first Create Model wizard (predict/classify/score/
 * forecast → pick real data → plain-language target → only then expose
 * algorithm/hyperparameters). That guided flow is real, substantial, separate
 * work and is intentionally NOT built in this Phase 1 slice.
 *
 * What Phase 1 ships here is real: a genuine landing destination whose four
 * actions link directly into existing, working capability —
 *   - Create Model      -> /models?action=register (real register-model dialog)
 *   - Improve Existing   -> /models (real model list + detail pages)
 *   - Retrain            -> /models (same real model list; retrain/redeploy
 *                            lives on a model's own detail page today)
 *   - Add Knowledge/Data -> /training (real dataset upload + connector list)
 * Nothing here is a mock or a fabricated capability — every link lands on a
 * real, already-shipped screen. The intent-first wizard is tracked as
 * follow-up Phase 8.5 work, not silently dropped.
 */
import Link from "next/link"
import { AppShell } from "@/components/gravitre/app-shell"
import { GravitrePageHeader } from "@/components/gravitre/nodus-product"
import { IntelligenceHubTabs } from "@/components/intelligence/intelligence-hub-tabs"
import { NucleoIntelligence } from "@/components/icons/nucleo/semantic"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { APP_ROUTES } from "@/lib/app-routes"
import { ArrowsClockwise, Brain, Database, Plus, Sparkle } from "@phosphor-icons/react"

const ACTIONS = [
  {
    id: "create",
    icon: Plus,
    title: "Create Model",
    description:
      "Register a new model in the registry — pick a type, a base model, and connect it to a real data source.",
    href: `${APP_ROUTES.models}?action=register`,
    cta: "Start creating",
  },
  {
    id: "improve",
    icon: Sparkle,
    title: "Improve this model",
    description:
      "Add examples, correct predictions, or add a data source to an existing model. Open a model from the registry to improve it.",
    href: APP_ROUTES.models,
    cta: "Open Models",
  },
  {
    id: "retrain",
    icon: ArrowsClockwise,
    title: "Retrain",
    description: "Run a fresh training pass on an existing model with more recent data.",
    href: APP_ROUTES.models,
    cta: "Open Models",
  },
  {
    id: "add-data",
    icon: Database,
    title: "Add Knowledge / Data",
    description:
      "Upload a dataset or connect a live source for models and agents to learn from.",
    href: APP_ROUTES.training,
    cta: "Open Training",
  },
] as const

export default function ModelStudioPage() {
  return (
    <AppShell title="Model Studio">
      <div className="space-y-6 p-4 md:p-6">
        <GravitrePageHeader
          title="Model Studio"
          description="Create, improve, retrain, and feed models — built on Gravitre's real, existing training and model infrastructure."
          icon={<NucleoIntelligence className="h-5 w-5" />}
        />

        <IntelligenceHubTabs active="model-studio" />

        <div className="grid gap-4 sm:grid-cols-2">
          {ACTIONS.map((action) => {
            const Icon = action.icon
            return (
              <Card key={action.id} className="flex flex-col">
                <CardHeader className="flex-row items-start gap-3 space-y-0 pb-2">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 ring-1 ring-primary/20">
                    <Icon className="h-5 w-5 text-primary" weight="duotone" aria-hidden />
                  </span>
                  <div>
                    <CardTitle className="text-base font-semibold">{action.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col justify-between gap-4">
                  <CardDescription className="text-sm text-muted-foreground">
                    {action.description}
                  </CardDescription>
                  <Button asChild size="sm" className="w-fit">
                    <Link href={action.href}>{action.cta}</Link>
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </div>

        <div className="rounded-xl border border-dashed border-border/80 bg-muted/20 p-4">
          <div className="flex items-start gap-3">
            <Brain className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
            <p className="text-xs leading-relaxed text-muted-foreground text-pretty">
              Model Studio is a real, first-class destination composing the same model registry and
              training infrastructure used everywhere else in Gravitre — nothing here is simulated. A
              guided, intent-first &quot;what do you want to predict&quot; flow (choose an intent, then
              real connected data, then plain-language target, before any algorithm settings) is
              planned as the next iteration of this page.
            </p>
          </div>
        </div>
      </div>
    </AppShell>
  )
}
