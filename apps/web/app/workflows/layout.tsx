import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Workflows | Gravitre",
  "Build, monitor, and run automations.",
  { canonical: "/workflows" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
