import { Metadata } from "next"
import { SURFACE_COPY } from "@/lib/surface-copy"

export const metadata: Metadata = {
  title: `${SURFACE_COPY.pages.predictive.title} | Gravitre Operator`,
  description: SURFACE_COPY.pages.predictive.description,
}

export default function PredictiveLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
