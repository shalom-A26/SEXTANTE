import { pct, type SkillInsights } from "@/lib/api";
import { segmentName } from "@/lib/dashboard";
import { formatCount, formatTimes } from "@/lib/skills";
import { Panel } from "./panel";

/** Skill pairs asked together far more often than chance (ranked by PMI, explained by the lift). */
export function SkillPairs({ pairs }: { pairs?: SkillInsights["pairs"] }) {
  if (!pairs?.length) return null;
  return (
    <Panel title="Habilidades que se piden en bloque" note="Parejas que las empresas piden juntas mucho más de lo que se esperaría por azar: si buscas una, probablemente necesitas la otra.">
      <ul className="pair-list">
        {pairs.map((p) => (
          <li key={`${p.a}|${p.b}`}>
            <strong>{p.a} <span className="label">+</span> {p.b}</strong>
            <span>se piden juntas <b>{formatTimes(p.lift)} veces</b> más de lo esperado</span>
            <small className="label">{formatCount(p.together)} vacantes</small>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/** Rare skills tied to one profile, with the skill they are most often paired with. */
export function NicheSkills({ niche, names }: { niche?: SkillInsights["niche"]; names: Record<number, string> }) {
  if (!niche?.length) return null;
  return (
    <Panel title="Habilidades de nicho" note="Poco pedidas en general, pero casi siempre en el mismo perfil y con una compañera fija: difíciles de encontrar, valiosas donde se piden.">
      <ul className="pair-list">
        {niche.map((s) => (
          <li key={s.skill_label}>
            <strong>{s.skill_label}</strong>
            <span>
              {pct(s.top_segment_share)} de sus vacantes en {segmentName(names, s.top_segment)}
              {s.partner && <> · suele ir con <b>{s.partner}</b> ({formatTimes(s.partner_lift)} veces lo esperado)</>}
            </span>
            <small className="label">{formatCount(s.postings)} vacantes</small>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
