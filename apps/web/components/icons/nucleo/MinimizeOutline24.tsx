import type { SVGProps } from "react";

export type MinimizeOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/**
 * Source: Nucleo Sharp "chevron-down" (owner's licensed nucleoapp.com library),
 * with a plain accent baseline added below it (a generic geometric stroke, not
 * a distinct Nucleo glyph) to keep the original "collapse into a dock" reading.
 */
export function MinimizeOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: MinimizeOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M3.5 8L12 16.5L20.5 8" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><line x1="6" y1="20" x2="18" y2="20" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line></svg>
  );
}
