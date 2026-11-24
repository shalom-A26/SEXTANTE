"use client";

import { useState } from "react";

import { pct, type SkillKind, type SkillMetrics } from "@/lib/api";
import { formatCount, formatTimes } from "@/lib/skills";
import { TechDetails } from "./tech-details";

type Key = "skill_label" | "share" | "degree" | "weighted_degree" | "betweenness" | "pagerank" | "community" | "kind";

const fixed = (digits: number) => (v: number) => v.toFixed(digits);
const KIND_LABEL: Record<SkillKind, string> = { transversal: "Transversal", intermedia: "Intermedia", especializada: "Especializada" };

const COLUMNS: { key: Key; label: string; format?: (v: number) => string }[] = [
  { key: "skill_label", label: "Habilidad" },
  { key: "share", label: "Frecuencia", format: pct },
  { key: "degree", label: "Grado", format: formatCount },
  { key: "weighted_degree", label: "Grado ponderado", format: formatTimes },
  { key: "betweenness", label: "Intermediación", format: fixed(3) },
  { key: "pagerank", label: "PageRank", format: fixed(4) },
  { key: "community", label: "Comunidad", format: String },
  { key: "kind", label: "Tipo" },
];

/** Full centrality metrics of the 30 most requested skills; click a header to sort by it. */
export function CentralityTable({ table }: { table?: SkillMetrics[] }) {
  const [sort, setSort] = useState<{ key: Key; desc: boolean }>({ key: "share", desc: true });
  if (!table?.length) return null;
  const rows = [...table].sort((a, b) => {
    const x = a[sort.key];
    const y = b[sort.key];
    const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), "es");
    return sort.desc ? -order : order;
  });
  const toggle = (key: Key) =>
    setSort((s) => (s.key === key ? { key, desc: !s.desc } : { key, desc: key !== "skill_label" && key !== "kind" }));
  return (
    <TechDetails title="Detalle técnico: métricas de centralidad">
      <p className="muted">
        Las 30 habilidades más frecuentes en el grafo de co-ocurrencia. Frecuencia = % de vacantes que la piden; grado = habilidades
        distintas con las que aparece; grado ponderado = total de co-apariciones; intermediación = qué tanto está en el camino
        entre grupos (puente); PageRank = conexión con otras habilidades centrales (núcleo); comunidad = grupo Louvain.
      </p>
      <table className="table sort-table">
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} aria-sort={sort.key === c.key ? (sort.desc ? "descending" : "ascending") : "none"}>
                <button type="button" onClick={() => toggle(c.key)}>
                  {c.label}{sort.key === c.key ? (sort.desc ? " ↓" : " ↑") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.esco_uri}>
              {COLUMNS.map((c) => {
                const v = r[c.key];
                const text = c.key === "kind" ? KIND_LABEL[r.kind] ?? r.kind
                  : typeof v === "number" && c.format ? c.format(v) : String(v ?? "—");
                return <td key={c.key}>{text}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </TechDetails>
  );
}
