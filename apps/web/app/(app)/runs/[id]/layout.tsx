import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Run details | Gravitre",
  "Workflow run execution trace and status.",
  { canonical: "/runs" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
