import { cn } from "@/lib/utils"

/**
 * Illustration tile from the Workspace designs, with an optional status chip
 * in the corner. The chip only states real data; it is not a control.
 */
export function WsArt({
  src,
  alt = "",
  status,
  tone = "green",
  className,
  style,
}: {
  src: string
  alt?: string
  status?: string | null
  tone?: "green" | "amber" | "red" | "grey"
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div className={cn("gv-art", className)} style={style}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={alt} />
      {status ? (
        <span className={cn("gv-live", tone !== "green" && tone)} role="status">
          <span className="gv-ldot" aria-hidden />
          {status}
        </span>
      ) : null}
    </div>
  )
}
