"use client";

import { useMemo, useRef, useState, type KeyboardEvent } from "react";

import { CountUp } from "@/components/motion";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { pct, type GraphCommunity } from "@/lib/api";
import { communityLegend, extent, type Bar } from "@/lib/dashboard";

/**
 * Runs `animate` once the element scrolls into view (skipped with reduced motion).
 * `deps` is the only trigger for replaying it: pass a stable value (an id or signature), not a fresh array.
 */
function useEntrance<T extends Element>(animate: (q: (selector: string) => Element[], root: T) => void,
  deps: unknown[] = []) {
  const ref = useRef<T>(null);
  useGSAP(() => {
    if (!ref.current) return;
    gsap.matchMedia().add(MOTION_OK, () => animate(gsap.utils.selector(ref), ref.current!));
  }, { dependencies: deps, scope: ref });
  return ref;
}

// Warm-leaning but hue-separated so 8-10 segments stay distinguishable on cream.
export const PALETTE = [
  "#e0761b", "#2f8f7f", "#c8445a", "#6f55c4", "#b8860b", "#2f6fbf", "#a3542e", "#5a8f2e",
  "#a8437f", "#7a6f66",
];

/** Colour for group `index`. Past the 10 base colours each lap is lightened, so a repeat is visibly a second round. */
export function colorFor(index: number): string {
  const i = Math.abs(Math.trunc(index));
  const base = PALETTE[i % PALETTE.length];
  const lap = Math.floor(i / PALETTE.length);
  if (!lap) return base;
  const mix = Math.min(0.7, 0.35 * lap);
  const channel = (k: number) => {
    const c = parseInt(base.slice(1 + 2 * k, 3 + 2 * k), 16);
    return Math.round(c + (255 - c) * mix).toString(16).padStart(2, "0");
  };
  return `#${channel(0)}${channel(1)}${channel(2)}`;
}

/**
 * `percent`: values are 0..1 shares, drawn on a fixed 0-100% scale (comparable across panels).
 * `count`: values are counts, drawn relative to the largest row.
 * `relative`: drawn relative to the largest row with no number (for scores whose raw value means little to readers).
 */
export function BarList({ data, unit = "count" }: { data: Bar[]; unit?: "percent" | "count" | "relative" }) {
  const format = unit === "percent" ? pct : unit === "relative" ? () => "" : (v: number) => v.toLocaleString("es-CO");
  const top = unit === "percent" ? 1 : unit === "relative" ? Math.max(extent(data.map((d) => d.value))?.[1] ?? 0, 1e-12) : Math.max(extent(data.map((d) => d.value))?.[1] ?? 0, 1);
  // Stable signature: a fresh array with the same rows must not replay the entrance animation.
  const signature = data.map((d) => `${d.label}:${d.value}`).join("|");
  const ref = useEntrance<HTMLUListElement>((q, root) => {
    gsap.timeline({ scrollTrigger: { trigger: root, start: "top 90%", once: true } })
      .from(q("li"), { x: -16, opacity: 0, duration: 0.7, stagger: 0.05 })
      .from(q(".barlist-fill"), { scaleX: 0, transformOrigin: "0% 50%", duration: 1.4, stagger: 0.05 }, 0.1);
  }, [signature]);
  return (
    <ul className={unit === "relative" ? "barlist barlist-bare" : "barlist"} ref={ref}>
      {data.map((d) => <BarRow key={d.label} bar={d} top={top} format={unit === "relative" ? null : format} />)}
    </ul>
  );
}

function BarRow({ bar: d, top, format }: { bar: Bar; top: number; format: ((v: number) => string) | null }) {
  const [open, setOpen] = useState(false);
  const row = (
    <li tabIndex={d.hint ? 0 : undefined} className={d.hint ? "barlist-row has-hint" : "barlist-row"}
      aria-label={d.hint ? `${d.label}${format ? `: ${format(d.value)}` : ""}. ${d.hint}` : undefined}
      onClick={d.hint ? () => setOpen((o) => !o) : undefined}>
      <span className="barlist-label">{d.label}</span>
      <span className="barlist-track">
        <span className="barlist-fill" style={{ width: `${Math.min(100, (100 * d.value) / top)}%` }} />
      </span>
      {format && <span className="barlist-value"><CountUp value={d.value} format={format} duration={1.4} /></span>}
    </li>
  );
  if (!d.hint) return row;
  // Controlled so the detail opens on hover, keyboard focus and tap alike.
  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger asChild>{row}</TooltipTrigger>
      <TooltipContent side="top">{d.label}: {d.hint}</TooltipContent>
    </Tooltip>
  );
}

