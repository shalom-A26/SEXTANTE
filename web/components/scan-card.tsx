"use client";

import { useRef } from "react";

import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";

// Scanner: a CV being read; lines it "recognises" light up as the beam passes.
export function ScanCard() {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      const beam = gsap.timeline({ repeat: -1, repeatDelay: 0.4 });
      beam
        .fromTo(q(".scanline"), { top: "4%" }, { top: "94%", duration: 1.8, ease: "power1.inOut" })
        .to(q(".scanline"), { top: "4%", duration: 1.8, ease: "power1.inOut" });
      q(".doc span").forEach((line, i) => {
        const at = 0.15 + (i / 6) * 1.6;
        beam.fromTo(line, { scaleX: 0.92, transformOrigin: "0 50%" }, {
          scaleX: 1, duration: 0.4, ease: "back.out(3)",
          backgroundColor: line.classList.contains("hit") ? "#ffd3a6" : "rgba(251,241,236,0.5)",
          yoyo: true, repeat: 1,
        }, at);
      });
      gsap.to(q(".corner"), { scale: 1.25, duration: 1.1, yoyo: true, repeat: -1, ease: "sine.inOut", stagger: 0.2 });
    });
  }, { scope: ref });

  return (
    <div className="scan-card" ref={ref}>
      <span className="label">Leyendo tu CV…</span>
      <div className="scan-frame">
        <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
        <div className="doc" aria-hidden="true">
          <span style={{ width: "62%" }} /><span style={{ width: "88%" }} /><span className="hit" style={{ width: "40%" }} />
          <span style={{ width: "76%" }} /><span className="hit" style={{ width: "52%" }} /><span style={{ width: "68%" }} />
          <div className="scanline" />
        </div>
      </div>
    </div>
  );
}
