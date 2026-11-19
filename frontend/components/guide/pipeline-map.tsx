import { useEffect, useRef } from "react";

import { gsap, MOTION_OK } from "@/components/motion/gsap";

import { LAYERS, STEPS, type Layer } from "./steps";

// The pipeline as a metro line that steps down through the medallion layers:
// sources → bronze → silver → gold → serving. A dot (one posting) travels to
// the active technique.

const W = 1280;
// Where each layer lives, in two short lines for the left column.
const FILES: Record<"sources" | Layer, [string, string]> = {
  sources: ["exportación SPE (CSV)", "JobSpy · no se guarda"],
  bronze: ["data/spe/week-*", "data/jobspy/day-*"],
  silver: ["derived/runs/<id>/", "postings · skills · tfidf"],
  gold: ["dashboard.json · modelos", "grafo · serving/"],
  serve: ["sextante_api", "/api/cv/match"],
};
const LANES: { id: "sources" | Layer; label: string; y: number; color: string }[] = [
  { id: "sources", label: "Fuentes", y: 42, color: "#8c3f2e" },
  ...(["bronze", "silver", "gold", "serve"] as Layer[]).map((id, i) => ({ id, label: LAYERS[id].name, y: 112 + i * 70, color: LAYERS[id].color })),
];
const laneY = (l: Layer) => LANES.find((x) => x.id === l)!.y;
const X: Record<string, number> = {
  capture: 420, store: 515, repair: 605, clean: 690, skills: 775, duplicates: 860, tfidf: 945,
  topics: 1025, segments: 1100, salary: 1170, graph: 1240, cv: 1240,
};
export const NODES = STEPS.map((s) => ({ key: s.key, x: X[s.key], y: laneY(s.layer), layer: s.layer, short: s.short }));
const SOURCES = [{ x: 255, label: "SPE" }, { x: 310, label: "LinkedIn" }, { x: 365, label: "Indeed" }];

// Smooth S-curves between consecutive stations.
type Seg = [number, number, number, number, number, number, number, number];
const SEGS: Seg[] = NODES.slice(1).map((q, i) => {
  const p = NODES[i];
  if (p.x === q.x) return [p.x, p.y, p.x + 32, p.y, q.x + 32, q.y, q.x, q.y];
  const mx = (p.x + q.x) / 2;
  return [p.x, p.y, mx, p.y, mx, q.y, q.x, q.y];
});
const segPath = (s: Seg) => `M${s[0]} ${s[1]} C${s[2]} ${s[3]} ${s[4]} ${s[5]} ${s[6]} ${s[7]}`;
function bezier(s: Seg, t: number) {
  const u = 1 - t;
  return [
    u * u * u * s[0] + 3 * u * u * t * s[2] + 3 * u * t * t * s[4] + t * t * t * s[6],
    u * u * u * s[1] + 3 * u * u * t * s[3] + 3 * u * t * t * s[5] + t * t * t * s[7],
  ];
}

const ICONS: Record<string, string> = {
  capture: "M12 4v11M7 10l5 5 5-5M5 19h14",
  store: "M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3zM5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3",
  repair: "M14.5 5.5a4 4 0 0 0-5 5L4 16l4 4 5.5-5.5a4 4 0 0 0 5-5l-2.5 2.5-3-3z",
  clean: "M4 5h16l-6 7v6l-4 2v-8z",
  skills: "M3 12l9-9h8v8l-9 9zM15.5 8.5h.01",
  duplicates: "M8 8h11v11H8zM5 16V5h11",
  tfidf: "M5 20V10M10 20V4M15 20v-7M20 20v-4",
  topics: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5",
  segments: "M7 7m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M17 9m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0M10 17m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  salary: "M12 3v18M16.5 7.5c0-1.7-2-3-4.5-3S7.5 5.8 7.5 7.5 9.5 10 12 10.5s4.5 1.3 4.5 3.2-2 3.3-4.5 3.3-4.5-1.4-4.5-3",
  graph: "M6 6m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M18 7m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M12 18m-2 0a2 2 0 1 0 4 0a2 2 0 1 0-4 0M8 7l8 0M7 8l4 8M17 9l-4 7",
  cv: "M6 3h9l4 4v14H6zM15 3v4h4M9 12h7M9 16h5",
};

