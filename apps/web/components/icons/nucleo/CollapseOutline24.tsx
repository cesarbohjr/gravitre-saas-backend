import type { SVGProps } from "react";

export type CollapseOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/** Source: Nucleo Sharp "arrows-reduce-diagonal-2" (owner's licensed nucleoapp.com library). */
export function CollapseOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: CollapseOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M3.5 3.5L10 10L9.29289 9.29289" fill="none" stroke="currentColor" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M10 5L9.99988 9.99987L5 10" fill="none" stroke="currentColor" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M20.4998 20.4999L13.9998 13.9999L14.7069 14.707" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M13.9998 18.9999L13.9999 14L18.9998 13.9999" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
