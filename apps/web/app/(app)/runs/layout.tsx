import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Runs | Gravitre",
  "Workflow and agent run history.",
  { canonical: "/runs" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
