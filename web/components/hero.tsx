"use client";

import Link from "next/link";
import { useRef } from "react";

import { DuskField, GlowFigure, SextantScale } from "@/components/field";
import { ScanCard, SkillsCard } from "@/components/hero-cards";
import { Magnetic } from "@/components/motion";
import { FINE_POINTER, gsap, MOTION_OK, SplitText, useGSAP } from "@/components/motion/gsap";

// Wind amplitude (skew degrees) per depth layer: far blades barely move.
const WIND = [1.2, 2.2, 3.6, 5.5];

export function Hero() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(() => {
    const mm = gsap.matchMedia();

    mm.add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      const split = SplitText.create(q("h1"), { type: "words", mask: "words" });

      // One orchestrated entrance: dusk settles, the field grows, the instrument draws itself.
      const intro = gsap.timeline({ defaults: { ease: "expo.out" } });
      intro
        .from(q(".dusk-shade"), { opacity: 0.75, duration: 2.2, ease: "sine.out" }, 0)
        .from(q(".sun"), { y: 160, scale: 0.6, transformOrigin: "50% 100%", opacity: 0, duration: 2.4 }, 0)
        .from(q(".blades"), {
          y: 50, opacity: 0, duration: 1.6, stagger: 0.14, ease: "power3.out",
        }, 0.2)
        .from(split.words, { yPercent: 120, rotate: 4, duration: 1.3, stagger: 0.08 }, 0.35)
        .from(q(".scale-ring"), { drawSVG: "50% 50%", duration: 1.8, ease: "power2.inOut" }, 0.5)
        .from(q(".ticks line"), {
          opacity: 0, scale: 0, transformOrigin: "50% 100%", duration: 0.5,
          stagger: { each: 0.01, from: "center" },
        }, 0.7)
        .from(q(".needle"), { rotate: -70, svgOrigin: "500 520", opacity: 0, duration: 1.8 }, 0.9)
        .from(q(".figure"), { y: 40, opacity: 0, filter: "brightness(0.2)", duration: 1.6 }, 1.0)
        .from(q(".halo"), { scale: 0.3, opacity: 0, duration: 2 }, 1.1)
        .from(q(".marker"), { y: 16, opacity: 0, stagger: 0.12, duration: 1 }, 1.4)
        .from(q(".cta-wrap .cta"), { y: 30, scale: 0.85, opacity: 0, duration: 1.1, ease: "back.out(2.2)" }, 1.55)
        .from(q(".hero-side .glass-card"), {
          x: (i) => (i ? 60 : -60), opacity: 0, filter: "blur(10px)", duration: 1.4, stagger: 0.15,
        }, 1.5);

      // Alive afterwards: wind through the grass, a breathing halo, a drifting needle.
      q(".blades").forEach((layer) => {
        const amp = WIND[Number(layer.getAttribute("data-layer")) || 0];
        layer.querySelectorAll(".blade").forEach((blade, i) => {
          gsap.fromTo(blade, { skewX: -amp * 0.4 }, {
            skewX: amp, transformOrigin: "50% 100%", duration: gsap.utils.random(2.2, 3.4),
            ease: "sine.inOut", yoyo: true, repeat: -1, delay: i * 0.18 + gsap.utils.random(0, 0.4),
          });
        });
      });
      gsap.to(q(".halo"), { scale: 1.08, opacity: 0.7, duration: 3, ease: "sine.inOut", yoyo: true, repeat: -1, delay: 3 });
      gsap.to(q(".needle"), {
        rotate: 22, svgOrigin: "500 520", duration: 7, ease: "sine.inOut", yoyo: true, repeat: -1, delay: 2.8,
      });
      gsap.to(q(".marker i"), { scale: 1.6, opacity: 0.6, duration: 1.4, yoyo: true, repeat: -1, ease: "sine.inOut", stagger: 0.7 });

      // Scrolling away: the scene sinks slower than the page, the title lifts and fades.
      const scroll = { trigger: ref.current, start: "top top", end: "bottom top", scrub: 0.6 };
      gsap.to(q(".field"), { yPercent: 18, ease: "none", scrollTrigger: scroll });
      gsap.to(q(".hero-center h1"), { y: -90, opacity: 0, ease: "none", scrollTrigger: { ...scroll, end: "60% top" } });
      gsap.to(q(".horizon-stage"), { y: -40, ease: "none", scrollTrigger: scroll });
      gsap.to(q(".hero-side"), { y: -120, opacity: 0, ease: "none", scrollTrigger: { ...scroll, end: "70% top" } });
    });

    // Depth with the mouse: each layer follows the pointer by a different amount.
    mm.add(FINE_POINTER, () => {
      const q = gsap.utils.selector(ref);
      const layers = [
        [q(".field"), 10], [q(".scale-wrap"), 18], [q(".figure-wrap"), 26], [q(".side-float"), -22],
      ] as const;
      const movers = layers.map(([el, depth]) => ({
        x: gsap.quickTo(el, "x", { duration: 1.2, ease: "power3.out" }),
        y: gsap.quickTo(el, "y", { duration: 1.2, ease: "power3.out" }),
        depth,
      }));
      const move = (event: PointerEvent) => {
        const nx = event.clientX / window.innerWidth - 0.5;
        const ny = event.clientY / window.innerHeight - 0.5;
        movers.forEach((m) => { m.x(nx * m.depth); m.y(ny * m.depth * 0.5); });
      };
      window.addEventListener("pointermove", move);
      return () => window.removeEventListener("pointermove", move);
    });
  }, { scope: ref });

  return (
    <section className="hero" ref={ref}>
      <DuskField />
      <div className="hero-veil" />
      <div className="hero-grid">
        <div className="hero-side">
          <div className="side-float"><SkillsCard /></div>
        </div>
        <div className="hero-center">
          <h1>El mercado laboral, leído desde el texto</h1>
          <div className="horizon-stage">
            <div className="scale-wrap"><SextantScale /></div>
            <span className="marker left"><i />Alta demanda</span>
            <span className="marker right"><i />Baja demanda</span>
            <div className="halo-wrap"><div className="halo" /></div>
            <div className="figure-wrap"><GlowFigure /></div>
            <div className="cta-wrap">
              <Magnetic><Link href="/cv" className="cta">Analizar mi CV</Link></Magnetic>
            </div>
          </div>
        </div>
        <div className="hero-side right">
          <div className="side-float"><ScanCard /></div>
        </div>
      </div>
    </section>
  );
}
