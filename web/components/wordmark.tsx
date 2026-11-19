"use client";

import { useRef } from "react";

import { gsap, MOTION_OK } from "@/components/motion/gsap";

/** The SEXTANTE logo (docs/assets/logo.svg): the sextant on a dusk tile. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="sx-dusk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#b9687c" />
          <stop offset="1" stopColor="#3a1715" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="14" fill="url(#sx-dusk)" />
      <g transform="translate(8 9) scale(2)" fill="none" stroke="#fbf1ec" strokeLinecap="round">
        <path className="sx-arc" d="M4 18 A 11 11 0 0 1 20 18" strokeWidth="1.6" />
        <path d="M12 4 L4 18 M12 4 L20 18" strokeWidth="1.4" />
        <path className="sx-arm" d="M12 4 L15 18" stroke="#f7a24b" strokeWidth="1.6" />
        <circle cx="12" cy="4" r="1.8" fill="#fbf1ec" stroke="none" />
      </g>
    </svg>
  );
}

/** "sextante" with the logo standing in for the x; the arc redraws and the arm swings on hover. */
export function Wordmark({ className }: { className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const draw = () => {
    if (!window.matchMedia(MOTION_OK).matches) return;
    const q = gsap.utils.selector(ref);
    gsap.fromTo(q(".sx-arc"), { drawSVG: "50% 50%" }, { drawSVG: "0% 100%", duration: 0.8, ease: "power3.out" });
    gsap.fromTo(q(".sx-arm"), { rotate: -18, svgOrigin: "12 4" }, { rotate: 0, svgOrigin: "12 4", duration: 1.1, ease: "elastic.out(1, 0.45)" });
  };
  return (
    <span ref={ref} className={`wordmark ${className ?? ""}`} onMouseEnter={draw}>
      se<LogoMark className="wordmark-x" />tante
    </span>
  );
}
