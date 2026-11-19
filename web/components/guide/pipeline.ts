// The SEXTANTE pipeline, small enough to run in the browser on the guide's rows.
// Each function mirrors the Python it explains (file named in its comment);
// parameters that must differ because there are only six rows are marked.

import type { Row } from "./rows";

// ---------- Text ----------

const MOJIBAKE = /Ã[\x80-\xbf¡-ÿ]|â€|Â[\xa0-\xbf]/;
// cp1252 bytes 0x80–0x9f that are not latin-1.
const CP1252: Record<string, number> = {
  "€": 0x80, "‚": 0x82, "ƒ": 0x83, "„": 0x84, "…": 0x85, "†": 0x86, "‡": 0x87, "ˆ": 0x88, "‰": 0x89, "Š": 0x8a,
  "‹": 0x8b, "Œ": 0x8c, "Ž": 0x8e, "‘": 0x91, "’": 0x92, "“": 0x93, "”": 0x94, "•": 0x95, "–": 0x96, "—": 0x97,
  "˜": 0x98, "™": 0x99, "š": 0x9a, "›": 0x9b, "œ": 0x9c, "ž": 0x9e, "Ÿ": 0x9f,
};

/** sextante_analysis/cleaning.py · repair_mojibake: undo up to two UTF-8 → cp1252 mis-decodings. */
export function repairMojibake(text: string): string {
  for (let round = 0; round < 2 && MOJIBAKE.test(text); round++) {
    const bytes: number[] = [];
    for (const ch of text) {
      const code = ch.codePointAt(0)!;
      if (code < 256) bytes.push(code);
      else if (ch in CP1252) bytes.push(CP1252[ch]);
      else return text;
    }
    try {
      text = new TextDecoder("utf-8", { fatal: true }).decode(new Uint8Array(bytes));
    } catch {
      return text;
    }
  }
  return text;
}

/** sextante_analysis/taxonomy.py · normalize_text: NFKD, casefold, drop accents, [^\W_]+ tokens. */
export function tokenize(value: string): string[] {
  const text = value.normalize("NFKD").toLowerCase().replace(/\p{M}/gu, "");
  return text.match(/[\p{L}\p{N}]+/gu) ?? [];
}
export const normalizeText = (value: string) => tokenize(value).join(" ");

export const STOPWORDS = new Set(("de la el en y a los las del con para por un una se su al lo como mas o que es " +
  "sus le ya este esta e u").split(" "));
// Template words: they describe the posting format, not the job (cleaning.py's template list).
export const TEMPLATE = new Set(("empresa lider sector busca buscamos requiere requerimos postulate horario lunes sabado " +
  "contrato termino fijo prestaciones ley todas salario beneficios valoramos").split(" "));

export type Token = { t: string; kind: "keep" | "stop" | "template" };

export function cleanTokens(text: string): Token[] {
  return tokenize(text).map((t) => ({ t, kind: STOPWORDS.has(t) ? "stop" : TEMPLATE.has(t) ? "template" : "keep" }));
}
export const keptTokens = (text: string) => cleanTokens(text).filter((x) => x.kind === "keep").map((x) => x.t);

// ---------- ESCO skills: token trie, longest match ----------

// A slice of ESCO (es) plus the Colombian synonyms the real dictionary adds.
export const ESCO: [string, string[]][] = [
  ["gestionar inventarios", ["gestion de inventarios", "gestionar inventarios"]],
  ["controlar despachos", ["control de despachos"]],
  ["manejar montacargas", ["manejo de montacargas", "montacargas"]],
  ["utilizar hojas de cálculo", ["excel", "excel basico", "hojas de calculo"]],
  ["Excel avanzado", ["excel avanzado"]],
  ["trabajar en equipo", ["trabajo en equipo", "trabajar en equipo"]],
  ["Power BI", ["power bi"]],
  ["SQL", ["sql", "consultas sql"]],
  ["Python", ["python"]],
  ["Django", ["django"]],
  ["comunicación efectiva", ["comunicacion efectiva"]],
  ["pensamiento analítico", ["pensamiento analitico"]],
  ["automatizar reportes", ["automatizar reportes", "automatice reportes"]],
  ["visualización de datos", ["tableros", "visualizacion de datos"]],
  ["procedimientos de facturación", ["facturacion", "facturacion electronica"]],
  ["conciliaciones bancarias", ["conciliaciones bancarias"]],
  ["nómina", ["nomina"]],
  ["diseñar APIs", ["apis rest", "api rest", "diseno de apis rest"]],
  ["bases de datos", ["bases de datos", "postgresql"]],
  ["inglés", ["ingles"]],
  ["vender seguros", ["venta de seguros"]],
  ["servicio al cliente", ["atencion al cliente", "servicio al cliente"]],
  ["orientación a resultados", ["orientacion a resultados"]],
];

