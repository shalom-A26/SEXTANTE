"use client";

import { useRef } from "react";

import { gsap, MOTION_OK, SplitText, useGSAP } from "@/components/motion/gsap";

const audiences = [
  ["Si buscas empleo", "Mira qué vacantes se parecen de verdad a tu perfil y qué habilidades te faltan para la que quieres."],
  ["Si contratas", "Compara salarios, modalidades y habilidades pedidas en tu sector antes de publicar."],
  ["Si formas talento", "Ve qué piden las empresas según el nivel educativo y dónde están las brechas."],
];

const steps = [
  ["Reunimos vacantes", "Del Servicio Público de Empleo y de portales como LinkedIn e Indeed, en un formato común."],
  ["Leemos la descripción", "Extraemos habilidades con la taxonomía europea ESCO y detectamos vacantes duplicadas."],
  ["Agrupamos perfiles", "Formamos segmentos ocupacionales por lo que piden las vacantes, no por su título."],
  ["Medimos señales", "Estimamos salarios y trazamos rutas entre ocupaciones a partir de habilidades compartidas."],
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

export function HowItWorks() {
  const ref = useRef<HTMLElement>(null);
  useGSAP(() => {
    const mm = gsap.matchMedia();
    const q = gsap.utils.selector(ref);

    // Wide screens: the section pins and a light runs along the four steps.
    mm.add(`${MOTION_OK} and (min-width: 961px)`, () => {
      const items = q(".how li");
      const tl = gsap.timeline({
        scrollTrigger: { trigger: ref.current, start: "top top", end: "+=1600", pin: true, scrub: 0.7 },
      });
      tl.from(q(".how-title"), { yPercent: 40, opacity: 0, duration: 0.6 })
        .fromTo(q(".how-progress"), { scaleX: 0 }, { scaleX: 1, ease: "none", duration: items.length }, 0.4);
      items.forEach((item, i) => {
        tl.fromTo(item, { opacity: 0.18, y: 30 }, { opacity: 1, y: 0, duration: 0.6 }, 0.4 + i)
          .fromTo(item.querySelector(".step-n"), { scale: 0.4, color: "#fbf1ec" },
            { scale: 1, color: "#f7a24b", duration: 0.5, ease: "back.out(3)" }, 0.5 + i);
      });
      tl.to({}, { duration: 0.6 });
    });

    // Narrow screens: steps simply rise into view.
    mm.add(`${MOTION_OK} and (max-width: 960px)`, () => {
      gsap.from(q(".how li"), {
        y: 40, opacity: 0, duration: 1, stagger: 0.12,
        scrollTrigger: { trigger: q(".how ol"), start: "top 85%", once: true },
      });
    });
  }, { scope: ref });

  return (
    <section className="how" id="como-funciona" ref={ref}>
      <h2 className="how-title">Cómo funciona</h2>
      <div className="how-track"><span className="how-progress" /></div>
      <ol>
        {steps.map(([title, body], i) => (
          <li key={title}>
            <span className="step-n">{i + 1}</span>
            <h3>{title}</h3>
            <p>{body}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
