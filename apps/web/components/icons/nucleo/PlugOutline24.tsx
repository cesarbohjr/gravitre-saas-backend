import type { SVGProps } from "react";

export type PlugOutline24Props = SVGProps<SVGSVGElement> & {
  strokeWidth?: number | string;
  corners?: "round" | "square";
};

export function PlugOutline24({
  strokeWidth = 2,
  corners = "square",
  ...props
}: PlugOutline24Props) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={24} height={24} viewBox="0 0 24 24" {...props}><path d="M12 20V23" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" data-color="color-2" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M4 6V10.6667C4.00137 12.1131 4.4636 13.5237 5.32314 14.7043C6.18267 15.885 7.3973 16.7777 8.8 17.2599V20H15.2V17.2599C16.6027 16.7777 17.8173 15.885 18.6769 14.7043C19.5364 13.5237 19.9986 12.1131 20 10.6667V6" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M2 6H22" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M16 1V6" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path> <path d="M8 1V6" stroke="currentColor" strokeWidth={strokeWidth} strokeMiterlimit="10" fill="none" strokeLinejoin={corners === "round" ? "round" : "miter"} strokeLinecap={corners === "round" ? "round" : "square"}></path></svg>
  );
}
