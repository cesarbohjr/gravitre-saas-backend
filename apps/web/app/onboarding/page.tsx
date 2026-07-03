import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Legacy /onboarding route — unified into /welcome. */
export default function LegacyOnboardingRedirectPage() {
  redirect(APP_ROUTES.welcome)
}
