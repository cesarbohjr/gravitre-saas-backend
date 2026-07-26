import { cn } from "@/lib/utils"
import { GravitreeLoader, type GravitreeLoaderSize } from "@/components/gravitre/gravitree-loader"

function Spinner({
  className,
  size = "sm",
  ...props
}: React.ComponentProps<"div"> & { size?: GravitreeLoaderSize }) {
  return (
    <div role="status" aria-label="Loading" className={cn("inline-flex shrink-0 items-center justify-center", className)} {...props}>
      <GravitreeLoader size={size} />
    </div>
  )
}

export { Spinner }