export function Scatter({ points, names }: {
  points: { component_1: number; component_2: number; cluster_id: number }[];
  names: Record<number, string>;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const [pinned, setPinned] = useState<number | null>(null);
  const active = hover ?? pinned;
  const { scaled, clusters } = useMemo(() => {
    const [x0, x1] = extent(points.map((p) => p.component_1)) ?? [0, 1];
    const [y0, y1] = extent(points.map((p) => p.component_2)) ?? [0, 1];
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
      <svg viewBox="0 0 600 360" className="chart" role="img"
        aria-label={`Proyección 2D de ${points.length.toLocaleString("es-CO")} vacantes en ${clusters.length} segmentos. Usa la leyenda para resaltar un segmento.`}>
        {scaled.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={active === null || active === p.c ? 3 : 2}
            fill={colorFor(p.c)} fillOpacity={active === null || active === p.c ? 0.75 : 0.12}
            style={{ transition: "r 0.3s, fill-opacity 0.3s" }} />
        ))}
      </svg>
      <div className="legend">
        {clusters.map((c) => (
          <button key={c} type="button" aria-pressed={pinned === c}
            onClick={() => setPinned((p) => (p === c ? null : c))}
            onMouseEnter={() => setHover(c)} onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(c)} onBlur={() => setHover(null)}>
            <i style={{ background: colorFor(c) }} />{names[c] ?? `Segmento ${c}`}
          </button>
        ))}
      </div>
    </div>
  );
}

type GraphNode = { esco_uri: string; skill_label: string; postings: number; pagerank: number; betweenness?: number; community: number };

