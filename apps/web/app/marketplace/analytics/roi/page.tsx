import { redirect } from "next/navigation"
import { APP_ROUTES } from "@/lib/app-routes"

/** Parallel ROI window retired — Reports section is canonical. */
export default function MarketplaceRoiRedirectPage() {
  redirect(APP_ROUTES.intelligenceReports)
}
