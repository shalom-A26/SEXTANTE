"use client";

import { useMemo, useRef, useState } from "react";

import { CountUp } from "@/components/motion";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

/** Runs `animate` once the element scrolls into view (skipped with reduced motion). */
function useEntrance<T extends Element>(animate: (q: (selector: string) => Element[], root: T) => void,
  deps: unknown[] = []) {
  const ref = useRef<T>(null);
  useGSAP(() => {
    if (!ref.current) return;
    gsap.matchMedia().add(MOTION_OK, () => animate(gsap.utils.selector(ref), ref.current!));
  }, { dependencies: deps, scope: ref });
  return ref;
}

// Warm-leaning but hue-separated so 8-10 segments stay distinguishable on burgundy.
export const PALETTE = [
  "#f7a24b", "#8fd3c4", "#f27c8c", "#c7b3f5", "#f6d36b", "#7fb6ff", "#ecc0a8", "#a8d98a",
  "#e59ad0", "#b9b0a6",
];

type Bar = { label: string; value: number; hint?: string };

export function BarList({ data, format = (v) => v.toLocaleString("es-CO"), max }: {
  data: Bar[];
  format?: (value: number) => string;
  max?: number;
}) {
  const top = max ?? Math.max(...data.map((d) => d.value), 1);
  const ref = useEntrance<HTMLUListElement>((q, root) => {
    gsap.timeline({ scrollTrigger: { trigger: root, start: "top 90%", once: true } })
      .from(q("li"), { x: -16, opacity: 0, duration: 0.7, stagger: 0.05 })
      .from(q(".barlist-fill"), { scaleX: 0, transformOrigin: "0% 50%", duration: 1.4, stagger: 0.05 }, 0.1);
  }, [data]);
  return (
    <ul className="barlist" ref={ref}>
      {data.map((d) => {
        const row = (
          <li key={d.label}>
            <span className="barlist-label">{d.label}</span>
            <span className="barlist-track">
              <span className="barlist-fill" style={{ width: `${(100 * d.value) / top}%` }} />
            </span>
            <span className="barlist-value"><CountUp value={d.value} format={format} duration={1.4} /></span>
          </li>
        );
        return d.hint ? (
          <Tooltip key={d.label}>
            <TooltipTrigger asChild>{row}</TooltipTrigger>
            <TooltipContent side="top">{d.label}: {d.hint}</TooltipContent>
          </Tooltip>
        ) : row;
      })}
    </ul>
  );
}

export function Scatter({ points, names }: {
  points: { component_1: number; component_2: number; cluster_id: number }[];
  names: Record<number, string>;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const { scaled, clusters } = useMemo(() => {
    const xs = points.map((p) => p.component_1);
    const ys = points.map((p) => p.component_2);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    return {
      scaled: points.map((p) => ({
        x: 20 + (560 * (p.component_1 - x0)) / (x1 - x0 || 1),
        y: 340 - (320 * (p.component_2 - y0)) / (y1 - y0 || 1),
        c: p.cluster_id,
      })),
      clusters: [...new Set(points.map((p) => p.cluster_id))].sort((a, b) => a - b),
    };
  }, [points]);
  const ref = useEntrance<HTMLDivElement>((q, root) => {
    gsap.from(q("circle"), {
      scale: 0, opacity: 0, transformOrigin: "50% 50%", duration: 0.9, ease: "back.out(2.5)",
      stagger: { amount: 1.6, from: "random" },
      scrollTrigger: { trigger: root, start: "top 85%", once: true },
    });
    gsap.from(q(".legend button"), {
      y: 10, opacity: 0, stagger: 0.05, duration: 0.6,
      scrollTrigger: { trigger: root, start: "top 85%", once: true },
    });
  }, [points]);
  return (
    <div ref={ref}>
      <svg viewBox="0 0 600 360" className="chart" role="img" aria-label="Proyección 2D de vacantes por segmento">
        {scaled.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={hover === null || hover === p.c ? 3 : 2}
            fill={PALETTE[p.c % PALETTE.length]} fillOpacity={hover === null || hover === p.c ? 0.75 : 0.12}
            style={{ transition: "r 0.3s, fill-opacity 0.3s" }} />
        ))}
      </svg>
      <div className="legend">
        {clusters.map((c) => (
          <button key={c} onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(c)} onBlur={() => setHover(null)}>
            <i style={{ background: PALETTE[c % PALETTE.length] }} />{names[c] ?? `Segmento ${c}`}
          </button>
        ))}
      </div>
    </div>
  );
}

