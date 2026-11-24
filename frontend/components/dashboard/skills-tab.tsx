import type { Dashboard } from "@/lib/api";
import { segmentNames } from "@/lib/dashboard";
import { CentralityTable } from "./centrality-table";
import { KeySkills } from "./key-skills";
import { SkillKinds } from "./skill-kinds";
import { NicheSkills, SkillPairs } from "./skill-pairs";
import { SkillSalary } from "./skill-salary";

/** Skill-level reading of the co-occurrence graph. Every section hides itself when its data is missing. */
export function SkillsTab({ data }: { data: Dashboard }) {
  const names = segmentNames(data.segments);
  const s = data.skill_insights;
  const empty = !s && !data.graph.rankings?.bridges?.length && !data.graph.nodes.length;
  return (
    <div className="grid-1">
      {empty && <p className="muted">Esta corrida no incluye el análisis de habilidades.</p>}
      <KeySkills data={data} />
      <SkillKinds table={s?.table} names={names} />
      {(s?.pairs?.length || s?.niche?.length) ? (
        <div className="grid-2">
          <SkillPairs pairs={s?.pairs} />
          <NicheSkills niche={s?.niche} names={names} />
        </div>
      ) : null}
      <SkillSalary salary={s?.salary} />
      <CentralityTable table={s?.table} />
    </div>
  );
}
