import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Model | Gravitre",
  "Model configuration and metrics.",
  { canonical: "/models" },
)

export default function Layout({ children }: { children: React.ReactNode }) {
  return children
}
