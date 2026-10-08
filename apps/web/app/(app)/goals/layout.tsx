import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Goals | Gravitre",
  "Track goals and outcomes across your org.",
  { canonical: "/goals" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
