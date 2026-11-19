"use client";

import Link from "next/link";
import { useRef } from "react";

import { Magnetic } from "@/components/motion";
import { gsap, MOTION_OK, ScrollTrigger, SplitText, useGSAP } from "@/components/motion/gsap";
import { sceneState } from "@/components/scene/state";

type Chapter = { pill: string; title: React.ReactNode; sub: string; cta?: boolean };

const CHAPTERS: Chapter[] = [
  {
    pill: "SEXTANTE · UTB",
    title: <>El mercado laboral, <em>leído</em> desde el texto</>,
    sub: "Vacantes colombianas del SPE y portales de empleo",
    cta: true,
  },
  {
    pill: "El problema",
    title: <>Un <em>“Analista junior”</em> <span className="arrow">↪</span> esconde trabajos distintos</>,
    sub: "El título no dice lo que piden: la señal está en la descripción",
  },
  {
    pill: "Qué leemos",
    title: <>Habilidades <span className="arrow">↪</span> <em>salarios</em> y perfiles</>,
    sub: "Catálogo ESCO · bandas salariales oficiales del SPE · segmentos ocupacionales",
  },
  {
    pill: "Para quién",
    title: <>Candidatos, <em>empresas</em> <span className="arrow">↪</span> y academia</>,
    sub: "Qué se pide, cuánto se paga y dónde están las brechas",
  },
  {
    pill: "Tu turno",
    title: <>Sube tu CV <span className="arrow">↪</span> y mira a qué <em>vacantes</em> te pareces</>,
    sub: "Se procesa en memoria y no se guarda",
    cta: true,
  },
];

const pad = (n: number) => String(n).padStart(2, "0");

// Pinned scroll story: one chapter at a time over the WebGL dusk, like a slide
// show driven by the scrollbar. Narrow screens and reduced motion get a plain stack.
export function Chapters() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(() => {
    const root = ref.current!;
    // The scene follows the whole page: dusk at the top, night at the bottom.
    const page = ScrollTrigger.create({
      start: 0, end: "max", onUpdate: (self) => { sceneState.progress = self.progress; },
    });

    const mm = gsap.matchMedia();
    mm.add(`${MOTION_OK} and (min-width: 768px)`, () => {
      root.classList.add("is-pinned");
      const q = gsap.utils.selector(root);
      const chapters = q(".chapter");
      const words = chapters.map((c) =>
        SplitText.create(c.querySelector("h1, h2"), { type: "words", mask: "words" }).words);
      const counter = q(".chapter-count b")[0];

      gsap.set(chapters.slice(1), { autoAlpha: 0 });
      // Entrance of the first chapter.
      gsap.from(words[0], { yPercent: 120, rotate: 4, duration: 1.3, stagger: 0.07, delay: 0.3 });
      gsap.from(q(".chapter:first-child .pill, .chapter:first-child .chapter-sub, .chapter:first-child .chapter-cta"), {
        y: 24, autoAlpha: 0, duration: 1.2, stagger: 0.1, delay: 0.8,
      });

      const tl = gsap.timeline({
        defaults: { ease: "power3.inOut" },
        scrollTrigger: {
          trigger: root, start: "top top", end: `+=${(CHAPTERS.length - 1) * 100}%`,
          pin: q(".chapters-stage")[0], scrub: 0.8,
          onUpdate: (self) => {
            counter.textContent = pad(Math.round(self.progress * (CHAPTERS.length - 1)) + 1);
          },
        },
      });
      for (let i = 1; i < CHAPTERS.length; i++) {
        const out = chapters[i - 1];
        const inn = chapters[i];
        tl.to(words[i - 1], { yPercent: -120, stagger: 0.03, duration: 0.5 }, i - 1)
          .to(out.querySelectorAll(".pill, .chapter-sub, .chapter-cta"), { y: -30, autoAlpha: 0, duration: 0.4 }, i - 1)
          .set(out, { autoAlpha: 0 }, i - 0.5)
          .set(inn, { autoAlpha: 1 }, i - 0.5)
          .from(words[i], { yPercent: 120, rotate: 3, stagger: 0.04, duration: 0.5 }, i - 0.5)
          .from(inn.querySelectorAll(".pill, .chapter-sub, .chapter-cta"), { y: 30, autoAlpha: 0, duration: 0.4 }, i - 0.4);
      }
      return () => root.classList.remove("is-pinned");
    });

    return () => {
      page.kill();
      sceneState.progress = 0;
    };
  }, { scope: ref });

  return (
    <section className="chapters" ref={ref}>
      <div className="chapters-stage">
        {CHAPTERS.map((c, i) => {
          const Title = i === 0 ? "h1" : "h2";
          return (
            <div className="chapter" key={c.pill}>
              <span className="pill">{c.pill}</span>
              <Title className="display">{c.title}</Title>
              <p className="label chapter-sub">{c.sub}</p>
              {c.cta && (
                <div className="chapter-cta">
                  <Magnetic><Link href="/cv" className="cta">Analizar mi CV ↪</Link></Magnetic>
                  <Link href="/dashboard" className="ghost-link">Ver el dashboard</Link>
                </div>
              )}
            </div>
          );
        })}
        <p className="label chapter-count" aria-hidden="true"><b>01</b> / {pad(CHAPTERS.length)}</p>
        <p className="label chapter-hint" aria-hidden="true">Desliza ↓</p>
      </div>
    </section>
  );
}
