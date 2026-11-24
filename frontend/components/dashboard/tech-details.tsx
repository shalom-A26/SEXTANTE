"use client";

import { Fragment } from "react";

import { BarList } from "@/components/charts";
import { CountUp } from "@/components/motion";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { pct, type Dashboard } from "@/lib/api";
import { shareOfTotalBars } from "@/lib/dashboard";

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

const num = (v: number | null | undefined) => (v == null ? "—" : v.toLocaleString("es-CO"));

export function CorpusDetails({ overview: o }: { overview: Dashboard["overview"] }) {
  const perPosting = o.skill_mentions != null && o.postings ? o.skill_mentions / o.postings : null;
  return (
    <>
      <p className="muted">Cifras de la última corrida del análisis. Los duplicados y las habilidades son señales automáticas aún sin validar.</p>
      <dl className="model">
        <dt>Menciones de habilidades ESCO</dt>
        <dd>{num(o.skill_mentions)} {perPosting !== null && <small>≈ {perPosting.toFixed(1)} por vacante, en promedio</small>}</dd>
        <dt>Pares de vacantes casi duplicadas</dt><dd>{num(o.duplicate_candidates)}</dd>
        <dt>Vacantes en algún par duplicado</dt>
        <dd>{num(o.duplicate_postings)} {o.duplicate_postings != null && o.postings > 0 && <small>{pct(o.duplicate_postings / o.postings)} de {num(o.postings)}</small>}</dd>
        <dt>Grupos de duplicados</dt><dd>{num(o.duplicate_groups)}</dd>
      </dl>
    </>
  );
}

export function SourceDetails({ overview: o }: { overview: Dashboard["overview"] }) {
  if (!o.sources?.length) return null;
  return (
    <div className="tech-block">
      <h4>Fuente de las vacantes</h4>
      <p className="muted">% de vacantes por fuente de captura (n={num(o.postings)}); lo que ves depende de lo que cada fuente publica.</p>
      <BarList data={shareOfTotalBars(o.sources, o.postings)} unit="percent" />
    </div>
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

export function GraphMetrics({ metrics }: { metrics: Dashboard["graph"]["metrics"] }) {
  const rows = GRAPH_METRICS.flatMap(([key, label, format]) => {
    const v = metrics?.[key];
    return v == null ? [] : [{ key, label, value: format(v) }];
  });
  if (!rows.length) return <p className="muted">Esta corrida no incluye métricas del grafo.</p>;
  return (
    <>
      <p className="muted">Grafo de co-ocurrencia: dos habilidades se conectan si aparecen en las mismas vacantes. Densidad = fracción de conexiones posibles que existen; grado = conexiones por habilidad; modularidad = qué tan separadas quedan las comunidades.</p>
      <dl className="model">
        {rows.map((r) => <Fragment key={r.key}><dt>{r.label}</dt><dd>{r.value}</dd></Fragment>)}
      </dl>
    </>
  );
}
