import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Environments | Gravitre",
  "Manage deployment environments.",
  { canonical: "/environments" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