type Trie = { next: Map<string, Trie>; skill?: string };

function buildTrie(): Trie {
  const root: Trie = { next: new Map() };
  for (const [label, aliases] of ESCO) {
    for (const alias of aliases) {
      let node = root;
      for (const tok of tokenize(alias)) {
        if (!node.next.has(tok)) node.next.set(tok, { next: new Map() });
        node = node.next.get(tok)!;
      }
      node.skill = label;
    }
  }
  return root;
}
const TRIE = buildTrie();

export type SkillHit = { start: number; end: number; skill: string };

/** taxonomy.py · EscoMatcher.match: from each token walk the trie; keep the longest match, then jump past it. */
export function matchSkills(tokens: string[]): SkillHit[] {
  const hits: SkillHit[] = [];
  let i = 0;
  while (i < tokens.length) {
    let node: Trie | undefined = TRIE;
    let best: SkillHit | null = null;
    for (let j = i; j < tokens.length && (node = node.next.get(tokens[j])); j++) {
      if (node.skill) best = { start: i, end: j + 1, skill: node.skill };
    }
    if (best) { hits.push(best); i = best.end; } else i++;
  }
  return hits;
}
export const skillSet = (text: string) => [...new Set(matchSkills(tokenize(text)).map((h) => h.skill))];

// ---------- Duplicates: shingles, MinHash, LSH threshold, TF-IDF cosine ----------

/** duplicates.py · _shingles: 3-token windows over normalized text. */
export function shingles(text: string, width = 3): string[] {
  const t = tokenize(text);
  return Array.from({ length: Math.max(1, t.length - width + 1) }, (_, i) => t.slice(i, i + width).join(" "));
}

function fnv1a(s: string) {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return h >>> 0;
}
const PRIME = 4294967311; // > 2^32
const PERMS = (() => {
  let s = 42;
  const rnd = () => { s = (Math.imul(s, 48271) % 2147483647 + 2147483647) % 2147483647; return s; };
  return Array.from({ length: 64 }, () => [1 + (rnd() % 1_000_000), rnd() % 1_000_000] as const);
})();

/** MinHash with 64 permutations (duplicates.py: num_perm=64, seed=42). */
export function minhash(items: string[]): number[] {
  const hashes = items.map(fnv1a);
  return PERMS.map(([a, b]) => hashes.reduce((m, h) => Math.min(m, (a * h + b) % PRIME), Infinity));
}
export const jaccard = (a: string[], b: string[]) => {
  const A = new Set(a), B = new Set(b);
  const inter = [...A].filter((x) => B.has(x)).length;
  return inter / (A.size + B.size - inter || 1);
};
export const minhashSimilarity = (a: number[], b: number[]) => a.filter((v, i) => v === b[i]).length / a.length;
export const LSH_THRESHOLD = 0.7;
export const DUPLICATE_THRESHOLD = 0.9;

// ---------- TF-IDF ----------

export type Vec = Map<string, number>;

function grams(tokens: string[]) {
  const out = [...tokens];
  for (let i = 0; i + 1 < tokens.length; i++) out.push(`${tokens[i]} ${tokens[i + 1]}`);
  return out;
}

/** features.py · TfidfVectorizer(ngram_range=(1, 2)), sklearn smooth idf + L2. min_df=1 here (real: 2) — six rows. */
export function fitTfidf(docs: string[][]) {
  const n = docs.length;
  const df = new Map<string, number>();
  const counts = docs.map((d) => {
    const c = new Map<string, number>();
    for (const g of grams(d)) c.set(g, (c.get(g) ?? 0) + 1);
    for (const g of c.keys()) df.set(g, (df.get(g) ?? 0) + 1);
    return c;
  });
  const idf = new Map([...df].map(([t, f]) => [t, Math.log((1 + n) / (1 + f)) + 1]));
  const transform = (c: Map<string, number>): Vec => {
    const v: Vec = new Map();
    for (const [t, tf] of c) if (idf.has(t)) v.set(t, tf * idf.get(t)!);
    const norm = Math.hypot(...v.values()) || 1;
    for (const [t, w] of v) v.set(t, w / norm);
    return v;
  };
  const vocab = [...idf.keys()].sort();
  return {
    vectors: counts.map(transform), idf, vocab,
    transformTokens: (tokens: string[]) => {
      const c = new Map<string, number>();
      for (const g of grams(tokens)) c.set(g, (c.get(g) ?? 0) + 1);
      return transform(c);
    },
  };
}
export function cosine(a: Vec, b: Vec) {
  let s = 0;
  for (const [t, w] of a) s += w * (b.get(t) ?? 0);
  return s;
}
export const topTerms = (v: Vec, k = 8) => [...v].sort((x, y) => y[1] - x[1]).slice(0, k);

