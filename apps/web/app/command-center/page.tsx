import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Legacy route — Command Center merged into Gravitre AI. */
export default function CommandCenterRedirectPage() {
  redirect(APP_ROUTES.gravitreAi)
}
