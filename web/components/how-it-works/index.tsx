"use client";

import { useEffect, useRef, useState } from "react";

import { CountUp, SplitHeading } from "@/components/motion";
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from "@/components/motion/gsap";
import { getDashboard, type Dashboard } from "@/lib/api";

import { STEPS } from "./steps";
import { buildTimeline, Visual } from "./visuals";

// A scroll walkthrough of the real pipeline: one sticky scene on the left that
// changes with the step being read on the right.
export function HowItWorks() {
  const ref = useRef<HTMLElement>(null);
  const [data, setData] = useState<Dashboard | null>(null);
  const [active, setActive] = useState(0);

  useEffect(() => {
    getDashboard().then(setData).catch(() => setData(null));
  }, []);

  const terms = data?.segments?.[0]?.terms?.slice(0, 6) ?? [];

  useGSAP(() => {
    const root = ref.current!;
    const scenes = gsap.utils.toArray<HTMLElement>(".hw-scene", root);
    const steps = gsap.utils.toArray<HTMLElement>(".hw-step", root);
    const mm = gsap.matchMedia();

    mm.add(MOTION_OK, () => {
      const timelines = scenes.map((scene) => buildTimeline(scene.dataset.key!, scene));
      let current = -1;
      const show = (index: number) => {
        if (index === current) return;
        if (current >= 0) {
          timelines[current].pause();
          gsap.to(scenes[current], { autoAlpha: 0, y: -20, scale: 0.97, duration: 0.5, ease: "power2.in", overwrite: true });
        }
        current = index;
        setActive(index);
        gsap.fromTo(scenes[index], { autoAlpha: 0, y: 30, scale: 0.97 }, { autoAlpha: 1, y: 0, scale: 1, duration: 0.8, delay: 0.15, overwrite: true });
        timelines[index].restart(true);
      };
      gsap.set(scenes, { autoAlpha: 0 });
      steps.forEach((step, i) => {
        ScrollTrigger.create({
          trigger: step, start: "top 55%", end: "bottom 55%",
          onToggle: (self) => self.isActive && show(i),
        });
        gsap.from(step.querySelectorAll(".hw-reveal"), {
          y: 40, opacity: 0, duration: 1, stagger: 0.1,
          scrollTrigger: { trigger: step, start: "top 80%", once: true },
        });
      });
      gsap.fromTo(".hw-progress-fill", { scaleY: 0 }, {
        scaleY: 1, ease: "none", transformOrigin: "50% 0%",
        scrollTrigger: { trigger: ".hw-steps", start: "top 55%", end: "bottom 55%", scrub: true },
      });
      show(0);
      return () => timelines.forEach((t) => t.kill());
    });
    // Reduced motion: every scene is visible in its final state next to its text.
    mm.add("(prefers-reduced-motion: reduce)", () => {
      root.classList.add("hw-static");
    });
  }, { scope: ref });

  return (
    <section className="hw" id="como-funciona" ref={ref}>
      <header className="hw-head">
        <SplitHeading as="h2">Cómo funciona, paso a paso</SplitHeading>
        <p className="lead">
          Lo que ocurre entre una vacante publicada y el resultado que ves: nueve etapas, el algoritmo detrás de cada una y las
          cifras reales del corpus actual.
        </p>
      </header>

      <div className="hw-body">
        <div className="hw-stage" aria-hidden="true">
          <div className="hw-frame">
            {STEPS.map((step) => (
              <div key={step.key} className="hw-scene" data-key={step.key}>
                <Visual stepKey={step.key} terms={terms} />
              </div>
            ))}
            <span className="hw-counter">
              <b>{String(active + 1).padStart(2, "0")}</b> / {String(STEPS.length).padStart(2, "0")}
            </span>
          </div>
        </div>

        <ol className="hw-steps">
          <span className="hw-progress" aria-hidden="true"><span className="hw-progress-fill" /></span>
          {STEPS.map((step, i) => {
            const metrics = data && step.metrics ? step.metrics(data) : [];
            return (
              <li key={step.key} className={`hw-step${i === active ? " is-active" : ""}`}>
                <span className="hw-num" aria-hidden="true">{i + 1}</span>
                <div className="hw-scene-inline" aria-hidden="true"><Visual stepKey={step.key} terms={terms} /></div>
                <h3 className="hw-reveal">{step.title}</h3>
                <p className="hw-reveal hw-lead">{step.lead}</p>
                <div className="hw-reveal hw-inside">
                  <span className="hw-label">Qué pasa por dentro</span>
                  <ul>{step.inside.map((line) => <li key={line}>{line}</li>)}</ul>
                </div>
                <pre className="hw-reveal hw-algo"><code>{step.algorithm}</code></pre>
                {metrics.length > 0 && (
                  <dl className="hw-reveal hw-metrics">
                    {metrics.map((m) => (
                      <div key={m.label}>
                        <dt>{m.label}</dt>
                        <dd><CountUp value={m.value} format={m.format} /></dd>
                      </div>
                    ))}
                  </dl>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
