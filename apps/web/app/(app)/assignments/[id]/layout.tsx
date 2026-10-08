import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Assignment | Gravitre",
  "Assignment details and deliverables.",
  { canonical: "/assignments" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
