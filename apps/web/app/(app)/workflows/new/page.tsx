import { redirect } from "next/navigation"

type SearchParams = Record<string, string | string[] | undefined>

export default async function NewWorkflowRedirectPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>
}) {
  const params = await searchParams
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "string") qs.set(key, value)
    else if (Array.isArray(value) && value[0]) qs.set(key, value[0])
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : ""
  redirect(`/workflows/new/builder${suffix}`)
}
