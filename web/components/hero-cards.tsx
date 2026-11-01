"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getDashboard, type Dashboard } from "@/lib/api";

// Live card: demand share of the most requested skills. Hidden if the API is down.
export function SkillsCard() {
  const [data, setData] = useState<Dashboard | null>(null);
  useEffect(() => {
    getDashboard().then(setData).catch(() => setData(null));
  }, []);
  if (!data || data.top_skills.length < 3) return <div className="glass-card placeholder" aria-hidden="true" />;

  const skills = data.top_skills.slice(0, 10);
  const max = skills[0].share || 1;
  const points = skills.map((s, i) => [8 + (i * 184) / (skills.length - 1), 92 - (s.share / max) * 66]);
  const line = points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const [tx, ty] = points[0];

  return (
    <Link href="/dashboard" className="glass-card skills-card">
      <span className="card-title">Habilidades más pedidas</span>
      <svg viewBox="0 0 200 100" role="img" aria-label={`${skills[0].skill} aparece en ${Math.round(skills[0].share * 100)}% de las vacantes`}>
        <defs>
          <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#f7a24b" stopOpacity="0.55" />
            <stop offset="1" stopColor="#f7a24b" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${line}L192 100L8 100Z`} fill="url(#area)" />
        <path d={line} fill="none" stroke="#f7a24b" strokeWidth="1.6" />
        <circle cx={tx} cy={ty} r="3.5" fill="#fbf1ec" />
      </svg>
      <span className="chip-float" style={{ left: `${(tx / 200) * 100}%` }}>{Math.round(skills[0].share * 100)}%</span>
      <span className="card-foot">{skills[0].skill}</span>
    </Link>
  );
}

// Decorative scanner: a CV being read, with the skills it finds.
export function ScanCard() {
  return (
    <div className="glass-card scan-card">
      <span className="card-title">Lectura de tu CV</span>
      <div className="scan-frame">
        <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
        <div className="doc" aria-hidden="true">
          <span style={{ width: "62%" }} /><span style={{ width: "88%" }} /><span className="hit" style={{ width: "40%" }} />
          <span style={{ width: "76%" }} /><span className="hit" style={{ width: "52%" }} /><span style={{ width: "68%" }} />
          <div className="scanline" />
        </div>
      </div>
      <Link href="/cv" className="play" aria-label="Probar con mi CV">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 6.5v11l9-5.5z" fill="currentColor" /></svg>
      </Link>
    </div>
  );
}
