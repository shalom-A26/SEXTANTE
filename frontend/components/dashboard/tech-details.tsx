"use client";

import { Fragment } from "react";

import { CountUp } from "@/components/motion";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { pct, type Dashboard } from "@/lib/api";

/** Technical detail kept at the bottom of a tab and collapsed: it matters to reviewers, not to the first read. */
export function TechDetails({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Accordion type="single" collapsible className="tech-details panel">
      <AccordionItem value="detail">
        <AccordionTrigger className="segment-trigger"><strong>{title}</strong></AccordionTrigger>
        <AccordionContent>{children}</AccordionContent>
      </AccordionItem>
    </Accordion>
  );
}

export function ModelCard({ models }: { models: Dashboard["salaries"]["models"] }) {
  const c = models.classification;
  if (models.skipped || !c || c.skipped || c.within_one_band == null) {
    return <p className="muted">{models.skipped ?? c?.skipped ?? "Sin modelo."}</p>;
  }
  return (
    <>
      <p className="muted">Clasificación del rango a partir del texto; validación cruzada contra la clase mayoritaria</p>
      <dl className="model">
        <dt>F1 macro</dt><dd><CountUp value={c.macro_f1} format={(v) => v.toFixed(2)} /> <small>vs {c.baseline_majority_macro_f1.toFixed(2)} clase mayoritaria</small></dd>
        <dt>Exactitud</dt><dd>{pct(c.accuracy)} <small>vs {pct(c.baseline_majority_accuracy)} clase mayoritaria</small></dd>
        <dt>Acierta el rango o el vecino</dt><dd>{pct(c.within_one_band)} <small>vs {pct(c.baseline_within_one_band)}</small></dd>
        <dt>Vacantes con rango publicado</dt><dd>{models.labeled_rows?.toLocaleString("es-CO")}</dd>
      </dl>
    </>
  );
}

export function ClusteringTable({ methods }: { methods?: Dashboard["clustering_comparison"]["methods"] }) {
  if (!methods) return null;
  return (
    <table className="table">
      <caption>Comparación de métodos de agrupamiento (muestra)</caption>
      <thead><tr><th>Método</th><th>Grupos</th><th>Silueta</th><th>Ruido</th></tr></thead>
      <tbody>
        {Object.entries(methods).map(([name, m]) => (
          <tr key={name}><td>{name}</td><td>{m.clusters}</td><td>{m.silhouette_cosine?.toFixed(2) ?? "—"}</td><td>{pct(m.noise_share)}</td></tr>
        ))}
      </tbody>
    </table>
  );
}

const fixed = (digits: number) => (v: number) => v.toFixed(digits);

// Rows of the skills-graph metrics; a key the run did not produce is left out, never shown as 0.
const GRAPH_METRICS: [key: string, label: string, format: (v: number) => string][] = [
  ["skill_nodes", "Habilidades (nodos)", (v) => v.toLocaleString("es-CO")],
  ["skill_edges", "Conexiones (aristas)", (v) => v.toLocaleString("es-CO")],
  ["density", "Densidad", fixed(3)],
  ["average_degree", "Grado promedio", fixed(1)],
  ["average_clustering", "Coeficiente de agrupamiento promedio", fixed(2)],
  ["skill_modularity", "Modularidad (Louvain)", fixed(2)],
  ["skill_communities", "Comunidades", (v) => v.toLocaleString("es-CO")],
];

/** `omit`: keys already shown elsewhere on the tab (e.g. the community-structure panel), so no number appears twice. */
export function GraphMetrics({ metrics, omit = [] }: { metrics: Dashboard["graph"]["metrics"]; omit?: string[] }) {
  const rows = GRAPH_METRICS.flatMap(([key, label, format]) => {
    const v = metrics?.[key];
    return v == null || omit.includes(key) ? [] : [{ key, label, value: format(v) }];
  });
  if (!rows.length) return <p className="muted">Esta corrida no incluye métricas del grafo.</p>;
  return (
    <>
      <p className="muted">Grafo de co-ocurrencia: dos habilidades se conectan si aparecen en las mismas vacantes. {omit.includes("density") ? "" : " Densidad = fracción de conexiones posibles que existen;"} Grado = conexiones por habilidad; modularidad = qué tan separadas quedan las comunidades (Louvain).{omit.length > 0 && " Densidad y agrupamiento promedio se muestran en «Estructura comunitaria»."}</p>
      <dl className="model">
        {rows.map((r) => <Fragment key={r.key}><dt>{r.label}</dt><dd>{r.value}</dd></Fragment>)}
      </dl>
    </>
  );
}
