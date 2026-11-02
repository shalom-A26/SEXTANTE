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
        .from(q(".page-body"), { y: 40, opacity: 0, duration: 1, clearProps: "transform,opacity" }, 0.25)
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
