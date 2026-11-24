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

export function neighbourBars(links: Dashboard["graph"]["segment_links"], names: Record<number, string>, limit = 12): Bar[] {
  return [...links].sort((a, b) => b.similarity - a.similarity).slice(0, limit).map((l) => ({
    label: `${segmentName(names, l.from)} ↔ ${segmentName(names, l.to)}`,
    value: l.similarity,
  }));
}

/** Shares of an explicit total (e.g. a segment's postings); lists cut to the top N add up to less than 100%. */
export function shareOfTotalBars(items: { label: string; count: number }[], total: number): Bar[] {
  return items.map((c) => ({ label: c.label, value: total ? Math.min(1, c.count / total) : 0, hint: `n=${n(c.count)}` }));
}

/** Postings with / without a published salary band; the gap is shown, not hidden. */
export function salaryCoverageBars(o: Dashboard["overview"]): Bar[] {
  const without = Math.max(0, o.postings - o.with_salary);
  const share = (count: number) => (o.postings ? count / o.postings : 0);
  return [
    { label: "Con rango salarial publicado", value: share(o.with_salary), hint: `n=${n(o.with_salary)} de ${n(o.postings)}` },
    { label: "Sin rango publicado", value: share(without), hint: `n=${n(without)} de ${n(o.postings)}` },
  ];
}

/** Topic terms as chips; the API sends them joined with " | ". */
export const topicTerms = (terms: string) => terms.split(" | ").map((t) => t.trim()).filter(Boolean);
