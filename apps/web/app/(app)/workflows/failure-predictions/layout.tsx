import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Failure alerts | Gravitre",
  "Predicted workflow failures.",
  { canonical: "/workflows/failure-predictions" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