export function SkillGraph({ nodes, edges, communities }: {
  nodes: GraphNode[];
  edges: { source: string; target: string; weight: number }[];
  communities?: GraphCommunity[];
}) {
  const legend = useMemo(() => communityLegend(nodes, communities), [nodes, communities]);
  return (
    <div>
      <SkillGraphCanvas nodes={nodes} edges={edges} />
      {legend.length > 0 && (
        <ul className="legend graph-legend" aria-label="Comunidades del grafo, nombradas por sus habilidades principales">
          {legend.map((c) => (
            <li key={c.community}>
              <i style={{ background: colorFor(c.community) }} />
              <span>{c.top_skills.join(", ")} <small>({c.size.toLocaleString("es-CO")} habilidades)</small></span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SkillGraphCanvas({ nodes, edges }: {
  nodes: GraphNode[];
  edges: { source: string; target: string; weight: number }[];
}) {
  const [hover, setHover] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const focus = hover ?? pinned;
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
    return { position, communities: communities.length };
  }, [nodes]);
  const degree = useMemo(() => {
    const d: Record<string, number> = {};
    for (const e of edges) {
      d[e.source] = (d[e.source] ?? 0) + 1;
      d[e.target] = (d[e.target] ?? 0) + 1;
    }
    return d;
  }, [edges]);
  const maxRank = Math.max(extent(nodes.map((n) => n.pagerank))?.[1] ?? 0, 1e-9);
  const maxWeight = Math.max(extent(edges.map((e) => e.weight))?.[1] ?? 0, 1);
  const neighbours = new Set(
    focus ? edges.flatMap((e) => (e.source === focus ? [e.target] : e.target === focus ? [e.source] : [])) : [],
  );
  // Keyboard order follows the layout (community by community), so arrows walk neighbouring nodes.
  const order = useMemo(() => [...nodes].sort((x, y) => x.community - y.community).map((n) => n.esco_uri), [nodes]);
  const nodeRefs = useRef<Record<string, SVGGElement | null>>({});
  // Roving tabindex: one tab stop for the whole graph, arrows move between nodes.
  const [lastFocused, setLastFocused] = useState<string | null>(null);
  const tabStop = order.includes(pinned ?? "") ? pinned : order.includes(lastFocused ?? "") ? lastFocused : order[0];
  const moveFocus = (from: string, key: string) => {
    const i = order.indexOf(from);
    const next = key === "ArrowRight" || key === "ArrowDown" ? (i + 1) % order.length
      : key === "ArrowLeft" || key === "ArrowUp" ? (i - 1 + order.length) % order.length
      : key === "Home" ? 0 : key === "End" ? order.length - 1 : -1;
    if (next >= 0) nodeRefs.current[order[next]]?.focus();
    return next >= 0;
  };
  // Labels: the focused node and its neighbours always show; the rest are greedy by size and skip collisions.
  const labelled = useMemo(() => {
    const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
    const shown = new Set<string>();
    const byUri = new Map(nodes.map((n) => [n.esco_uri, n]));
    const boxOf = (n: GraphNode) => {
      const p = layout.position[n.esco_uri];
      const r = 4 + 10 * Math.sqrt(n.pagerank / maxRank);
      const half = (n.skill_label.length * 5.4) / 2;
      return { x0: p.x - half, x1: p.x + half, y0: p.y - r - 14, y1: p.y - r };
    };
    const hits = (b: { x0: number; x1: number; y0: number; y1: number }) =>
      placed.some((o) => b.x0 < o.x1 && b.x1 > o.x0 && b.y0 < o.y1 && b.y1 > o.y0);
    const add = (n: GraphNode, force: boolean) => {
      const b = boxOf(n);
      if (!force && hits(b)) return;
      placed.push(b);
      shown.add(n.esco_uri);
    };
    const near = new Set(
      focus ? edges.flatMap((e) => (e.source === focus ? [e.target] : e.target === focus ? [e.source] : [])) : [],
    );
    if (focus && byUri.has(focus)) add(byUri.get(focus)!, true);
    for (const uri of near) if (byUri.has(uri)) add(byUri.get(uri)!, true);
    [...nodes].sort((x, y) => y.pagerank - x.pagerank).forEach((n) => {
      if (!shown.has(n.esco_uri) && 4 + 10 * Math.sqrt(n.pagerank / maxRank) > 8) add(n, false);
    });
    return shown;
  }, [nodes, layout.position, maxRank, focus, edges]);
  const ref = useEntrance<SVGSVGElement>((q, root) => {
    gsap.timeline({ scrollTrigger: { trigger: root, start: "top 80%", once: true } })
      .from(q(".edge"), { drawSVG: 0, duration: 1.6, stagger: { amount: 1.2, from: "random" }, ease: "power2.inOut" })
      .from(q(".node circle"), {
        scale: 0, transformOrigin: "50% 50%", duration: 0.8, ease: "back.out(3)", stagger: { amount: 1, from: "center" },
      }, 0.3)
      .from(q(".node-label"), { opacity: 0, y: 6, duration: 0.6, stagger: 0.02 }, 1.1);
  }, [nodes]);
  return (
    <svg viewBox="0 0 720 520" className="chart" role="group" ref={ref}
      aria-label={`Grafo de co-ocurrencia de ${nodes.length} habilidades en ${layout.communities} comunidades. Cada nodo es un botón: las flechas pasan de uno a otro, Enter o espacio lo fija.`}>
      {edges.map((e, i) => {
        const a = layout.position[e.source];
        const b = layout.position[e.target];
        if (!a || !b) return null;
        const active = !focus || e.source === focus || e.target === focus;
        return <line key={i} className="edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} strokeWidth={0.4 + (2 * e.weight) / maxWeight} strokeOpacity={active ? 0.35 : 0.04}
          style={{ transition: "stroke-opacity 0.3s" }} />;
      })}
      {nodes.map((n) => {
        const p = layout.position[n.esco_uri];
        const active = !focus || focus === n.esco_uri || neighbours.has(n.esco_uri);
        const r = 4 + 10 * Math.sqrt(n.pagerank / maxRank);
        const toggle = () => setPinned((cur) => (cur === n.esco_uri ? null : n.esco_uri));
        return (
          <g key={n.esco_uri} className="node" tabIndex={n.esco_uri === tabStop ? 0 : -1} role="button"
            ref={(el) => { nodeRefs.current[n.esco_uri] = el; }} aria-pressed={pinned === n.esco_uri}
            aria-label={`${n.skill_label}: ${n.postings.toLocaleString("es-CO")} vacantes, ${degree[n.esco_uri] ?? 0} conexiones${n.betweenness != null ? `, intermediación ${n.betweenness.toFixed(3)} (qué tanto une grupos de habilidades)` : ""}`}
            onMouseEnter={() => setHover(n.esco_uri)} onMouseLeave={() => setHover(null)}
            onFocus={() => { setHover(n.esco_uri); setLastFocused(n.esco_uri); }} onBlur={() => setHover(null)}
            onClick={toggle}
            onKeyDown={(e: KeyboardEvent<SVGGElement>) => {
              if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); }
              else if (moveFocus(n.esco_uri, e.key)) e.preventDefault();
            }}
            fillOpacity={active ? 1 : 0.2}
            style={{ cursor: "pointer", transition: "fill-opacity 0.3s" }}>
            <circle cx={p.x} cy={p.y} r={r} fill={colorFor(n.community)} />
            {labelled.has(n.esco_uri) && (
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
