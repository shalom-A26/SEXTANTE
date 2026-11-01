"use client";

import { useEffect, useMemo, useState } from "react";

import { BarList, Scatter, SkillGraph } from "@/components/charts";
import { cop, getDashboard, pct, type Dashboard } from "@/lib/api";

const TABS = ["Candidatos", "Empleadores", "Programas académicos", "Mapa del mercado"] as const;
type Tab = (typeof TABS)[number];

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Candidatos");

  useEffect(() => {
    getDashboard().then(setData).catch((e: Error) => setError(e.message));
  }, []);

  const names = useMemo(
    () => Object.fromEntries((data?.segments ?? []).map((s) => [s.id, s.name])) as Record<number, string>,
    [data],
  );

  if (error) return <div className="notice error">No se pudo cargar el API ({error}). ¿Está corriendo en {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}?</div>;
  if (!data) return <div className="notice">Cargando datos…</div>;
  const o = data.overview;

  return (
    <div className="dashboard">
      {data.run.synthetic && (
        <div className="notice warn">Datos sintéticos de demostración: ejecuta el análisis sobre el corpus real para ver cifras reales.</div>
      )}
      <section className="kpis">
        <Kpi label="Vacantes analizadas" value={o.postings.toLocaleString("es-CO")} />
        <Kpi label="Segmentos ocupacionales" value={String(o.segments)} />
        <Kpi label="Habilidades ESCO detectadas" value={o.skills_detected.toLocaleString("es-CO")} />
        <Kpi label="Salario mediano" value={cop(data.salaries.overall.median)} hint={`${o.with_salary.toLocaleString("es-CO")} vacantes con salario`} />
      </section>

      <div className="tabs" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </div>

      {tab === "Candidatos" && (
        <div className="grid-2">
          <Panel title="Habilidades más pedidas" note="% de vacantes que la mencionan">
            <BarList data={data.top_skills.slice(0, 15).map((s) => ({ label: s.skill, value: s.share }))} format={pct} />
          </Panel>
          <Panel title="Segmentos ocupacionales" note="Salario mediano y habilidades distintivas">
            <div className="segment-list">
              {data.segments.map((s) => (
                <details key={s.id}>
                  <summary>
                    <strong>{s.name}</strong>
                    <span>{s.postings.toLocaleString("es-CO")} vacantes · {cop(s.salary.median)}</span>
                  </summary>
                  <p className="chips">{s.top_skills.map((k) => <span key={k.skill}>{k.skill} · {pct(k.share)}</span>)}</p>
                  <p className="muted">Términos: {s.terms.join(", ")}</p>
                </details>
              ))}
            </div>
          </Panel>
        </div>
      )}

      {tab === "Empleadores" && (
        <div className="grid-2">
          <Panel title="Salario por segmento" note="Mediana mensual (COP); rango intercuartílico al pasar el cursor">
            <BarList
              data={data.segments.filter((s) => s.salary.median).map((s) => ({
                label: s.name, value: s.salary.median ?? 0, hint: `P25 ${cop(s.salary.p25)} · P75 ${cop(s.salary.p75)} · n=${s.salary.n}`,
              }))}
              format={(v) => cop(v)}
            />
          </Panel>
          <Panel title="Salario por departamento" note="Departamentos con 3+ vacantes con salario">
            <BarList data={data.salaries.by_department.map((d) => ({ label: d.department, value: d.median ?? 0, hint: `n=${d.n}` }))} format={(v) => cop(v)} />
          </Panel>
          <Panel title="Modalidad de trabajo">
            <BarList data={o.modality.map((c) => ({ label: c.label, value: c.count }))} />
          </Panel>
          <Panel title="Tipo de contrato">
            <BarList data={o.contracts.map((c) => ({ label: c.label, value: c.count }))} />
          </Panel>
          <Panel title="Ciudades con más vacantes">
            <BarList data={o.cities.map((c) => ({ label: c.label, value: c.count }))} />
          </Panel>
          <Panel title="Modelo de estimación salarial" note="Validación cruzada contra una línea base ingenua">
            <ModelCard models={data.salaries.models} />
          </Panel>
        </div>
      )}

      {tab === "Programas académicos" && (
        <div className="grid-2">
          {data.education_skills.map((e) => (
            <Panel key={e.education} title={e.education} note={`${e.postings.toLocaleString("es-CO")} vacantes · habilidades más pedidas`}>
              <BarList data={e.skills.map((s) => ({ label: s.skill, value: s.count }))} />
            </Panel>
          ))}
        </div>
      )}

      {tab === "Mapa del mercado" && (
        <div className="grid-1">
          <Panel title="Grafo de habilidades" note={`Habilidades que aparecen juntas en las mismas vacantes; color = comunidad (Louvain, modularidad ${data.graph.metrics.skill_modularity?.toFixed(2) ?? "—"}); tamaño = PageRank. Pasa el cursor sobre un nodo.`}>
            <SkillGraph nodes={data.graph.nodes} edges={data.graph.edges} />
          </Panel>
          <div className="grid-2">
            <Panel title="Proyección de vacantes" note="TF-IDF reducido a 2D (SVD), color = segmento">
              <Scatter points={data.projection} names={names} />
            </Panel>
            <Panel title="Ocupaciones vecinas" note="Segmentos con perfiles de habilidades similares: rutas de transición">
              <BarList
                data={data.graph.segment_links.sort((a, b) => b.similarity - a.similarity).slice(0, 12).map((l) => ({
                  label: `${names[l.from]} ↔ ${names[l.to]}`, value: l.similarity,
                }))}
                format={pct} max={1}
              />
              <ClusteringTable methods={data.clustering_comparison.methods} />
            </Panel>
          </div>
        </div>
      )}
      <p className="muted run-id">Corrida {data.run.run_id} · corpus {data.run.corpus}</p>
    </div>
  );
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}

function Panel({ title, note, children }: { title: string; note?: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <h3>{title}</h3>
      {note && <p className="muted">{note}</p>}
      {children}
    </section>
  );
}

function ModelCard({ models }: { models: Dashboard["salaries"]["models"] }) {
  if (models.skipped || !models.regression) return <p className="muted">{models.skipped ?? "Sin modelo."}</p>;
  const r = models.regression;
  const c = models.classification;
  return (
    <dl className="model">
      <dt>Error absoluto medio</dt><dd>{cop(r.mae_cop)} <small>vs {cop(r.baseline_median_mae_cop)} prediciendo la mediana</small></dd>
      <dt>Error porcentual mediano</dt><dd>{pct(r.median_abs_pct_error)}</dd>
      <dt>R² (log salario)</dt><dd>{r.r2_log.toFixed(2)}</dd>
      {c && !c.skipped && (<>
        <dt>Banda salarial (bajo/medio/alto)</dt>
        <dd>exactitud {pct(c.accuracy)} · F1 {c.macro_f1.toFixed(2)} <small>vs {pct(c.baseline_majority_accuracy)} clase mayoritaria</small></dd>
      </>)}
      <dt>Vacantes con salario usable</dt><dd>{models.labeled_rows?.toLocaleString("es-CO")}</dd>
    </dl>
  );
}

function ClusteringTable({ methods }: { methods?: Dashboard["clustering_comparison"]["methods"] }) {
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
