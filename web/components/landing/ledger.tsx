"use client";

import { useEffect, useRef, useState } from "react";

import { CountUp } from "@/components/motion";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { getDashboard, type Dashboard } from "@/lib/api";

type Group = { title: string; rows: [string, string][] };

const pct = (v: number) => `${Math.round(v * 100)}%`;

// The corpus in figures, laid out like an awards table: group · [count] on the
// left, its rows on the right. Hovering a group dims the others.
export function Ledger() {
  const ref = useRef<HTMLElement>(null);
  const [data, setData] = useState<Dashboard | null>(null);
  useEffect(() => {
    getDashboard().then(setData).catch(() => setData(null));
  }, []);

  useGSAP(() => {
    if (!data) return;
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      gsap.from(q(".ledger-line"), {
        scaleX: 0, duration: 1.4, ease: "expo.inOut", stagger: 0.12,
        scrollTrigger: { trigger: q(".ledger-groups")[0], start: "top 85%", once: true },
      });
      gsap.from(q(".ledger-group h3, .ledger-rows li"), {
        y: 24, autoAlpha: 0, duration: 1, stagger: 0.03,
        scrollTrigger: { trigger: q(".ledger-groups")[0], start: "top 80%", once: true },
      });
    });
  }, { scope: ref, dependencies: [data] });

  if (!data) return null;
  const o = data.overview;
  const groups: Group[] = [
    { title: "Fuentes", rows: o.sources.map((s) => [s.label.toUpperCase() === "SPE" ? "Servicio Público de Empleo" : s.label[0].toUpperCase() + s.label.slice(1), s.count.toLocaleString("es-CO")]) },
    { title: "Habilidades", rows: data.top_skills.slice(0, 5).map((s) => [s.skill, pct(s.share)]) },
    { title: "Ciudades", rows: o.cities.slice(0, 4).map((c) => [c.label, c.count.toLocaleString("es-CO")]) },
    { title: "Salarios", rows: data.salaries.overall.bands.slice(0, 4).map((b) => [b.band, pct(b.share)]) },
  ];

  return (
    <section className="ledger paper" ref={ref}>
      <div className="ledger-top">
        <h2 className="display">El corpus <i>&amp;</i><br />sus cifras</h2>
        <p className="mono">
          {data.run.synthetic ? "Datos sintéticos de demostración" : "Vacantes reales del SPE y portales de empleo"}, recalculadas cada día
        </p>
        <span className="pill">Total: <CountUp value={o.postings} /></span>
      </div>
      <ul className="ledger-groups">
        {groups.map((g) => (
          <li key={g.title} className="ledger-group">
            <span className="ledger-line" aria-hidden="true" />
            <h3>{g.title}<small>[{g.rows.length}]</small></h3>
            <ul className="ledger-rows">
              {g.rows.map(([label, value]) => (
                <li key={label}><span>{label}</span><small className="mono">{value}</small></li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
