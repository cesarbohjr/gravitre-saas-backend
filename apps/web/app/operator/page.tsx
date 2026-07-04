import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Legacy Command Center — canonical surface is Gravitre AI. */
export default function OperatorRedirectPage() {
  redirect(APP_ROUTES.gravitreAi)
}
