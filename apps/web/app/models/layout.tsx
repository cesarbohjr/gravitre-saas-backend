import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Model Registry | Gravitre",
  "Configure and manage ML models.",
  { canonical: "/models" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
