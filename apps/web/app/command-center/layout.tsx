import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Command Center | Gravitre",
  description:
    "Delegate tracked work to Gravitre — action plans, async jobs, context from runs and connectors, and explicit verification.",
  alternates: { canonical: "/command-center" },
}

export default function CommandCenterLayout({ children }: { children: React.ReactNode }) {
  return children
}
