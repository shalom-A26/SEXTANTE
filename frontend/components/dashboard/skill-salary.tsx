import { BarList } from "@/components/charts";
import { pct, type SkillInsights } from "@/lib/api";
import { formatCount, salarySkillBars } from "@/lib/skills";
import { Panel } from "./panel";

/** Share of postings paying $2M COP or more per skill, plus skill combinations that raise it. */
export function SkillSalary({ salary }: { salary?: SkillInsights["salary"] }) {
  const top = salarySkillBars(salary?.top);
  const bottom = salarySkillBars(salary?.bottom);
  const boosts = salary?.boosts ?? [];
  if (!salary || (!top.length && !bottom.length && !boosts.length)) return null;
  const overall = salary.overall_high_share;
  return (
    <Panel title="Habilidades y salario" note="% de las vacantes con salario publicado que ofrecen $2M o más, según la habilidad que piden.">
      {overall != null && (
        <p className="salary-ref">Promedio general (sin vacantes repetidas):<strong>{pct(overall)}</strong> con $2M o más</p>
      )}
      {(top.length > 0 || bottom.length > 0) && (
        <div className="rank-pair">
          {top.length > 0 && (
            <div>
              <h4>Más ligadas a salarios altos</h4>
              <p className="muted">Las habilidades con mayor parte de vacantes de $2M o más.</p>
              <BarList data={top} unit="percent" />
            </div>
          )}
          {bottom.length > 0 && (
            <div>
              <h4>Menos ligadas a salarios altos</h4>
              <p className="muted">Las habilidades con menor parte de vacantes de $2M o más.</p>
              <BarList data={bottom} unit="percent" />
            </div>
          )}
        </div>
      )}
      {boosts.length > 0 && (
        <div className="tech-block">
          <h4>Combinaciones que suben el salario</h4>
          <p className="muted">Sumar una segunda habilidad a la primera cambia la parte de vacantes con $2M o más.</p>
          <ul className="pair-list">
            {boosts.map((b) => (
              <li key={`${b.anchor}|${b.complement}`}>
                <strong>{b.anchor} <span className="label">→ con</span> {b.complement}</strong>
                <span>de <b>{pct(b.anchor_high_share)}</b> a <b>{pct(b.combo_high_share)}</b> de vacantes con $2M o más</span>
                <small className="label">n={formatCount(b.anchor_postings)} → {formatCount(b.combo_postings)}</small>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="muted footnote">Es una asociación, no una causa: aprender una habilidad no garantiza un mejor salario. Los salarios son rangos oficiales del SPE, no montos exactos.</p>
    </Panel>
  );
}
