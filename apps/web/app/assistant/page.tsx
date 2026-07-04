import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Legacy workspace chat — canonical surface is Gravitre AI. */
export default function AssistantRedirectPage() {
  redirect(APP_ROUTES.gravitreAiChat)
}
