"use client";

import { useRef, useState } from "react";

import { GlowButton, HookArrow } from "@/components/glow-button";
import { STEPS } from "@/components/guide/steps";
import { gsap, MOTION_OK, SplitText, useGSAP } from "@/components/motion/gsap";

const ROW = 56; // px, must match .wwd-track li height

// Sticky block: the paragraph lights up word by word while the list of pipeline
// stages slides under a fixed "reading line"; the stage on it is the active one.
export function WhatWeDo() {
  const ref = useRef<HTMLElement>(null);
  const [active, setActive] = useState(0);

  useGSAP(() => {
    const q = gsap.utils.selector(ref);
    gsap.matchMedia().add(`${MOTION_OK} and (min-width: 961px)`, () => {
      const words = SplitText.create(q(".wwd-text .lit"), { type: "words" }).words;
      const tl = gsap.timeline({
        scrollTrigger: {
          trigger: ref.current, start: "top top", end: "bottom bottom", scrub: 0.6,
          onUpdate: (self) => setActive(Math.min(STEPS.length - 1, Math.round(self.progress * 1.25 * (STEPS.length - 1)))),
        },
      });
      tl.fromTo(words, { opacity: 0.18 }, { opacity: 1, stagger: 0.05, ease: "none", duration: 0.3 }, 0)
        .fromTo(q(".wwd-track"), { y: -ROW / 2 }, { y: -ROW / 2 - ROW * (STEPS.length - 1), ease: "none", duration: 0.8 }, 0)
        .from(q(".wwd-left .glow-btn"), { autoAlpha: 0, y: 20, duration: 0.1 }, 0.25);
    });
  }, { scope: ref });

  return (
    <section className="wwd paper" ref={ref}>
      <div className="wwd-stage">
        <div className="wwd-left">
          <p className="wwd-text">
            <span className="pill">Qué hacemos</span>
            <span className="indent"><HookArrow className="inline-arrow" /></span>
            <span className="lit">
              Leemos miles de vacantes colombianas y convertimos su texto en datos: qué habilidades piden, cuánto pagan, qué
              perfiles existen y dónde encaja el tuyo. Primero entendemos el porqué; luego medimos el resto.
            </span>
          </p>
          <GlowButton href="/dashboard">Ver el dashboard</GlowButton>
        </div>
        <div className="wwd-list" aria-label="Etapas del sistema">
          <ol className="wwd-track">
            {STEPS.map((s, i) => (
              <li key={s.key} className={i === active ? "on" : Math.abs(i - active) === 1 ? "near" : ""}>
                <a href="#como-funciona" onClick={() => window.dispatchEvent(new CustomEvent("guide:goto", { detail: i }))}>
                  <span className="idx"><span className="mono">({String(i + 1).padStart(3, "0")})</span><HookArrow /></span>
                  <strong>{s.title}</strong>
                </a>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
