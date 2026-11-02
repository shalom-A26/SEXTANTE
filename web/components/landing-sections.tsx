"use client";

import { useRef } from "react";

import { gsap, MOTION_OK, SplitText, useGSAP } from "@/components/motion/gsap";

const audiences = [
  ["Si buscas empleo", "Mira qué vacantes se parecen de verdad a tu perfil y qué habilidades te faltan para la que quieres."],
  ["Si contratas", "Compara salarios, modalidades y habilidades pedidas en tu sector antes de publicar."],
  ["Si formas talento", "Ve qué piden las empresas según el nivel educativo y dónde están las brechas."],
];


export function About() {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      // The arc rises like the horizon of the hero, tied to scroll.
      gsap.fromTo(q(".about-arc"), { y: 260, scale: 0.85, opacity: 0 }, {
        y: 0, scale: 1, opacity: 1, ease: "none",
        scrollTrigger: { trigger: ref.current, start: "top bottom", end: "top 20%", scrub: 0.8 },
      });
      // The statement is read word by word as you scroll.
      const split = SplitText.create(q(".statement"), { type: "words" });
      gsap.fromTo(split.words, { opacity: 0.14, filter: "blur(3px)" }, {
        opacity: 1, filter: "blur(0px)", stagger: 0.1, ease: "none",
        scrollTrigger: { trigger: q(".statement"), start: "top 85%", end: "bottom 45%", scrub: 0.5 },
      });
      gsap.from(q(".audiences li"), {
        x: -40, opacity: 0, duration: 1.1, stagger: 0.14,
        scrollTrigger: { trigger: q(".audiences"), start: "top 80%", once: true },
      });
      gsap.from(q(".sources > *"), {
        x: 40, opacity: 0, duration: 1.1, stagger: 0.12,
        scrollTrigger: { trigger: q(".sources"), start: "top 80%", once: true },
      });
      gsap.from(q(".about-center .kicker"), {
        letterSpacing: "0.4em", opacity: 0, duration: 1.4,
        scrollTrigger: { trigger: q(".about-center"), start: "top 80%", once: true },
      });
    });
  }, { scope: ref });

  return (
    <section className="about" ref={ref}>
      <div className="about-arc" aria-hidden="true" />
      <div className="about-grid">
        <ul className="audiences">
          {audiences.map(([title, body]) => (
            <li key={title}><h3>{title}</h3><p>{body}</p></li>
          ))}
        </ul>
        <div className="about-center">
          <span className="kicker">Sobre SEXTANTE</span>
          <p className="statement">
            Un título como “Analista junior” esconde trabajos muy distintos. Leemos miles de vacantes colombianas
            para saber qué se pide, cuánto se paga y dónde encaja tu perfil.
          </p>
        </div>
        <div className="sources">
          <span className="kicker">Datos de</span>
          <strong>Servicio Público de Empleo</strong>
          <strong>LinkedIn</strong>
          <strong>Indeed</strong>
        </div>
      </div>
    </section>
  );
}
