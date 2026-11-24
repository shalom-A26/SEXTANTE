import { BarList } from "@/components/charts";
import type { Dashboard } from "@/lib/api";
import { programSkillBars, shareOfTotalBars } from "@/lib/dashboard";
import { Panel } from "./panel";

export function ProgramsTab({ data }: { data: Dashboard }) {
  const o = data.overview;
  return (
    <div className="grid-2">
      <Panel title="Nivel educativo que piden las vacantes" note={`% de vacantes por nivel (n=${o.postings.toLocaleString("es-CO")}); "Sin dato" son vacantes que no lo especifican`}>
        <BarList data={shareOfTotalBars(o.education, o.postings)} unit="percent" />
      </Panel>
      {data.education_skills.map((e) => (
        <Panel key={e.education} title={e.education} note={`${e.postings.toLocaleString("es-CO")} vacantes · % que pide cada habilidad`}>
          <BarList data={programSkillBars(e)} unit="percent" />
        </Panel>
      ))}
    </div>
  );
}