type GraphNode = { esco_uri: string; skill_label: string; postings: number; pagerank: number; community: number };

export function SkillGraph({ nodes, edges }: {
  nodes: GraphNode[];
  edges: { source: string; target: string; weight: number }[];
}) {
  const [focus, setFocus] = useState<string | null>(null);
  const layout = useMemo(() => {
    const communities = [...new Set(nodes.map((n) => n.community))];
    const position: Record<string, { x: number; y: number }> = {};
    communities.forEach((community, ci) => {
      const members = nodes.filter((n) => n.community === community);
      const angle = (2 * Math.PI * ci) / communities.length;
      const cx = 360 + 220 * Math.cos(angle);
      const cy = 260 + 170 * Math.sin(angle);
      const radius = 18 + 9 * Math.sqrt(members.length);
      members.forEach((n, mi) => {
        const a = (2 * Math.PI * mi) / members.length;
        position[n.esco_uri] = { x: cx + radius * Math.cos(a), y: cy + radius * Math.sin(a) };
      });
    });
    return position;
  }, [nodes]);
  const maxRank = Math.max(...nodes.map((n) => n.pagerank), 1e-9);
  const maxWeight = Math.max(...edges.map((e) => e.weight), 1);
  const neighbours = new Set(
    focus ? edges.flatMap((e) => (e.source === focus ? [e.target] : e.target === focus ? [e.source] : [])) : [],
  );
  const ref = useEntrance<SVGSVGElement>((q, root) => {
    gsap.timeline({ scrollTrigger: { trigger: root, start: "top 80%", once: true } })
      .from(q(".edge"), { drawSVG: 0, duration: 1.6, stagger: { amount: 1.2, from: "random" }, ease: "power2.inOut" })
      .from(q(".node circle"), {
        scale: 0, transformOrigin: "50% 50%", duration: 0.8, ease: "back.out(3)", stagger: { amount: 1, from: "center" },
      }, 0.3)
      .from(q(".node-label"), { opacity: 0, y: 6, duration: 0.6, stagger: 0.02 }, 1.1);
  }, [nodes]);
  return (
    <svg viewBox="0 0 720 520" className="chart" role="img" aria-label="Grafo de co-ocurrencia de habilidades" ref={ref}>
      {edges.map((e, i) => {
        const a = layout[e.source];
        const b = layout[e.target];
        if (!a || !b) return null;
        const active = !focus || e.source === focus || e.target === focus;
        return <line key={i} className="edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#ecc0a8"
          strokeWidth={0.4 + (2 * e.weight) / maxWeight} strokeOpacity={active ? 0.35 : 0.04}
          style={{ transition: "stroke-opacity 0.3s" }} />;
      })}
      {nodes.map((n) => {
        const p = layout[n.esco_uri];
        const active = !focus || focus === n.esco_uri || neighbours.has(n.esco_uri);
        const r = 4 + 10 * Math.sqrt(n.pagerank / maxRank);
        return (
          <g key={n.esco_uri} className="node" onMouseEnter={() => setFocus(n.esco_uri)}
            onMouseLeave={() => setFocus(null)} fillOpacity={active ? 1 : 0.2}
            style={{ cursor: "pointer", transition: "fill-opacity 0.3s" }}>
            <circle cx={p.x} cy={p.y} r={r} fill={PALETTE[n.community % PALETTE.length]} />
            {(r > 8 || focus === n.esco_uri || neighbours.has(n.esco_uri)) && (
              <text x={p.x} y={p.y - r - 3} textAnchor="middle" className="node-label">{n.skill_label}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function Meter({ value, label }: { value: number; label?: string }) {
  const tone = value >= 70 ? "good" : value >= 45 ? "mid" : "low";
  const ref = useEntrance<HTMLSpanElement>((q, root) => {
    gsap.from(q(".meter-fill"), {
      scaleX: 0, transformOrigin: "0% 50%", duration: 1.5, ease: "power3.out",
      scrollTrigger: { trigger: root, start: "top 95%", once: true },
    });
  }, [value]);
  return (
    <span className={`meter meter-${tone}`} aria-label={label ?? `${value}%`} ref={ref}>
      <span className="meter-fill" style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
      <b><CountUp value={value} format={(v) => `${v.toFixed(0)}%`} duration={1.5} /></b>
    </span>
  );
}
