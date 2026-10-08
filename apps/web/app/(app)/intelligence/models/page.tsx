import { redirect } from "next/navigation"

/** Built-in models are a section of the one Models page now; this route and /models/built-in land there. */
export default function IntelligenceModelsPage() {
  redirect("/models?tab=built-in")
}
