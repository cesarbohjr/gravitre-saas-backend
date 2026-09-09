import type { SVGProps } from "react";

export type ExpandOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

/** Source: Nucleo Sharp "arrows-expand" (owner's licensed nucleoapp.com library). */
export function ExpandOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: ExpandOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M17 17L7.00002 7" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} data-color="color-2" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M2.99989 10.0001L3.96265 10L9.99989 4.02411L9.99989 3.00006L2.99985 3.00012L2.99989 10.0001Z" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path><path d="M21.0001 14.0002L20.0001 14.0002L14.0001 20.0001L14.0001 21.0002L21.0002 21.0001L21.0001 14.0002Z" fill="none" stroke="currentColor" strokeMiterlimit="10" strokeWidth={strokeWidth} strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
