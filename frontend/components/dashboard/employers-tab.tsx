import { BarList } from "@/components/charts";
import type { Dashboard } from "@/lib/api";
import { countBars, departmentSalaryBars, salaryBandBars, salaryCoverageBars, segmentSalaryBars, shareBars } from "@/lib/dashboard";
import { Panel } from "./panel";
import { ModelCard, TechDetails } from "./tech-details";

export function EmployersTab({ data }: { data: Dashboard }) {
  const o = data.overview;
  return (
    <div className="grid-1">
      <div className="grid-2">
        <Panel title="Distribución salarial" note="% de vacantes por rango oficial del SPE (salario mensual, COP). Las vacantes publican rangos, no cifras exactas.">
          <BarList data={salaryBandBars(data.salaries.overall)} unit="percent" />
        </Panel>
        <Panel title="Cobertura salarial" note={`% de las ${o.postings.toLocaleString("es-CO")} vacantes que publican un rango. Las cifras de salario de esta pestaña describen solo las que lo publican.`}>
          <BarList data={salaryCoverageBars(o)} unit="percent" />
        </Panel>
        <Panel title="Salario por segmento" note="% de vacantes que pagan $2M o más; enfoca una barra para ver el rango más común y la mediana">
          <BarList data={segmentSalaryBars(data.segments)} unit="percent" />
        </Panel>
        <Panel title="Salario por departamento" note="% de vacantes que pagan $2M o más (departamentos con 30+ vacantes con rango); enfoca una barra para ver el rango más común y la mediana">
          <BarList data={departmentSalaryBars(data.salaries.by_department)} unit="percent" />
        </Panel>
        <Panel title="Modalidad de trabajo" note="% de vacantes">
          <BarList data={shareBars(o.modality)} unit="percent" />
        </Panel>
        <Panel title="Tipo de contrato" note="% de vacantes">
          <BarList data={shareBars(o.contracts)} unit="percent" />
        </Panel>
        <Panel title="Ciudades con más vacantes" note="Número de vacantes">
          <BarList data={countBars(o.cities)} unit="count" />
        </Panel>
      </div>
      <TechDetails title="Detalle técnico: modelo de rango salarial">
        <ModelCard models={data.salaries.models} />
      </TechDetails>
    </div>
  );
}
