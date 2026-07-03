import type { Metadata } from "next"
import { authenticatedMetadata } from "@/lib/authenticated-metadata"

export const metadata: Metadata = authenticatedMetadata(
  "Welcome to Gravitre",
  "Set up your AI operations platform in a few guided steps.",
)

export default function WelcomeLayout({ children }: { children: React.ReactNode }) {
  return children
}
