import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Retired top-level Outcomes — Activity hub is canonical. */
export default function OutcomesRedirectPage() {
  redirect(APP_ROUTES.activity)
}
