"use client";

import { useRef } from "react";

import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from "@/components/motion/gsap";

// Re-mounted on every navigation: a dusk veil lifts off the new page.
export default function Template({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      gsap.timeline()
        .fromTo(q(".page-veil"), { scaleY: 1 }, { scaleY: 0, transformOrigin: "50% 0%", duration: 0.9, ease: "expo.inOut" })
        // Opacity only: a transform here would trap the fixed layers (intro, header, orb).
        .from(q(".page-body"), { opacity: 0, duration: 1, clearProps: "opacity" }, 0.25)
        .call(() => ScrollTrigger.refresh());
    });
  }, { scope: ref });
  return (
    <div ref={ref}>
      <div className="page-veil" aria-hidden="true" />
      <div className="page-body">{children}</div>
    </div>
  );
}
