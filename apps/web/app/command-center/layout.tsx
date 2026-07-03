import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Command Center | Gravitre",
  "Delegate tracked work to Gravitre — action plans, async jobs, context from runs and connectors, and explicit verification.",
  { canonical: "/ai" },
)

export default function CommandCenterLayout({ children }: { children: React.ReactNode }) {
  return children
}