// ---------- Linear algebra helpers ----------

const dense = (vectors: Vec[], vocab: string[]) => vectors.map((v) => vocab.map((t) => v.get(t) ?? 0));
function seeded(seed: number) {
  return () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
}

/** NMF, X ≈ W·H with Lee–Seung multiplicative updates (features.py uses sklearn NMF, k=12 there; 2 here). */
export function nmf(vectors: Vec[], vocab: string[], k = 2, iters = 300) {
  const X = dense(vectors, vocab);
  const r = seeded(7);
  let W = X.map(() => Array.from({ length: k }, () => r() + 0.1));
  let H = Array.from({ length: k }, () => vocab.map(() => r() + 0.1));
  const eps = 1e-9;
  for (let it = 0; it < iters; it++) {
    // H ← H ∘ (WᵀX) / (WᵀWH)
    const WtX = H.map((_, a) => vocab.map((_, j) => X.reduce((s, row, i) => s + W[i][a] * row[j], 0)));
    const WtW = H.map((_, a) => H.map((_, b) => W.reduce((s, w) => s + w[a] * w[b], 0)));
    H = H.map((h, a) => h.map((v, j) => v * WtX[a][j] / (WtW[a].reduce((s, wab, b) => s + wab * H[b][j], 0) + eps)));
    // W ← W ∘ (XHᵀ) / (WHHᵀ)
    const XHt = X.map((row) => H.map((h) => row.reduce((s, x, j) => s + x * h[j], 0)));
    const HHt = H.map((ha) => H.map((hb) => ha.reduce((s, v, j) => s + v * hb[j], 0)));
    W = W.map((w, i) => w.map((v, a) => v * XHt[i][a] / (w.reduce((s, wb, b) => s + wb * HHt[b][a], 0) + eps)));
  }
  const topics = H.map((h) => h.map((v, j) => [vocab[j], v] as [string, number]).sort((x, y) => y[1] - x[1]).slice(0, 6));
  const weights = W.map((w) => { const s = w.reduce((a, b) => a + b, 0) || 1; return w.map((v) => v / s); });
  return { topics, weights };
}

/** TruncatedSVD to 2-D (power iteration on XXᵀ with deflation): the projection the dashboard plots. */
export function svd2(vectors: Vec[], vocab: string[]) {
  const X = dense(vectors, vocab);
  const G = X.map((a) => X.map((b) => a.reduce((s, v, j) => s + v * b[j], 0)));
  const comps: number[][] = [];
  const r = seeded(11);
  for (let c = 0; c < 2; c++) {
    let u = G.map(() => r());
    let lambda = 0;
    for (let it = 0; it < 200; it++) {
      const next = G.map((row) => row.reduce((s, g, j) => s + g * u[j], 0));
      lambda = Math.hypot(...next) || 1;
      u = next.map((v) => v / lambda);
    }
    comps.push(u.map((v) => v * Math.sqrt(lambda)));
    G.forEach((row, i) => row.forEach((_, j) => { row[j] -= lambda * u[i] * u[j]; }));
  }
  return X.map((_, i) => [comps[0][i], comps[1][i]] as [number, number]);
}

