import { pct, type Dashboard, type SalarySkill, type SkillKind, type SkillMetrics, type SkillPivot, type Topic } from "@/lib/api";
import { segmentName, type Bar } from "@/lib/dashboard";

export const formatCount = (value: number) => value.toLocaleString("es-CO");
/** A ratio such as a lift, with one decimal ("2,4"). */
export const formatTimes = (value: number) => value.toLocaleString("es-CO", { maximumFractionDigits: 1 });
const n = formatCount;
const times = formatTimes;

/** Skills most connected to other in-demand skills (PageRank); drawn relative to the top one. */
export const coreBars = (core: NonNullable<Dashboard["skill_insights"]>["core"]): Bar[] =>
  (core ?? []).map((s) => ({
    label: s.skill_label,
    value: s.pagerank,
    hint: `se pide junto a ${n(s.degree)} habilidades distintas · n=${n(s.postings)} vacantes`,
  }));

/** Segments that have at least one pivot, largest first (by number of postings), with readable names. */
export function pivotOrigins(pivots: SkillPivot[], segments: Dashboard["segments"], names: Record<number, string>) {
  const size = Object.fromEntries(segments.map((s) => [s.id, s.postings])) as Record<number, number>;
  return [...new Set(pivots.map((p) => p.from_segment))]
    .sort((a, b) => (size[b] ?? 0) - (size[a] ?? 0))
    .map((id) => ({ id, name: segmentName(names, id) }));
}

export const pivotTargets = (pivots: SkillPivot[], from: number) =>
  pivots.filter((p) => p.from_segment === from).sort((a, b) => b.similarity - a.similarity);

export const KIND_ORDER: SkillKind[] = ["transversal", "intermedia", "especializada"];

/** Table rows grouped by kind, each group by postings (most requested first). */
export function kindGroups(table: SkillMetrics[]) {
  return KIND_ORDER.map((kind) => ({
    kind,
    skills: table.filter((s) => s.kind === kind).sort((a, b) => b.postings - a.postings),
  })).filter((g) => g.skills.length);
}

/** Share of postings with salary >= $2M for each skill; the hint carries the sample size and the lift. */
export const salarySkillBars = (rows: SalarySkill[] | undefined): Bar[] =>
  (rows ?? []).map((s) => ({
    label: s.skill_label,
    value: s.high_share,
    hint: `${pct(s.high_share)} de ${n(s.postings_with_salary)} vacantes con salario publicado · ${times(s.lift)} veces el promedio`,
  }));

/** Topic terms as chips; the API sends them joined with " | ". */
export const topicTerms = (terms: string) => terms.split(" | ").map((t) => t.trim()).filter(Boolean);

const capitalize = (s: string) => (s ? s[0].toLocaleUpperCase("es-CO") + s.slice(1) : s);

/** Human title for a topic: its most typical job title, else its first terms. */
export function topicTitle(t: Topic) {
  const title = t.top_titles?.find((x) => x.trim());
  const name = title ? title.trim() : topicTerms(t.terms).slice(0, 3).join(", ");
  return `Tema ${t.topic_id + 1} · ${capitalize(name)}`;
}

/** True when the API sent the enriched topic fields (any of them). */
export const topicsEnriched = (topics: Topic[]) =>
  topics.some((t) => t.share != null || t.top_titles?.length || t.top_skills?.length || t.top_segments?.length);
