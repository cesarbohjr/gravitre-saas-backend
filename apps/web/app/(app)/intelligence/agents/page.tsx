import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Agent intelligence roster deleted — use Agents hub. */
export default function IntelligenceAgentsRedirectPage() {
  redirect(APP_ROUTES.agents)
}
