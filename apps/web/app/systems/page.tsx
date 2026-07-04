import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Orphan route — connected systems live under Connectors. */
export default function SystemsRedirectPage() {
  redirect(APP_ROUTES.connectors)
}
