import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Agent intelligence detail merged into Agents profile. */
export default async function IntelligenceAgentDetailRedirectPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  redirect(`${APP_ROUTES.agents}/${id}`)
}
