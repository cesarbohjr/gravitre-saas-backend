import { RouteLoading } from "@/components/gravitre/route-loading"
import { GravitreeLoader } from "@/components/gravitre/gravitree-loader"

export default function Loading() {
  return (
    <div className="relative">
      <RouteLoading variant="dashboard" />
      <div className="pointer-events-none fixed inset-0 flex items-center justify-center">
        <GravitreeLoader size="lg" className="opacity-90" />
      </div>
    </div>
  )
}
