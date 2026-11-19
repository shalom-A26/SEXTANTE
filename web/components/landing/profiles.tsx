"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { GlowButton, HookArrow } from "@/components/glow-button";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { prng } from "@/components/world/shapes";
import { getDashboard, type Segment } from "@/lib/api";

const HUES = [
  ["#e0761b", "#f7c6a3"], ["#8c3f2e", "#f27c8c"], ["#b9687c", "#ffd3a6"], ["#5e2420", "#f7a24b"],
  ["#c8445a", "#fbf1ec"], ["#6f3a52", "#ecc0a8"], ["#a3542e", "#f6d36b"], ["#2e1211", "#f27c8c"],
];

/** Generated cover: a dusk gradient with the segment's skills as glowing bodies. */
function Art({ seg, i }: { seg: Segment; i: number }) {
  const r = prng(seg.id * 97 + 3);
  const [deep, light] = HUES[i % HUES.length];
  const skills = seg.top_skills.slice(0, 7);
  return (
    <svg viewBox="0 0 400 500" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <radialGradient id={`g${seg.id}`} cx="50%" cy="38%" r="75%">
          <stop offset="0" stopColor={light} />
          <stop offset="0.45" stopColor={deep} />
          <stop offset="1" stopColor="#1c0a0a" />
        </radialGradient>
        <filter id={`b${seg.id}`}><feGaussianBlur stdDeviation="14" /></filter>
      </defs>
      <rect width="400" height="500" fill={`url(#g${seg.id})`} />
      <circle cx="200" cy="200" r="120" fill={light} opacity="0.35" filter={`url(#b${seg.id})`} />
      {skills.map((k, j) => {
        const x = 70 + r() * 260, y = 120 + r() * 300, rad = 8 + k.share * 160;
        return <circle key={k.skill} cx={x} cy={y} r={Math.min(rad, 70)} fill={j % 2 ? light : "#fbf1ec"} opacity={0.25 + r() * 0.5} />;
      })}
      <path d="M40 470 Q 200 380 360 470" stroke="#fbf1ec" strokeOpacity="0.4" fill="none" />
    </svg>
  );
}

function Letters({ text }: { text: string }) {
  return <>{[...text].map((c, i) => <span key={i} className="ch" style={{ "--i": i } as React.CSSProperties}>{c}</span>)}</>;
}

export function Profiles() {
  const ref = useRef<HTMLElement>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  useEffect(() => {
    getDashboard().then((d) => setSegments(d.segments.slice(0, 8))).catch(() => setSegments([]));
  }, []);

  useGSAP(() => {
    if (!segments.length) return;
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      gsap.from(q(".profiles-title > *"), {
        yPercent: 60, autoAlpha: 0, duration: 1.4, stagger: 0.1, ease: "expo.out",
        scrollTrigger: { trigger: q(".profiles-title")[0], start: "top 85%", once: true },
      });
      q(".p-card").forEach((card, i) => {
        gsap.from(card, {
          y: 120, autoAlpha: 0, duration: 1.4, ease: "expo.out", delay: (i % 4) * 0.06,
          scrollTrigger: { trigger: card, start: "top 92%", once: true },
        });
        // Slight parallax: cards drift at different speeds.
        gsap.to(card.querySelector(".p-art"), {
          yPercent: (i % 3) * -6 - 3, ease: "none",
          scrollTrigger: { trigger: card, start: "top bottom", end: "bottom top", scrub: true },
        });
      });
    });
  }, { scope: ref, dependencies: [segments] });

  if (!segments.length) return null;
  return (
    <section className="profiles paper" id="perfiles" ref={ref}>
      <h2 className="profiles-title" aria-label="Algunos de los perfiles">
        <span className="display">Algunos</span>
        <span className="it">de los</span>
        <span className="arrow-r" aria-hidden="true">⟶</span>
        <span className="display">Perfiles</span>
      </h2>
      <div className="p-grid">
        {segments.map((s, i) => {
          const skills = s.top_skills.slice(0, 3).map((k) => k.skill).join(" · ") || "—";
          return (
            <Link key={s.id} href="/dashboard" className="p-card">
              <div className="p-art">
                <Art seg={s} i={i} />
                <div className="p-overlay" aria-hidden="true">
                  <dl className="p-data mono">
                    <dt><Letters text="SEG" /></dt><dd><Letters text={`/${String(i + 1).padStart(2, "0")}`} /></dd>
                    <dt><Letters text="VACANTES" /></dt><dd><Letters text={s.postings.toLocaleString("es-CO")} /></dd>
                    <dt><Letters text="SALARIO" /></dt><dd><Letters text={s.salary.mode ?? "sin rango"} /></dd>
                    <dt><Letters text="MODALIDAD" /></dt><dd><Letters text={s.modality[0]?.label ?? "—"} /></dd>
                  </dl>
                  <p className="mono"><Letters text={skills} /></p>
                </div>
              </div>
              <span className="label">{s.postings.toLocaleString("es-CO")} vacantes / {s.salary.mode ?? "sin rango"}</span>
              <span className="p-name"><HookArrow /><span>{s.name}</span></span>
            </Link>
          );
        })}
      </div>
      <div className="p-more"><GlowButton href="/dashboard" size="lg">Ver todos los segmentos</GlowButton></div>
    </section>
  );
}
