import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Workflow schedules | Gravitre",
  "Scheduled runs for this workflow.",
  { canonical: "/workflows" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
