"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { getDashboard, type Dashboard } from "@/lib/api";

// Live card: demand share of the most requested skills. Hidden if the API is down.
export function SkillsCard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const ref = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    getDashboard().then(setData).catch(() => setData(null));
  }, []);

  const skills = data?.top_skills.slice(0, 10) ?? [];
  const share = skills.length ? Math.round(skills[0].share * 100) : 0;

  useGSAP(() => {
    if (!ref.current) return;
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      const counter = { v: 0 };
      gsap.timeline({ delay: 0.3 })
        .from(ref.current, { opacity: 0, y: 24, filter: "blur(8px)", duration: 1.2 })
        .from(q(".spark-line"), { drawSVG: 0, duration: 2, ease: "power2.inOut" }, 0.2)
        .from(q(".spark-area"), { opacity: 0, duration: 1.6 }, 0.8)
        .from(q(".spark-dot"), { scale: 0, transformOrigin: "50% 50%", duration: 0.8, ease: "back.out(3)" }, 1.4)
        .from(q(".chip-float"), { y: 10, opacity: 0, duration: 0.6 }, 1.5)
        .to(counter, {
          v: share, duration: 1.4, ease: "power3.out",
          onUpdate: () => { const chip = q(".chip-float")[0]; if (chip) chip.textContent = `${Math.round(counter.v)}%`; },
        }, 1.5);
      gsap.to(q(".spark-dot"), { scale: 1.5, transformOrigin: "50% 50%", duration: 1.2, yoyo: true, repeat: -1, ease: "sine.inOut", delay: 3 });
    });
  }, { dependencies: [data], scope: ref });

  if (skills.length < 3) return <div className="glass-card placeholder" aria-hidden="true" />;

  const max = skills[0].share || 1;
  const points = skills.map((s, i) => [8 + (i * 184) / (skills.length - 1), 92 - (s.share / max) * 66]);
  const line = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const [tx, ty] = points[0];

  return (
    <Link href="/dashboard" className="glass-card skills-card" ref={ref}>
      <span className="card-title">Habilidades más pedidas</span>
      <svg viewBox="0 0 200 100" role="img" aria-label={`${skills[0].skill} aparece en ${share}% de las vacantes`}>
        <defs>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f7a24b" stopOpacity="0.55" />
            <stop offset="1" stopColor="#f7a24b" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path className="spark-area" d={`${line}L192 100L8 100Z`} fill="url(#area)" />
        <path className="spark-line" d={line} fill="none" stroke="#f7a24b" strokeWidth="1.6" />
        <circle className="spark-dot" cx={tx} cy={ty} r="3.5" fill="#fbf1ec" />
      </svg>
      <span className="chip-float" style={{ left: `${(tx / 200) * 100}%` }}>{share}%</span>
      <span className="card-foot">{skills[0].skill}</span>
    </Link>
  );
}

// Scanner: a CV being read; lines it "recognises" light up as the beam passes.
export function ScanCard({ standalone = false }: { standalone?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      const beam = gsap.timeline({ repeat: -1, repeatDelay: 0.4 });
      beam
        .fromTo(q(".scanline"), { top: "4%" }, { top: "94%", duration: 1.8, ease: "power1.inOut" })
        .to(q(".scanline"), { top: "4%", duration: 1.8, ease: "power1.inOut" });
      q(".doc span").forEach((line, i) => {
        const at = 0.15 + (i / 6) * 1.6;
        beam.fromTo(line, { scaleX: 0.92, transformOrigin: "0 50%" }, {
          scaleX: 1, duration: 0.4, ease: "back.out(3)",
          backgroundColor: line.classList.contains("hit") ? "#ffd3a6" : "rgba(251,241,236,0.5)",
          yoyo: true, repeat: 1,
        }, at);
      });
      gsap.to(q(".corner"), { scale: 1.25, duration: 1.1, yoyo: true, repeat: -1, ease: "sine.inOut", stagger: 0.2 });
      if (!standalone) gsap.to(q(".play"), { scale: 1.1, duration: 0.9, yoyo: true, repeat: -1, ease: "sine.inOut", delay: 2.5 });
    });
  }, { scope: ref });

  return (
    <div className={`glass-card scan-card${standalone ? " standalone" : ""}`} ref={ref}>
      <span className="card-title">{standalone ? "Leyendo tu CV…" : "Lectura de tu CV"}</span>
      <div className="scan-frame">
        <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
        <div className="doc" aria-hidden="true">
          <span style={{ width: "62%" }} /><span style={{ width: "88%" }} /><span className="hit" style={{ width: "40%" }} />
          <span style={{ width: "76%" }} /><span className="hit" style={{ width: "52%" }} /><span style={{ width: "68%" }} />
          <div className="scanline" />
        </div>
      </div>
      {!standalone && (
        <Link href="/cv" className="play" aria-label="Probar con mi CV">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6.5v11l9-5.5z" fill="currentColor" /></svg>
        </Link>
      )}
    </div>
  );
}