export function PipelineMap({ step, onStep }: { step: number; onStep: (i: number) => void }) {
  const dot = useRef<SVGCircleElement>(null);
  const pos = useRef({ t: 0 });

  useEffect(() => {
    const place = () => {
      const t = pos.current.t;
      const i = Math.min(Math.floor(t), SEGS.length - 1);
      const [x, y] = t >= SEGS.length ? [NODES[SEGS.length].x, NODES[SEGS.length].y] : bezier(SEGS[i], t - i);
      dot.current?.setAttribute("cx", String(x));
      dot.current?.setAttribute("cy", String(y));
    };
    if (!window.matchMedia(MOTION_OK).matches) { pos.current.t = step; place(); return; }
    const tween = gsap.to(pos.current, { t: step, duration: 0.5 + Math.abs(pos.current.t - step) * 0.18, ease: "power2.inOut", onUpdate: place });
    return () => { tween.kill(); };
  }, [step]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") { e.preventDefault(); onStep(Math.min(STEPS.length - 1, step + 1)); }
    if (e.key === "ArrowLeft") { e.preventDefault(); onStep(Math.max(0, step - 1)); }
  };

  return (
    <div className="pm-wrap glass" role="tablist" aria-label="Pipeline por capas" onKeyDown={onKey}>
      <svg viewBox={`0 0 ${W} 360`} className="pm">
        {LANES.map((l) => (
          <g key={l.id} className="pm-lane">
            <rect x="0" y={l.y - 30} width={W} height="60" rx="16" fill={l.color} opacity={l.id === "sources" ? 0.05 : 0.09} />
            <text x="18" y={l.y - 8} className="pm-lane-name" fill={l.color}>{l.label.toUpperCase()}</text>
            <text x="18" y={l.y + 8} className="pm-lane-files">{FILES[l.id][0]}</text>
            <text x="18" y={l.y + 20} className="pm-lane-files">{FILES[l.id][1]}</text>
          </g>
        ))}
        {SOURCES.map((s) => (
          <g key={s.label}>
            <path d={`M${s.x} 42 C${s.x} 80 ${NODES[0].x - 40} ${NODES[0].y} ${NODES[0].x} ${NODES[0].y}`} className="pm-seg done" />
            <circle cx={s.x} cy="42" r="11" className="pm-src" />
            <text x={s.x} y="66" textAnchor="middle" className="pm-src-label">{s.label}</text>
          </g>
        ))}
        {SEGS.map((s, i) => <path key={i} d={segPath(s)} className={`pm-seg${i < step ? " done" : ""}`} />)}
        {NODES.map((n, i) => {
          const color = LAYERS[n.layer].color;
          const state = i === step ? "on" : i < step ? "done" : "";
          return (
            <g key={n.key} role="tab" aria-selected={i === step} aria-label={`${i + 1}. ${n.short}`} tabIndex={i === step ? 0 : -1}
              className={`pm-node ${state}`} transform={`translate(${n.x} ${n.y})`} onClick={() => onStep(i)}
              style={{ "--lc": color } as React.CSSProperties}>
              <circle r="21" className="pm-halo" />
              <circle r="17" className="pm-disc" />
              <path d={ICONS[n.key]} transform="translate(-9 -9) scale(0.75)" className="pm-icon" />
              <text y={n.key === "cv" ? 36 : -27} textAnchor="middle" className="pm-label">{n.short}</text>
            </g>
          );
        })}
        <circle ref={dot} r="6" className="pm-dot" cx={NODES[0].x} cy={NODES[0].y} />
      </svg>
    </div>
  );
}
