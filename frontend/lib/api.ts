export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Count = { label: string; count: number };
// Salaries are official bands (SPE), never exact amounts: see sextante_analysis/supervised.py.
export type SalaryStats = {
  n: number;
  bands: { band: string; count: number; share: number }[];
  mode: string | null;
  median: string | null;
};

export type Segment = {
  id: number;
  name: string;
  postings: number;
  terms: string[];
  salary: SalaryStats;
  top_skills: { skill: string; share: number; lift: number }[];
  modality: Count[];
  education: Count[];
  cities: Count[];
};

export type Dashboard = {
  run: { run_id: string; created_at_utc: string; corpus: string; revision: string; synthetic: boolean };
  overview: {
    postings: number;
    with_salary: number;
    segments: number;
    skills_detected: number;
    skill_mentions: number | null;
    duplicate_candidates: number | null;
    duplicate_postings?: number | null;
    duplicate_groups?: number | null;
    sources: Count[];
    cities: Count[];
    modality: Count[];
    contracts: Count[];
    education: Count[];
  };
  segments: Segment[];
  top_skills: { esco_uri: string; skill: string; postings: number; share: number; community: number }[];
  education_skills: { education: string; postings: number; skills: { skill: string; count: number }[] }[];
  salaries: {
    overall: SalaryStats;
    by_department: (SalaryStats & { department: string })[];
    models: {
      labeled_rows?: number;
      skipped?: string;
      classification?: {
        accuracy: number; macro_f1: number; within_one_band: number;
        baseline_majority_accuracy: number; baseline_majority_macro_f1: number; baseline_within_one_band: number;
        cv_rows?: number; skipped?: string;
      };
    };
  };
  graph: {
    metrics: Record<string, number | null>;
    nodes: { esco_uri: string; skill_label: string; postings: number; pagerank: number; betweenness: number; community: number }[];
    edges: { source: string; target: string; weight: number }[];
    segment_links: { from: number; to: number; similarity: number }[];
  };
  topics: { topic_id: number; terms: string }[];
  projection: { component_1: number; component_2: number; cluster_id: number }[];
  clustering_comparison: {
    methods?: Record<string, { clusters: number; silhouette_cosine: number | null; noise_share: number }>;
  };
};

export type Gap = { skill: string; share: number };
export type SegmentAdvice = {
  segment: number;
  name: string;
  affinity: number;
  skill_coverage: number;
  postings: number;
  salary_band: string | null;
  gaps: Gap[];
  route?: { segment: number; name: string }[];
};

export type Match = {
  vacancy_id: string;
  source: string;
  url: string;
  title: string;
  company: string | null;
  city: string | null;
  work_modality: string | null;
  salary_min: number | null;
  salary_max: number | null;
  segment_name: string;
  match: number;
  text_similarity: number;
  skill_coverage: number | null;
  matched_skills: string[];
  missing_skills: string[];
};

export type CvResult = {
  cv_skills: string[];
  current_segment: SegmentAdvice | null;
  matches: Match[];
  niches: SegmentAdvice[];
  pivots: SegmentAdvice[];
  salary_estimate: { salary_band: string; probability: number } | null;
  method: string;
};

// One shared request per page load: hero, backdrop, "Cómo funciona" and the
// dashboard all read the same ~0.5 MB payload. A failed request is not cached.
let dashboardRequest: Promise<Dashboard> | null = null;

/** Failed request: `status` is set for HTTP errors, absent when the API was unreachable. */
export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

/** User-facing (Spanish) explanation that tells a connection failure from an HTTP error. */
export function apiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status !== undefined) {
    return `El API respondió con un error (HTTP ${error.status}). Intenta de nuevo en un momento.`;
  }
  return `No se pudo conectar con el API en ${API_URL}. ¿Está corriendo? Si está en el plan gratis, puede tardar un minuto en despertar.`;
}

export function getDashboard(): Promise<Dashboard> {
  dashboardRequest ??= fetch(`${API_URL}/api/dashboard`).then(
    (response) => {
      if (!response.ok) throw new ApiError(`API ${response.status}`, response.status);
      return response.json() as Promise<Dashboard>;
    },
    () => { throw new ApiError("API unreachable"); },
  ).catch((error: Error) => {
    dashboardRequest = null;
    throw error;
  });
  return dashboardRequest;
}

export async function matchCv(form: FormData): Promise<CvResult> {
  const response = await fetch(`${API_URL}/api/cv/match`, { method: "POST", body: form });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? `API ${response.status}`);
  return body;
}

export const cop = (value: number | null | undefined) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 }).format(value);

export const pct = (value: number) => `${(100 * value).toFixed(0)}%`;

/** Lower bound in millions of COP parsed from a band label ("Hasta $1,5M" -> 0, "$2M – $3M" -> 2); null if unreadable. */
function bandLowerBound(label: string): number | null {
  if (/^hasta/i.test(label)) return 0;
  const m = /\$(\d+(?:,\d+)?)\s*M/.exec(label);
  return m ? Number(m[1].replace(",", ".")) : null;
}

/**
 * Share of banded postings paying $2M COP or more, derived from the band labels themselves.
 * Returns null when there are no bands or any label cannot be read, so callers never show a guessed number.
 */
export function shareAbove2M(s: SalaryStats): number | null {
  if (!s.bands.length) return null;
  let total = 0;
  for (const b of s.bands) {
    const lower = bandLowerBound(b.band);
    if (lower === null) return null;
    if (lower >= 2) total += b.share;
  }
  return total;
}
