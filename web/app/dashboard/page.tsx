"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { BarList, Scatter, SkillGraph } from "@/components/charts";
import { CountUp, Reveal, SplitHeading } from "@/components/motion";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { API_URL, cop, getDashboard, pct, type Dashboard } from "@/lib/api";

const TABS = ["Candidatos", "Empleadores", "Programas académicos", "Mapa del mercado"] as const;
type Tab = (typeof TABS)[number];

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Candidatos");
  const tabsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getDashboard().then(setData).catch((e: Error) => {
      setError(e.message);
      toast.error("No se pudo cargar el dashboard", { description: e.message });
    });
  }, []);

  const names = useMemo(
    () => Object.fromEntries((data?.segments ?? []).map((s) => [s.id, s.name])) as Record<number, string>,
    [data],
  );

  // Sliding indicator under the active tab, and the new panel's content cascading in.
  useGSAP(() => {
    const root = tabsRef.current;
    if (!root) return;
    const active = root.querySelector<HTMLElement>('[role="tab"][data-state="active"]');
    const indicator = root.querySelector<HTMLElement>(".tab-indicator");
    if (active && indicator) {
      gsap.to(indicator, { x: active.offsetLeft, width: active.offsetWidth, duration: 0.6, ease: "expo.out" });
    }
    gsap.matchMedia().add(MOTION_OK, () => {
      const panel = root.querySelector('[role="tabpanel"][data-state="active"]');
      if (panel) gsap.from(panel.querySelectorAll(":scope > div > *"), { y: 30, opacity: 0, duration: 0.8, stagger: 0.08 });
    });
  }, { dependencies: [tab, data], scope: tabsRef });

  if (error) {
    return (
      <div className="dashboard">
        <div className="notice error">No se pudo cargar el API ({error}). ¿Está corriendo en {API_URL}? Si está en el plan gratis, puede tardar un minuto en despertar.</div>
      </div>
    );
  }
  if (!data) return <DashboardSkeleton />;
  const o = data.overview;

  return (
    <div className="dashboard">
      {data.run.synthetic && (
        <div className="notice warn">Datos sintéticos de demostración: ejecuta el análisis sobre el corpus real para ver cifras reales.</div>
      )}
      <SplitHeading as="h1" className="page-title" onScroll={false}>El mercado laboral colombiano, en cifras</SplitHeading>
      <Reveal className="kpis" stagger={0.1}>
        <Kpi label="Vacantes analizadas" value={o.postings} />
        <Kpi label="Segmentos ocupacionales" value={o.segments} />
        <Kpi label="Habilidades ESCO detectadas" value={o.skills_detected} />
        <Kpi label="Salario mediano" value={data.salaries.overall.median ?? 0} format={(v) => cop(v)}
          hint={`${o.with_salary.toLocaleString("es-CO")} vacantes con salario`} />
      </Reveal>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} ref={tabsRef} className="dash-tabs">
        <TabsList variant="line" className="tab-list">
          {TABS.map((t) => <TabsTrigger key={t} value={t} className="tab-trigger">{t}</TabsTrigger>)}
          <span className="tab-indicator" aria-hidden="true" />
        </TabsList>

        <TabsContent value="Candidatos">
          <div className="grid-2">
            <Panel title="Habilidades más pedidas" note="% de vacantes que la mencionan">
              <BarList data={data.top_skills.slice(0, 15).map((s) => ({ label: s.skill, value: s.share }))} format={pct} />
            </Panel>
            <Panel title="Segmentos ocupacionales" note="Salario mediano y habilidades distintivas">
              <Accordion type="single" collapsible className="segment-list">
                {data.segments.map((s) => (
                  <AccordionItem key={s.id} value={String(s.id)}>
                    <AccordionTrigger className="segment-trigger">
                      <strong>{s.name}</strong>
                      <span>{s.postings.toLocaleString("es-CO")} vacantes · {cop(s.salary.median)}</span>
                    </AccordionTrigger>
                    <AccordionContent>
                      <p className="chips">
                        {s.top_skills.map((k) => <Badge key={k.skill} variant="outline" className="chip">{k.skill} · {pct(k.share)}</Badge>)}
                      </p>
                      <p className="muted">Términos: {s.terms.join(", ")}</p>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </Panel>
          </div>
        </TabsContent>

        <TabsContent value="Empleadores">
          <div className="grid-2">
            <Panel title="Salario por segmento" note="Mediana mensual (COP); pasa el cursor para ver el rango intercuartílico">
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
        </TabsContent>

        <TabsContent value="Programas académicos">
          <div className="grid-2">
            {data.education_skills.map((e) => (
              <Panel key={e.education} title={e.education} note={`${e.postings.toLocaleString("es-CO")} vacantes · habilidades más pedidas`}>
                <BarList data={e.skills.map((s) => ({ label: s.skill, value: s.count }))} />
              </Panel>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="Mapa del mercado">
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
                  data={[...data.graph.segment_links].sort((a, b) => b.similarity - a.similarity).slice(0, 12).map((l) => ({
                    label: `${names[l.from]} ↔ ${names[l.to]}`, value: l.similarity,
                  }))}
                  format={pct} max={1}
                />
                <ClusteringTable methods={data.clustering_comparison.methods} />
              </Panel>
            </div>
          </div>
        </TabsContent>
      </Tabs>
      <p className="muted run-id">Corrida {data.run.run_id} · corpus {data.run.corpus}</p>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="dashboard" aria-busy="true" aria-label="Cargando datos">
      <Skeleton className="sk h-12 w-2/3" />
      <div className="kpis">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="kpi"><Skeleton className="sk h-4 w-32" /><Skeleton className="sk mt-2 h-10 w-40" /></div>
        ))}
      </div>
      <Skeleton className="sk h-9 w-full max-w-xl" />
      <div className="grid-2">
        {[0, 1].map((i) => (
          <div key={i} className="panel">
            <Skeleton className="sk h-5 w-48" />
            {Array.from({ length: 8 }, (_, j) => <Skeleton key={j} className="sk mt-3 h-3" style={{ width: `${90 - j * 8}%` }} />)}
          </div>
        ))}
      </div>
      <p className="muted">Cargando datos… si el API estaba dormido puede tardar hasta un minuto.</p>
    </div>
  );
}

function Kpi({ label, value, hint, format }: { label: string; value: number; hint?: string; format?: (v: number) => string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong><CountUp value={value} format={format} /></strong>
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
      <dt>Error absoluto medio</dt><dd><CountUp value={r.mae_cop} format={(v) => cop(v)} /> <small>vs {cop(r.baseline_median_mae_cop)} prediciendo la mediana</small></dd>
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
