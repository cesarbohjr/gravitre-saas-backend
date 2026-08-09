import { cn } from "@/lib/utils"
import { GravitreLoader, type GravitreLoaderSize } from "@/components/gravitre/gravitre-loader"

function Spinner({
  className,
  size = "sm",
  ...props
}: React.ComponentProps<"div"> & { size?: GravitreLoaderSize }) {
  return (
    <div role="status" aria-label="Loading" className={cn("inline-flex shrink-0 items-center justify-center", className)} {...props}>
      <GravitreLoader size={size} />
    </div>
  )
}

export { Spinner }
