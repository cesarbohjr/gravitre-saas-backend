import { Badge } from "@/components/ui/badge"
import { ShieldCheck, Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

export function AssetTrustBadges({
  asset,
  className,
}: {
  asset: { featured?: boolean; verified?: boolean }
  className?: string
}) {
  if (!asset.featured && !asset.verified) return null
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {asset.featured ? (
        <Badge variant="secondary" className="gap-1 text-[11px]">
          <Sparkles className="h-3 w-3" aria-hidden />
          Featured
        </Badge>
      ) : null}
      {asset.verified ? (
        <Badge className="gap-1 bg-primary/10 text-[11px] text-primary hover:bg-primary/10">
          <ShieldCheck className="h-3 w-3" aria-hidden />
          Verified
        </Badge>
      ) : null}
    </div>
  )
}