/** K-Means on L2-normalized TF-IDF (features.py: KMeans(random_state=42)); farthest-point init, deterministic. */
export function kmeans(vectors: Vec[], vocab: string[], k: number) {
  const X = dense(vectors, vocab);
  const dist = (a: number[], b: number[]) => Math.sqrt(a.reduce((s, v, j) => s + (v - b[j]) ** 2, 0));
  const centers = [X[0]];
  while (centers.length < k) {
    let best = 0, bestD = -1;
    X.forEach((x, i) => { const d = Math.min(...centers.map((c) => dist(x, c))); if (d > bestD) { bestD = d; best = i; } });
    centers.push(X[best]);
  }
  let labels = X.map(() => 0);
  for (let it = 0; it < 50; it++) {
    const next = X.map((x) => centers.map((c) => dist(x, c)).reduce((bi, d, i, arr) => (d < arr[bi] ? i : bi), 0));
    centers.forEach((_, c) => {
      const members = X.filter((_, i) => next[i] === c);
      if (members.length) centers[c] = members[0].map((_, j) => members.reduce((s, m) => s + m[j], 0) / members.length);
    });
    if (next.every((l, i) => l === labels[i])) break;
    labels = next;
  }
  // Silhouette with cosine distance (the dashboard's silhouette_cosine).
  const cos = (a: number[], b: number[]) => 1 - a.reduce((s, v, j) => s + v * b[j], 0) / ((Math.hypot(...a) * Math.hypot(...b)) || 1);
  const sil = X.map((x, i) => {
    const same = X.filter((_, j) => j !== i && labels[j] === labels[i]);
    if (!same.length) return 0;
    const a = same.reduce((s, y) => s + cos(x, y), 0) / same.length;
    const b = Math.min(...[...new Set(labels)].filter((c) => c !== labels[i]).map((c) => {
      const other = X.filter((_, j) => labels[j] === c);
      return other.reduce((s, y) => s + cos(x, y), 0) / other.length;
    }));
    return (b - a) / Math.max(a, b);
  });
  return { labels, silhouette: sil.reduce((s, v) => s + v, 0) / sil.length, perRow: sil };
}

// ---------- Salary bands + multinomial logistic regression ----------

export const BAND_EDGES = [1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000];
export const BANDS = ["Hasta $1,5M", "$1,5M – $2M", "$2M – $3M", "$3M – $4M", "$4M – $6M", "Más de $6M"];

/** supervised.py · salary_band: the (min, max) midpoint only locates the band; it is never shown as a salary. */
export function salaryBand(row: Pick<Row, "salary_min" | "salary_max">): number | null {
  const vals = [row.salary_min, row.salary_max].filter((v): v is number => v != null);
  if (!vals.length) return null;
  const mid = vals.reduce((a, b) => a + b, 0) / vals.length;
  if (mid < 500_000 || mid > 60_000_000) return null;
  const idx = BAND_EDGES.findIndex((edge) => mid <= edge);
  return idx === -1 ? BAND_EDGES.length : idx;
}

/** supervised.py · LogisticRegression(C=2.0), softmax over the bands seen in training; trained here, now. */
export function trainLogistic(vectors: Vec[], vocab: string[], labels: (number | null)[]) {
  const X = dense(vectors, vocab);
  const classes = [...new Set(labels.filter((l): l is number => l != null))].sort((a, b) => a - b);
  const train = X.map((x, i) => ({ x, y: labels[i] })).filter((d): d is { x: number[]; y: number } => d.y != null);
  const W = classes.map(() => vocab.map(() => 0));
  const b = classes.map(() => 0);
  const lambda = 1 / (2.0 * train.length);
  const softmax = (x: number[]) => {
    const z = classes.map((_, c) => W[c].reduce((s, w, j) => s + w * x[j], b[c]));
    const m = Math.max(...z);
    const e = z.map((v) => Math.exp(v - m));
    const sum = e.reduce((s, v) => s + v, 0);
    return e.map((v) => v / sum);
  };
  for (let it = 0; it < 400; it++) {
    const gW = W.map((w) => w.map(() => 0));
    const gb = b.map(() => 0);
    for (const { x, y } of train) {
      const p = softmax(x);
      classes.forEach((c, k) => {
        const err = p[k] - (c === y ? 1 : 0);
        gb[k] += err;
        x.forEach((v, j) => { if (v) gW[k][j] += err * v; });
      });
    }
    W.forEach((w, k) => w.forEach((_, j) => { w[j] -= 1.5 * (gW[k][j] / train.length + lambda * w[j]); }));
    b.forEach((_, k) => { b[k] -= 1.5 * gb[k] / train.length; });
  }
  const counts = classes.map((c) => labels.filter((l) => l === c).length);
  const majority = classes[counts.indexOf(Math.max(...counts))];
  return { classes, probs: X.map(softmax), majority };
}

// ---------- Graph: co-occurrence, Louvain (phase 1), PageRank, Dijkstra ----------

export type Edge = { a: string; b: string; w: number };

