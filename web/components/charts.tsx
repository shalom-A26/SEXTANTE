"use client";

import { useMemo, useState } from "react";

export const PALETTE = [
  "#2f6fde", "#e0892b", "#1f9e89", "#c4455d", "#7b5cc4", "#5b8c2a", "#b8742e", "#3a8fb7",
  "#d4609a", "#6b7a8f",
];

type Bar = { label: string; value: number; hint?: string };

export function BarList({ data, format = (v) => v.toLocaleString("es-CO"), max }: {
  data: Bar[];
  format?: (value: number) => string;
  max?: number;
}) {
  const top = max ?? Math.max(...data.map((d) => d.value), 1);
  return (
    <ul className="barlist">
      {data.map((d) => (
        <li key={d.label} title={d.hint}>
          <span className="barlist-label">{d.label}</span>
          <span className="barlist-track">
            <span className="barlist-fill" style={{ width: `${(100 * d.value) / top}%` }} />
          </span>
          <span className="barlist-value">{format(d.value)}</span>
        </li>
      ))}
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
  return (
    <div>
      <svg viewBox="0 0 600 360" className="chart" role="img" aria-label="Proyección 2D de vacantes por segmento">
        {scaled.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={hover === null || hover === p.c ? 3 : 2}
            fill={PALETTE[p.c % PALETTE.length]} opacity={hover === null || hover === p.c ? 0.75 : 0.12} />
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
  return (
    <svg viewBox="0 0 720 520" className="chart" role="img" aria-label="Grafo de co-ocurrencia de habilidades">
      {edges.map((e, i) => {
        const a = layout[e.source];
        const b = layout[e.target];
        if (!a || !b) return null;
        const active = !focus || e.source === focus || e.target === focus;
        return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#8a94a6"
          strokeWidth={0.4 + (2 * e.weight) / maxWeight} opacity={active ? 0.35 : 0.04} />;
      })}
      {nodes.map((n) => {
        const p = layout[n.esco_uri];
        const active = !focus || focus === n.esco_uri || neighbours.has(n.esco_uri);
        const r = 4 + 10 * Math.sqrt(n.pagerank / maxRank);
        return (
          <g key={n.esco_uri} onMouseEnter={() => setFocus(n.esco_uri)} onMouseLeave={() => setFocus(null)}
            opacity={active ? 1 : 0.2} style={{ cursor: "pointer" }}>
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
  return (
    <span className={`meter meter-${tone}`} aria-label={label ?? `${value}%`}>
      <span style={{ width: `${Math.max(2, Math.min(100, value))}%` }} />
      <b>{value.toFixed(0)}%</b>
    </span>
  );
}
