import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Legacy route — canonical URL is `/multi-agent-run` (see next.config redirects). */
export default function LegacyAgentSwarmRedirect() {
  redirect(APP_ROUTES.multiAgentRun)
}
