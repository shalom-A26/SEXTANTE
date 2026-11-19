"use client";

import { useRef } from "react";

import { gsap, MOTION_OK, SplitText, useGSAP } from "@/components/motion/gsap";

const AUDIENCES = [
  ["Si buscas empleo", "Mira qué vacantes se parecen de verdad a tu perfil y qué habilidades te faltan para la que quieres."],
  ["Si contratas", "Compara salarios, modalidades y habilidades pedidas en tu sector antes de publicar."],
  ["Si formas talento", "Ve qué piden las empresas según el nivel educativo y dónde están las brechas."],
];

export function Audiences() {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      // The statement is read word by word as you scroll.
      const split = SplitText.create(q(".statement"), { type: "words" });
      gsap.fromTo(split.words, { opacity: 0.14, filter: "blur(3px)" }, {
        opacity: 1, filter: "blur(0px)", stagger: 0.1, ease: "none",
        scrollTrigger: { trigger: q(".statement"), start: "top 85%", end: "bottom 45%", scrub: 0.5 },
      });
      gsap.from(q(".numbered li"), {
        y: 50, opacity: 0, duration: 1.1, stagger: 0.14,
        scrollTrigger: { trigger: q(".numbered"), start: "top 80%", once: true },
      });
    });
  }, { scope: ref });

  return (
    <section className="block audiences" ref={ref}>
      <span className="pill">Sobre SEXTANTE</span>
      <p className="statement">
        <span className="arrow">↪</span> Un título como “Analista junior” esconde trabajos muy distintos. Leemos miles de
        vacantes colombianas para saber qué se pide, cuánto se paga y dónde encaja tu perfil.
      </p>
      <ol className="numbered">
        {AUDIENCES.map(([title, body], i) => (
          <li key={title}>
            <span className="label">({String(i + 1).padStart(3, "0")})</span>
            <h3>{title}</h3>
            <p>{body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
