"use client"

import Link from "next/link"
import { APP_ROUTES } from "@/lib/app-routes"
import { SURFACE_COPY } from "@/lib/surface-copy"
import { TRAINING_STEPS } from "@/lib/training-ui-copy"
import { TYPE } from "@/lib/design-system"
import { cn } from "@/lib/utils"

type TrainingOverviewProps = {
  totalDatasets: number
  readyDatasets: number
  totalJobs: number
  activeJobs: number
  totalInstructions: number
}

export function TrainingOverview({
  totalDatasets,
  readyDatasets,
  totalJobs,
  activeJobs,
  totalInstructions,
}: TrainingOverviewProps) {
  return (
    <section className="space-y-4 border-b border-divide pb-6">
      <div>
        <p className={TYPE.eyebrow}>{SURFACE_COPY.training.badge}</p>
        <h2 className={cn(TYPE.sectionTitle, "mt-1")}>{SURFACE_COPY.training.heroTitle}</h2>
        <p className={cn(TYPE.bodyMuted, "mt-1 max-w-2xl")}>
          Teach agents with examples, documents, and live feedback. Run a training job, then assign the model.
          Starts from what{" "}
          <Link href={APP_ROUTES.learning} className="underline-offset-4 hover:underline">
            {SURFACE_COPY.learning.title}
          </Link>{" "}
          already detected. Finished models also appear in{" "}
          <Link href={APP_ROUTES.models} className="underline-offset-4 hover:underline">
            {SURFACE_COPY.models.title}
          </Link>
          .
        </p>
        <p className={cn(TYPE.meta, "mt-2")}>
          {totalDatasets} datasets · {readyDatasets} ready ·{" "}
          {activeJobs > 0 ? `${activeJobs} active jobs` : `${totalJobs} jobs`} · {totalInstructions}{" "}
          instructions
        </p>
      </div>
      <ol className="space-y-2">
        {TRAINING_STEPS.map((item) => (
          <li key={item.step} className="text-sm">
            <span className="font-medium text-foreground">
              {item.step}. {item.title}.
            </span>{" "}
            <span className="text-muted-foreground">{item.body}</span>
          </li>
        ))}
      </ol>
    </section>
  )
}
