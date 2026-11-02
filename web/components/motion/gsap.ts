"use client";

// Single place where GSAP plugins are registered (client only).
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { ScrollToPlugin } from "gsap/ScrollToPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";

gsap.registerPlugin(useGSAP, ScrollTrigger, ScrollToPlugin, SplitText, DrawSVGPlugin);
gsap.defaults({ ease: "expo.out", duration: 1 });
// Some animated pieces render conditionally (empty lists, loading states).
gsap.config({ nullTargetWarn: false });

// Animations only run for people who have not asked the OS to reduce motion;
// otherwise everything stays in its final, static state.
export const MOTION_OK = "(prefers-reduced-motion: no-preference)";
export const FINE_POINTER = "(prefers-reduced-motion: no-preference) and (pointer: fine)";

export { gsap, ScrollTrigger, SplitText, useGSAP };
