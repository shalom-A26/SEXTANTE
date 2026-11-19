"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Wordmark } from "@/components/wordmark";
import { GlowButton } from "@/components/glow-button";
import { gsap } from "@/components/motion/gsap";
import { worldState } from "@/components/world/state";
import { setSound } from "@/lib/ambient";

// Entry gate (once per session): logo, tagline, load progress, and the choice to
// enter with the ambient sound. The click also unlocks Web Audio.
export function Intro() {
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem("sx-intro")) return;
    setOpen(true);
    document.documentElement.dataset.intro = "open";
    document.documentElement.style.overflow = "hidden";
    const done = () => setReady(true);
    if (worldState.ready) done();
    window.addEventListener("world-ready", done);
    // Reduced motion / no WebGL never fires world-ready: don't block the door.
    const fallback = window.setTimeout(done, 2500);
    return () => {
      window.removeEventListener("world-ready", done);
      window.clearTimeout(fallback);
    };
  }, []);

  useEffect(() => {
    if (open) gsap.to(".intro-progress i", { scaleX: ready ? 1 : 0.7, duration: ready ? 0.5 : 2.5, ease: "power2.out" });
  }, [open, ready]);

  const enter = (withSound: boolean) => {
    if (withSound) setSound(true);
    sessionStorage.setItem("sx-intro", "1");
    gsap.to(ref.current, {
      clipPath: "inset(0 0 100% 0)", duration: 1.1, ease: "expo.inOut",
      onComplete: () => {
        setOpen(false);
        document.documentElement.style.overflow = "";
        delete document.documentElement.dataset.intro;
        window.dispatchEvent(new Event("intro-done"));
      },
    });
  };

  if (!open) return null;
  // Portaled so no ancestor stacking context (page transition) can sit above it.
  return createPortal(
    <div className="intro" ref={ref} style={{ clipPath: "inset(0 0 0 0)" }} role="dialog" aria-label="Bienvenida">
      <div className="intro-center">
        <span className="brand"><Wordmark /></span>
        <p className="mono">El mercado laboral colombiano,<br />leído desde el texto de sus vacantes</p>
        <span className="intro-progress" aria-hidden="true"><i style={{ transform: "scaleX(0)" }} /></span>
      </div>
      <div className="intro-actions">
        <GlowButton size="lg" onClick={() => enter(true)} disabled={!ready}>Entrar con sonido</GlowButton>
        <button type="button" className="u-link" onClick={() => enter(false)} disabled={!ready}>
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6">
            <path d="M4 9h4l5-4v14l-5-4H4z" /><path d="M17 9l5 6M22 9l-5 6" />
          </svg>
          Entrar sin sonido
        </button>
      </div>
    </div>,
    document.body,
  );
}
