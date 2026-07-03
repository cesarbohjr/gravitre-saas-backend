import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Metrics | Gravitre",
  "Operational metrics and performance dashboards.",
  { canonical: "/metrics" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
