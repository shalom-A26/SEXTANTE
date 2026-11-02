"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { getDashboard } from "@/lib/api";

// Fixed, faint layer behind every page: what the system reads and computes,
// drifting by. Decorative only (aria-hidden, no pointer events).
const PIPELINE = [
  "TF-IDF 1–2 gramas", "K-Means", "SVD", "MinHash LSH", "Louvain", "PageRank", "Ridge log-salario",
  "ESCO v1.2.1", "silueta", "coseno", "NMF", "Dijkstra", "17 columnas", "append-only", "trie de tokens",
];
const FALLBACK_SKILLS = [
  "servicio al cliente", "hojas de cálculo", "trabajar en equipo", "procedimientos de facturación",
  "ventas", "contabilidad", "logística", "atención telefónica", "gestión de inventarios", "nómina",
];

function seeded(n: number) {
  let s = 7;
  return Array.from({ length: n }, () => {
    s = (s * 16807) % 2147483647;
    return s / 2147483647;
  });
}

export function SystemBackdrop() {
  const ref = useRef<HTMLDivElement>(null);
  const [skills, setSkills] = useState(FALLBACK_SKILLS);
  const [segments, setSegments] = useState<string[]>([]);

  useEffect(() => {
    getDashboard().then((d) => {
      const top = d.top_skills.map((s) => s.skill).slice(0, 18);
      if (top?.length) setSkills(top);
      setSegments(d.segments.map((s) => s.name).slice(0, 16));
    }).catch(() => undefined);
  }, []);

  const rows = useMemo(() => [
    skills,
    PIPELINE,
    segments.length ? segments : FALLBACK_SKILLS.slice().reverse(),
    [...PIPELINE].reverse(),
  ], [skills, segments]);

  const nodes = useMemo(() => {
    const r = seeded(80);
    return Array.from({ length: 40 }, (_, i) => ({ x: r[i * 2] * 1000, y: r[i * 2 + 1] * 1000 }));
  }, []);
  const edges = useMemo(() => nodes.flatMap((a, i) => nodes.slice(i + 1)
    .filter((b) => Math.hypot(a.x - b.x, a.y - b.y) < 170).map((b) => [a, b] as const)), [nodes]);

  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      const tweens = q(".bd-row-inner").map((row, i) => gsap.fromTo(row,
        { xPercent: i % 2 ? -50 : 0 },
        { xPercent: i % 2 ? 0 : -50, duration: 90 + i * 25, ease: "none", repeat: -1 }));
      tweens.push(gsap.to(q(".bd-node"), {
        opacity: 0.9, duration: 2.4, ease: "sine.inOut", yoyo: true, repeat: -1,
        stagger: { each: 0.15, from: "random", repeat: -1, yoyo: true },
      }));
      gsap.to(q(".bd-graph"), {
        yPercent: -18, ease: "none",
        scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 1 },
      });
      const onVisibility = () => tweens.forEach((t) => (document.hidden ? t.pause() : t.resume()));
      document.addEventListener("visibilitychange", onVisibility);
      return () => document.removeEventListener("visibilitychange", onVisibility);
    });
  }, { scope: ref, dependencies: [rows], revertOnUpdate: true });

  return (
    <div className="backdrop" ref={ref} aria-hidden="true">
      <svg className="bd-graph" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice">
        {edges.map(([a, b], i) => <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />)}
        {nodes.map((n, i) => <circle key={i} className="bd-node" cx={n.x} cy={n.y} r={i % 5 ? 2.2 : 4} />)}
      </svg>
      <div className="bd-rows">
        {rows.map((row, i) => (
          <div key={i} className={`bd-row bd-row-${i}`}>
            {/* Content duplicated so the loop at -50% is seamless. */}
            <div className="bd-row-inner">
              {[...row, ...row].map((word, k) => <span key={k}>{word}</span>)}
            </div>
          </div>
        ))}
      </div>
      <div className="bd-ticks bd-ticks-left" />
      <div className="bd-ticks bd-ticks-right" />
    </div>
  );
}
