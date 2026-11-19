"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { DuskField } from "@/components/field";
import { GlowButton } from "@/components/glow-button";
import { gsap, MOTION_OK, ScrollTrigger, SplitText, useGSAP } from "@/components/motion/gsap";
import { worldState } from "@/components/world/state";

const World = dynamic(() => import("@/components/world/world"), { ssr: false });

function webglOk() {
  try {
    return !!document.createElement("canvas").getContext("webgl2");
  } catch {
    return false;
  }
}

// Five chapters over the dusk valley; each one sits in a different part of the
// frame, like the reference. Copy is SEXTANTE's own.
export function Chapters() {
  const ref = useRef<HTMLElement>(null);
  const [live, setLive] = useState<boolean | null>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    setLive(webglOk() && window.matchMedia(MOTION_OK).matches);
  }, []);

  useGSAP(() => {
    if (!live) return;
    const root = ref.current!;
    const q = gsap.utils.selector(root);
    const chapters = q(".chapter");
    const splits = chapters.map((c) => SplitText.create(c.querySelectorAll(".display, .ch-lead"), { type: "words", mask: "words" }));
    gsap.set(chapters.slice(1), { autoAlpha: 0 });

    let current = 0;
    const show = (next: number) => {
      if (next === current) return;
      const out = chapters[current];
      const inn = chapters[next];
      const dir = next > current ? 1 : -1;
      gsap.to(splits[current].words, { yPercent: -110 * dir, duration: 0.5, stagger: 0.02, ease: "power3.in", overwrite: true });
      gsap.to(out.querySelectorAll(".pill, .mono, .ch-cta"), { y: -20 * dir, autoAlpha: 0, duration: 0.35, overwrite: true });
      gsap.set(out, { autoAlpha: 0, delay: 0.5 });
      gsap.set(inn, { autoAlpha: 1, delay: 0.35 });
      gsap.fromTo(splits[next].words, { yPercent: 110 * dir }, { yPercent: 0, duration: 0.9, stagger: 0.04, delay: 0.4, ease: "expo.out", overwrite: true });
      gsap.fromTo(inn.querySelectorAll(".pill, .mono, .ch-cta"), { y: 24 * dir, autoAlpha: 0 }, { y: 0, autoAlpha: 1, duration: 0.8, stagger: 0.08, delay: 0.55, overwrite: true });
      const title = inn.querySelector(".display")!;
      title.classList.remove("glitch");
      gsap.delayedCall(0.45, () => title.classList.add("glitch"));
      current = next;
      setActive(next);
    };

    const st = ScrollTrigger.create({
      trigger: root, start: "top top", end: "bottom bottom",
      onUpdate: (self) => {
        worldState.progress = self.progress * 4;
        show(Math.min(4, Math.floor(self.progress * 5)));
      },
      // The header turns cream while it floats over the world.
      onToggle: (self) => { document.documentElement.dataset.header = self.isActive ? "light" : ""; },
    });
    document.documentElement.dataset.header = window.scrollY < root.offsetHeight - window.innerHeight ? "light" : "";

    // First chapter entrance, once the intro has gone.
    const enter = () => {
      gsap.from(splits[0].words, { yPercent: 115, duration: 1.4, stagger: 0.06, ease: "expo.out" });
      gsap.from(q(".ch-1 .mono"), { autoAlpha: 0, y: 20, duration: 1.2, delay: 0.5 });
    };
    if (document.documentElement.dataset.intro === "open") window.addEventListener("intro-done", enter, { once: true });
    else enter();

    return () => {
      st.kill();
      window.removeEventListener("intro-done", enter);
      delete document.documentElement.dataset.header;
      worldState.progress = 0;
    };
  }, { scope: ref, dependencies: [live] });

  return (
    <section ref={ref} className={`world-section theme-dark${live === false ? " world-static" : ""}`} aria-label="SEXTANTE en cinco capítulos">
      <div className="world-stage">
        {live ? <World /> : <DuskField />}
        <div className="world-veil" />

        <div className="chapter ch-1">
          <p className="mono">Vacantes colombianas del SPE y portales de empleo, leídas por su texto</p>
          <span className="ch-lead it">Donde</span>
          <h1 className="display">cada vacante se vuelve un mapa del trabajo</h1>
        </div>

        <div className="chapter ch-2">
          <span className="pill">El problema</span>
          <h2 className="display"><i>Un</i> “analista junior” <span className="arrow">↪</span> esconde trabajos distintos</h2>
          <p className="mono">El título no dice lo que piden. La señal está en la descripción, sin taxonomía y con vocabulario libre.</p>
        </div>

        <div className="chapter ch-3">
          <span className="pill">Qué leemos</span>
          <h2 className="display">Habilidades <i>y</i> salarios <span className="arrow">↪</span> en cifras</h2>
          <p className="mono">Habilidades del catálogo ESCO, rangos salariales oficiales del SPE y modalidades, vacante por vacante.</p>
        </div>

        <div className="chapter ch-4">
          <span className="pill">Segmentos</span>
          <h2 className="display">Perfiles <i>con</i> sentido</h2>
          <p className="mono">Agrupamos las vacantes por lo que de verdad piden y medimos qué habilidades conectan un oficio con otro.</p>
        </div>

        <div className="chapter ch-5">
          <span className="pill">Tu turno</span>
          <p className="mono">Tu CV se procesa en memoria y no se guarda</p>
          <span className="ch-lead it">Tú</span>
          <h2 className="display">Sube tu CV <span className="arrow">↪</span> y mira a qué vacantes te pareces</h2>
          <div className="ch-cta">
            <GlowButton href="/cv" size="lg" solid>Analizar mi CV</GlowButton>
            <a href="/dashboard" className="u-link mono">Ver el dashboard</a>
          </div>
        </div>

        <nav className="world-progress" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((i) => <i key={i} className={i === active ? "on" : ""} />)}
        </nav>
        <p className="world-hint label" style={{ color: "#fbf1ec" }} aria-hidden="true">Desliza ↓</p>
      </div>
    </section>
  );
}
