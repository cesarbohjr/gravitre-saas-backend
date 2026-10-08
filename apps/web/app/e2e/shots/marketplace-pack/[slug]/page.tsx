import MarketplaceAssetDetailPage from "@/app/(app)/marketplace/assets/[slug]/page"

import { ShotAuthProvider } from "../../shot-auth"

/**
 * Pack detail for capture. The real page reads `slug` from useParams, so this
 * route keeps the same param name and the fixture catalog supplies the asset.
 */
export default function Page() {
  return (
    <ShotAuthProvider>
      <MarketplaceAssetDetailPage />
    </ShotAuthProvider>
  )
}
