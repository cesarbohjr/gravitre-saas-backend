import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Intelligence Models | Gravitre Operator",
  description: "Manage and monitor machine learning models in Gravitre Operator.",
}

export default function ModelsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
