"use client";

import { useRef } from "react";

import { gsap, MOTION_OK } from "@/components/motion/gsap";

/** The sextant drawn as an "x": two crossed radii under a graduated arc, with the pivot in accent. */
export function SextantX({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 44" className={className} aria-hidden="true" fill="none" stroke="currentColor" strokeLinecap="round">
      <path className="sx-arc" d="M4 10 Q20 0 36 10" strokeWidth="2.2" />
      <path d="M8.6 8 L10 11.6 M14.2 5.6 L15 9.3 M20 4.8 L20 8.6 M25.8 5.6 L25 9.3 M31.4 8 L30 11.6" strokeWidth="1.6" />
      {/* Serif contrast, like Boska's own x: the thick stroke falls left to right. */}
      <path d="M8 15 L32 42" strokeWidth="6" />
      <path d="M32 15 L8 42" strokeWidth="2.2" />
      <circle cx="20" cy="28.5" r="3.4" fill="var(--sx-accent)" stroke="none" />
    </svg>
  );
}

/** "sextante" with the x replaced by the instrument; the arc redraws on hover. */
export function Wordmark({ className }: { className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const draw = () => {
    if (!window.matchMedia(MOTION_OK).matches) return;
    gsap.fromTo(ref.current!.querySelector(".sx-arc"), { drawSVG: "50% 50%" }, { drawSVG: "0% 100%", duration: 0.8, ease: "power3.out" });
  };
  return (
    <span ref={ref} className={`wordmark ${className ?? ""}`} onMouseEnter={draw}>
      se<SextantX className="wordmark-x" />tante
    </span>
  );
}
