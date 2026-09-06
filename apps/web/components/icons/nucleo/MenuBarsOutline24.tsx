import type { SVGProps } from "react";

export type MenuBarsOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

export function MenuBarsOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: MenuBarsOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><line x1="20" y1="5" x2="22" y2="5" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line><line x1="2" y1="5" x2="16" y2="5" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line><line x1="4" y1="12" x2="2" y2="12" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line><line x1="22" y1="12" x2="8" y2="12" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line><line x1="20" y1="19" x2="22" y2="19" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line><line x1="2" y1="19" x2="16" y2="19" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></line></svg>
  );
}