/** graph.py · skill_graph: an edge per pair of skills asked in the same posting (real: MIN_COOCCURRENCE = 2; here 1). */
export function cooccurrence(skillLists: string[][]): { nodes: string[]; edges: Edge[] } {
  const w = new Map<string, number>();
  for (const skills of skillLists) {
    const s = [...new Set(skills)].sort();
    for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++) {
      const key = `${s[i]}|${s[j]}`;
      w.set(key, (w.get(key) ?? 0) + 1);
    }
  }
  const edges = [...w].map(([k, v]) => { const [a, b] = k.split("|"); return { a, b, w: v }; });
  const nodes = [...new Set(skillLists.flat())].sort();
  return { nodes, edges };
}

/** graph.py · louvain_communities (first phase: greedy local moves that raise modularity Q). */
export function louvain(nodes: string[], edges: Edge[]) {
  const adj = new Map(nodes.map((n) => [n, new Map<string, number>()]));
  for (const { a, b, w } of edges) { adj.get(a)!.set(b, w); adj.get(b)!.set(a, w); }
  const k = new Map(nodes.map((n) => [n, [...adj.get(n)!.values()].reduce((s, v) => s + v, 0)]));
  const m2 = [...k.values()].reduce((s, v) => s + v, 0) || 1;
  const comm = new Map(nodes.map((n, i) => [n, i]));
  const tot = new Map(nodes.map((n, i) => [i, k.get(n)!]));
  for (let pass = 0, moved = true; moved && pass < 20; pass++) {
    moved = false;
    for (const n of nodes) {
      const from = comm.get(n)!;
      tot.set(from, tot.get(from)! - k.get(n)!);
      const links = new Map<number, number>();
      for (const [nb, w] of adj.get(n)!) links.set(comm.get(nb)!, (links.get(comm.get(nb)!) ?? 0) + w);
      // ΔQ · 2m = k_i,in − Σ_tot · k_i / m   (m = total edge weight = m2 / 2)
      let best = from, bestGain = (links.get(from) ?? 0) - (tot.get(from)! * k.get(n)!) / (m2 / 2);
      for (const [c, kin] of links) {
        const gain = kin - (tot.get(c)! * k.get(n)!) / (m2 / 2);
        if (gain > bestGain + 1e-12) { best = c; bestGain = gain; }
      }
      tot.set(best, tot.get(best)! + k.get(n)!);
      if (best !== from) { comm.set(n, best); moved = true; }
    }
  }
  const ids = [...new Set(comm.values())];
  const community = new Map(nodes.map((n) => [n, ids.indexOf(comm.get(n)!)]));
  let q = 0;
  for (const a of nodes) for (const b of nodes) {
    if (community.get(a) !== community.get(b)) continue;
    q += (adj.get(a)!.get(b) ?? 0) - (k.get(a)! * k.get(b)!) / m2;
  }
  return { community, modularity: q / m2 };
}

/** graph.py · nx.pagerank(weight="weight"), damping 0.85. */
export function pagerank(nodes: string[], edges: Edge[], d = 0.85) {
  const out = new Map(nodes.map((n) => [n, [] as [string, number][]]));
  for (const { a, b, w } of edges) { out.get(a)!.push([b, w]); out.get(b)!.push([a, w]); }
  let pr = new Map(nodes.map((n) => [n, 1 / nodes.length]));
  for (let it = 0; it < 60; it++) {
    const next = new Map(nodes.map((n) => [n, (1 - d) / nodes.length]));
    let dangling = 0;
    for (const n of nodes) {
      const links = out.get(n)!;
      const total = links.reduce((s, [, w]) => s + w, 0);
      if (!total) { dangling += pr.get(n)!; continue; }
      for (const [nb, w] of links) next.set(nb, next.get(nb)! + d * pr.get(n)! * (w / total));
    }
    for (const n of nodes) next.set(n, next.get(n)! + (d * dangling) / nodes.length);
    pr = next;
  }
  return pr;
}

/** graph.py · transition_routes: Dijkstra over segments with distance 1 − skill-profile similarity. */
export function dijkstra(sim: number[][], from: number, to: number) {
  const n = sim.length;
  const dist = Array(n).fill(Infinity), prev = Array(n).fill(-1), done = Array(n).fill(false);
  dist[from] = 0;
  for (let it = 0; it < n; it++) {
    let u = -1;
    for (let i = 0; i < n; i++) if (!done[i] && (u === -1 || dist[i] < dist[u])) u = i;
    if (u === -1 || dist[u] === Infinity) break;
    done[u] = true;
    for (let v = 0; v < n; v++) {
      if (v === u || sim[u][v] <= 0) continue;
      const alt = dist[u] + (1 - sim[u][v]);
      if (alt < dist[v]) { dist[v] = alt; prev[v] = u; }
    }
  }
  const path: number[] = [];
  for (let v = to; v !== -1; v = prev[v]) path.unshift(v);
  return { path: path[0] === from ? path : [], cost: dist[to] };
}

