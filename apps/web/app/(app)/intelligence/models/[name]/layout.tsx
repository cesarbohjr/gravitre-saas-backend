import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Model Profile | Gravitre Operator",
  description: "View model performance, training readiness, and business impact.",
}

export default function ModelProfileLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
