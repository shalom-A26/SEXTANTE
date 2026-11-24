"use client";

import { useEffect, useRef, useState } from "react";

import { CandidatesTab } from "@/components/dashboard/candidates-tab";
import { EmployersTab } from "@/components/dashboard/employers-tab";
import { MarketTab } from "@/components/dashboard/market-tab";
import { ProgramsTab } from "@/components/dashboard/programs-tab";
import { CountUp, Reveal, SplitHeading } from "@/components/motion";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { apiErrorMessage, getDashboard, pct, type Dashboard } from "@/lib/api";
import { modeKpi } from "@/lib/dashboard";

const TABS = ["Candidatos", "Empleadores", "Programas académicos", "Mapa del mercado"] as const;
type Tab = (typeof TABS)[number];

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("Candidatos");
  const tabsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getDashboard().then(setData).catch((e: unknown) => setError(apiErrorMessage(e)));
  }, []);

  // The new tab's panels cascade in (independent of how each tab lays its panels out).
  useGSAP(() => {
    const root = tabsRef.current;
    if (!root) return;
    gsap.matchMedia().add(MOTION_OK, () => {
      const panels = root.querySelectorAll('[role="tabpanel"][data-state="active"] .panel');
      if (panels.length) gsap.from(panels, { y: 30, opacity: 0, duration: 0.8, stagger: 0.08 });
    });
  }, { dependencies: [tab, data], scope: tabsRef });

  if (error) {
    return (
      <div className="dashboard">
        <div className="notice error" role="alert">No se pudo cargar el dashboard. {error}</div>
      </div>
    );
  }
  if (!data) return <DashboardSkeleton />;
  const o = data.overview;
  const { mode, share } = modeKpi(data.salaries.overall);

  return (
    <div className="dashboard">
      {data.run.synthetic && (
        <div className="notice warn">Datos sintéticos de demostración: ejecuta el análisis sobre el corpus real para ver cifras reales.</div>
      )}
      <div className="page-head">
        <span className="pill">Dashboard</span>
        <SplitHeading as="h1" className="page-title" onScroll={false}><>El mercado laboral <i>colombiano</i>, en cifras</></SplitHeading>
      </div>
      <p className="muted">
        Datos actualizados al {new Date(data.run.created_at_utc).toLocaleDateString("es-CO", { day: "numeric", month: "long", year: "numeric", timeZone: "America/Bogota" })} · se recalculan cada día
      </p>
      <Reveal className="kpis" stagger={0.1}>
        <Kpi label="Vacantes analizadas" value={o.postings} />
        <Kpi label="Segmentos ocupacionales" value={o.segments} />
        <Kpi label="Habilidades ESCO detectadas" value={o.skills_detected} />
        <Kpi label="Vacantes en el rango salarial más común" value={share} format={pct}
          hint={mode
            ? `${mode} · ${o.with_salary.toLocaleString("es-CO")} vacantes con rango publicado`
            : "Sin rangos salariales publicados"} />
      </Reveal>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} ref={tabsRef} className="dash-tabs">
        <TabsList variant="line" className="tab-list">
          {TABS.map((t) => <TabsTrigger key={t} value={t} className="tab-trigger">{t}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="Candidatos"><CandidatesTab data={data} /></TabsContent>
        <TabsContent value="Empleadores"><EmployersTab data={data} /></TabsContent>
        <TabsContent value="Programas académicos"><ProgramsTab data={data} /></TabsContent>
        <TabsContent value="Mapa del mercado"><MarketTab data={data} /></TabsContent>
      </Tabs>
      <p className="label run-id">Corrida {data.run.run_id} · corpus {data.run.corpus}</p>
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

function Kpi({ label, value, hint, format }: { label: string; value: number | null; hint?: string; format?: (v: number) => string }) {
  return (
    <div className="kpi">
      <span>{label}</span>
      <strong>{value === null ? "—" : <CountUp value={value} format={format} />}</strong>
      {hint && <small>{hint}</small>}
    </div>
  );
}
