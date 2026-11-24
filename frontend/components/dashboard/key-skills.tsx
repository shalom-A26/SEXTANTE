import { BarList } from "@/components/charts";
import type { Dashboard } from "@/lib/api";
import { bridgeBars, transversalBars } from "@/lib/dashboard";
import { coreBars } from "@/lib/skills";
import { Panel } from "./panel";
import { SkillPivots } from "./skill-pivots";

/** Core (PageRank), bridge (betweenness) and pivot skills. Runs without `core` fall back to the degree ranking. */
export function KeySkills({ data }: { data: Dashboard }) {
  const core = coreBars(data.skill_insights?.core);
  const transversal = core.length ? [] : transversalBars(data.graph);
  const bridges = bridgeBars(data.graph);
  const pivots = data.skill_insights?.pivots ?? [];
  if (!core.length && !transversal.length && !bridges.length && !pivots.length) return null;
  return (
    <Panel title="Habilidades clave" note="Qué habilidades sostienen el mercado, cuáles abren paso a otros perfiles y qué falta para cambiar de rol.">
      <div className="key-skills">
      <div className="rank-pair">
        {core.length > 0 && (
          <div>
            <h4>Núcleo</h4>
            <p className="muted">Se piden junto a otras habilidades muy demandadas: son la base de muchos perfiles. La barra compara con la primera.</p>
            <BarList data={core} unit="relative" />
          </div>
        )}
        {transversal.length > 0 && (
          <div>
            <h4>Transversales</h4>
            <p className="muted">Aparecen junto a más habilidades distintas: abren más puertas. El número es cuántas.</p>
            <BarList data={transversal} unit="count" />
          </div>
        )}
        {bridges.length > 0 && (
          <div>
            <h4>Puente</h4>
            <p className="muted">Conectan perfiles distintos que casi no se tocan: son las que más rinden para cambiar de campo. La barra compara con la primera.</p>
            <BarList data={bridges} unit="relative" />
          </div>
        )}
      </div>
      {pivots.length > 0 && <SkillPivots pivots={pivots} segments={data.segments} />}
      </div>
    </Panel>
  );
}
