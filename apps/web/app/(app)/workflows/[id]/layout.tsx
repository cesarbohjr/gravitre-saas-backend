import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Workflow | Gravitre",
  "Workflow definition and run history.",
  { canonical: "/workflows" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