// ---------- CV matching ----------

/** sextante_api/insights.py · match_cv: ½ · cosine relative to the best posting + ½ · coverage of its skills. */
export function matchCv(cvVec: Vec, cvSkills: string[], rows: { vec: Vec; skills: string[] }[]) {
  const cos = rows.map((r) => cosine(cvVec, r.vec));
  const best = Math.max(...cos, 0);
  const have = new Set(cvSkills);
  return rows.map((r, i) => {
    const text = best > 0 ? cos[i] / best : 0;
    const coverage = r.skills.length ? r.skills.filter((s) => have.has(s)).length / r.skills.length : null;
    const score = coverage == null ? text : 0.5 * text + 0.5 * coverage;
    return { score: Math.round(score * 100), text, coverage, cosine: cos[i],
      matched: r.skills.filter((s) => have.has(s)), missing: r.skills.filter((s) => !have.has(s)) };
  });
}

// ---------- Everything at once ----------

export type Analysis = ReturnType<typeof analyze>;

/** Runs the whole pipeline on the rows (after the append-only store) and an optional CV. */
export function analyze(rows: Row[], cv: string) {
  const repaired = rows.map((r) => ({ ...r, title: repairMojibake(r.title), description: repairMojibake(r.description) }));
  const text = repaired.map((r) => `${r.title} . ${r.description}`);
  const tokens = text.map(keptTokens);
  const hits = repaired.map((r) => matchSkills(tokenize(r.description)));
  const skills = repaired.map((r) => skillSet(`${r.title} ${r.description}`));
  const tfidf = fitTfidf(tokens);
  const { vectors, vocab } = tfidf;
  const sims = vectors.map((a) => vectors.map((b) => cosine(a, b)));
  const sh = repaired.map((r) => shingles(r.description));
  const sigs = sh.map(minhash);
  const pairs: { i: number; j: number; estimate: number; jaccard: number; cosine: number; duplicate: boolean }[] = [];
  for (let i = 0; i < rows.length; i++) for (let j = i + 1; j < rows.length; j++) {
    const estimate = minhashSimilarity(sigs[i], sigs[j]);
    pairs.push({ i, j, estimate, jaccard: jaccard(sh[i], sh[j]), cosine: sims[i][j],
      duplicate: estimate >= LSH_THRESHOLD && sims[i][j] >= DUPLICATE_THRESHOLD });
  }
  const topics = nmf(vectors, vocab, 2);
  const projection = svd2(vectors, vocab);
  // comparison.py compares methods by silhouette; here we pick k the same way.
  const sweep = [2, 3, 4].map((k) => ({ k, ...kmeans(vectors, vocab, k) }));
  const clusters = sweep.reduce((best, c) => (c.silhouette > best.silhouette ? c : best));
  const bands = repaired.map(salaryBand);
  const logistic = trainLogistic(vectors, vocab, bands);
  const graph = cooccurrence(skills);
  const communities = louvain(graph.nodes, graph.edges);
  const ranks = pagerank(graph.nodes, graph.edges);
  // Segment skill profiles → similarity → Dijkstra routes.
  const segIds = [...new Set(clusters.labels)].sort();
  const profile = segIds.map((s) => {
    const v: Vec = new Map();
    skills.forEach((list, i) => { if (clusters.labels[i] === s) list.forEach((k2) => v.set(k2, (v.get(k2) ?? 0) + 1)); });
    const norm = Math.hypot(...v.values()) || 1;
    for (const [t, w] of v) v.set(t, w / norm);
    return v;
  });
  const segSim = profile.map((a) => profile.map((b) => cosine(a, b)));
  const cvTokens = keptTokens(cv);
  const cvSkills = skillSet(cv);
  const cvVec = tfidf.transformTokens(cvTokens);
  const matches = matchCv(cvVec, cvSkills, vectors.map((vec, i) => ({ vec, skills: skills[i] })));
  return { repaired, tokens, hits, skills, tfidf, sims, shingles: sh, sigs, pairs, topics, projection, clusters, sweep,
    bands, logistic, graph, communities, ranks, segIds, segSim, cvSkills, matches };
}
