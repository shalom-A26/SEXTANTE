export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Count = { label: string; count: number };
export type SalaryStats = { median: number | null; p25: number | null; p75: number | null; n: number };

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
    sources: Count[];
    cities: Count[];
    modality: Count[];
    contracts: Count[];
    education: Count[];
  };
  segments: Segment[];
  top_skills: { skill: string; postings: number; share: number; community: number }[];
  education_skills: { education: string; postings: number; skills: { skill: string; count: number }[] }[];
  salaries: {
    overall: SalaryStats;
    by_department: (SalaryStats & { department: string })[];
    models: {
      labeled_rows?: number;
      skipped?: string;
      regression?: { mae_cop: number; baseline_median_mae_cop: number; r2_log: number; median_abs_pct_error: number };
      classification?: { accuracy: number; macro_f1: number; baseline_majority_accuracy: number; skipped?: string };
    };
  };
  graph: {
    metrics: Record<string, number | null>;
    nodes: { esco_uri: string; skill_label: string; postings: number; pagerank: number; community: number }[];
    edges: { source: string; target: string; weight: number }[];
    segment_links: { from: number; to: number; similarity: number }[];
  };
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
  median_salary: number | null;
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
  salary_estimate: { salary_estimate_cop: number; salary_band: string | null } | null;
  method: string;
};

// One shared request per page load: hero, backdrop, "Cómo funciona" and the
// dashboard all read the same ~0.5 MB payload. A failed request is not cached.
let dashboardRequest: Promise<Dashboard> | null = null;

export function getDashboard(): Promise<Dashboard> {
  dashboardRequest ??= fetch(`${API_URL}/api/dashboard`).then((response) => {
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json() as Promise<Dashboard>;
  }).catch((error: Error) => {
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
