import type { SVGProps } from "react";

export type PlayOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/** Source: Nucleo Sharp "media-play" (owner's licensed nucleoapp.com library). */
export function PlayOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: PlayOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M6 4V20L20 12L6 4Z" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
