import { shareAbove2M, type Dashboard, type SalaryStats } from "@/lib/api";

/** One row of a BarList. `value` is a 0..1 share when the list is in percent mode, a count otherwise. */
export type Bar = { label: string; value: number; hint?: string };

const n = (value: number) => value.toLocaleString("es-CO");

/** [min, max] of a list without spreading it into Math.min/max (safe when empty or huge). */
export function extent(values: number[]): [number, number] | null {
  if (!values.length) return null;
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
}

export const segmentName = (names: Record<number, string>, id: number) => names[id] ?? `Segmento ${id}`;

export const segmentNames = (segments: Dashboard["segments"]) =>
  Object.fromEntries(segments.map((s) => [s.id, s.name])) as Record<number, string>;

/** Headline KPI: share of banded postings in the most common salary band, or null when there is none. */
export function modeKpi(overall: SalaryStats) {
  const share = overall.mode ? overall.bands.find((b) => b.band === overall.mode)?.share : undefined;
  return { mode: overall.mode, share: share ?? null };
}

export const skillBars = (skills: Dashboard["top_skills"], limit = 15): Bar[] =>
  skills.slice(0, limit).map((s) => ({ label: s.skill, value: s.share, hint: `n=${n(s.postings)}` }));

export const salaryBandBars = (overall: SalaryStats): Bar[] =>
  overall.bands.map((b) => ({ label: b.band, value: b.share, hint: `n=${n(b.count)}` }));

const salaryHint = (s: SalaryStats) =>
  `Rango más común: ${s.mode ?? "—"} · mediana: ${s.median ?? "—"} · n=${n(s.n)}`;

/** Share of postings paying $2M or more; groups whose bands cannot be read are left out, never guessed. */
function aboveTwoMillion(items: { label: string; stats: SalaryStats }[]): Bar[] {
  return items.flatMap(({ label, stats }) => {
    const value = shareAbove2M(stats);
    return value === null ? [] : [{ label, value, hint: salaryHint(stats) }];
  }).sort((a, b) => b.value - a.value);
}

export const segmentSalaryBars = (segments: Dashboard["segments"]): Bar[] =>
  aboveTwoMillion(segments.filter((s) => s.salary.n).map((s) => ({ label: s.name, stats: s.salary })));

export const departmentSalaryBars = (departments: Dashboard["salaries"]["by_department"]): Bar[] =>
  aboveTwoMillion(departments.map((d) => ({ label: d.department, stats: d })));

/** Counts turned into shares of their own total (the panel is about the mix), keeping n as the hint. */
export function shareBars(items: { label: string; count: number }[]): Bar[] {
  const total = items.reduce((sum, c) => sum + c.count, 0);
  return items.map((c) => ({ label: c.label, value: total ? c.count / total : 0, hint: `n=${n(c.count)}` }));
}

export const countBars = (items: { label: string; count: number }[]): Bar[] =>
  items.map((c) => ({ label: c.label, value: c.count }));

/** Skills of one program as the share of that program's postings that ask for them. */
export const programSkillBars = (e: Dashboard["education_skills"][number]): Bar[] =>
  e.skills.map((s) => ({
    label: s.skill,
    value: e.postings ? Math.min(1, s.count / e.postings) : 0,
    hint: `n=${n(s.count)}`,
  }));

/** Segments most similar to `id` (links are undirected and stored once, from < to), best first. */
export function nearbySegments(links: Dashboard["graph"]["segment_links"], id: number, names: Record<number, string>, limit = 3) {
  return links
    .flatMap((l) => (l.from === id ? [{ id: l.to, similarity: l.similarity }]
      : l.to === id ? [{ id: l.from, similarity: l.similarity }] : []))
    .sort((a, b) => b.similarity - a.similarity)
    .slice(0, limit)
    .map((l) => ({ name: segmentName(names, l.id), similarity: l.similarity }));
}

type Graph = Dashboard["graph"];

/** Skills connected to the most other skills; falls back to the drawn nodes on runs without `rankings`. */
export function transversalBars(graph: Graph, limit = 10): Bar[] {
  const ranked: { skill_label: string; postings: number; degree: number }[] = graph.rankings?.transversal?.length
    ? graph.rankings.transversal
    : graph.nodes.flatMap((s) => (s.degree != null ? [{ ...s, degree: s.degree }] : []))
      .sort((a, b) => b.degree - a.degree);
  return ranked.slice(0, limit).map((s) => ({
    label: s.skill_label,
    value: s.degree,
    hint: `aparece junto a ${n(s.degree)} habilidades distintas · n=${n(s.postings)} vacantes`,
  }));
}

/** Skills that link different areas of the graph (betweenness); drawn relative to the top one, no raw decimals. */
export function bridgeBars(graph: Graph, limit = 10): Bar[] {
  const ranked: { skill_label: string; postings: number; betweenness: number }[] = graph.rankings?.bridges?.length
    ? graph.rankings.bridges
    : [...graph.nodes].filter((s) => s.betweenness > 0).sort((a, b) => b.betweenness - a.betweenness);
  return ranked.slice(0, limit).map((s) => ({
    label: s.skill_label,
    value: s.betweenness,
    hint: `une grupos de habilidades distintos · n=${n(s.postings)} vacantes`,
  }));
}

/** One legend entry per community, named by its top skills; derived from the nodes when the API omits them. */
export function communityLegend(nodes: { skill_label: string; postings: number; community: number }[],
  communities?: Graph["communities"], skills = 3) {
  const present = new Set(nodes.map((s) => s.community));
  const given = (communities ?? []).filter((c) => present.has(c.community) && c.top_skills.length);
  if (given.length) {
    return given.sort((a, b) => b.size - a.size).map((c) => ({ ...c, top_skills: c.top_skills.slice(0, skills) }));
  }
  return [...present].map((community) => {
    const members = nodes.filter((s) => s.community === community).sort((a, b) => b.postings - a.postings);
    return { community, size: members.length, top_skills: members.slice(0, skills).map((s) => s.skill_label) };
  }).sort((a, b) => b.size - a.size);
}

/** Shares of an explicit total (e.g. a segment's postings); lists cut to the top N add up to less than 100%. */
export function shareOfTotalBars(items: { label: string; count: number }[], total: number): Bar[] {
  return items.map((c) => ({ label: c.label, value: total ? Math.min(1, c.count / total) : 0, hint: `n=${n(c.count)}` }));
}
