import type { SVGProps } from "react";

export type PanelToggleOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/** Source: Nucleo Sharp "layout-sidebar" (owner's licensed nucleoapp.com library). */
export function PanelToggleOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: PanelToggleOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M12 20L22 20L22 4L12 4" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M2 20L2 4L8 4L8 20L2 20Z" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
