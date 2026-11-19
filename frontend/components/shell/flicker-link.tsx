"use client";

import Link from "next/link";
import { useRef } from "react";

import { gsap, MOTION_OK } from "@/components/motion/gsap";

/** Nav link whose letters flicker like a bad neon when hovered. */
export function FlickerLink({ href, children }: { href: string; children: string }) {
  const ref = useRef<HTMLAnchorElement>(null);
  const flicker = () => {
    if (!window.matchMedia(MOTION_OK).matches) return;
    const letters = ref.current!.querySelectorAll("span");
    gsap.killTweensOf(letters);
    letters.forEach((letter) => {
      gsap.timeline()
        .to(letter, { opacity: 0.15, duration: 0.04, delay: Math.random() * 0.18 })
        .to(letter, { opacity: 1, duration: 0.04 })
        .to(letter, { opacity: 0.3, duration: 0.03, delay: Math.random() * 0.12 })
        .to(letter, { opacity: 1, duration: 0.05 });
    });
  };
  return (
    <Link href={href} ref={ref} className="flicker mono" aria-label={children} onMouseEnter={flicker} onFocus={flicker}>
      {[...children].map((c, i) => <span key={i} aria-hidden="true">{c}</span>)}
    </Link>
  );
}
