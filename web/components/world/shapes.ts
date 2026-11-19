// Morph targets for the particle swarm, one per chapter. Every shape returns
// exactly `n` points (x, y, z) in local space, roughly 8-10 units across.

type Rand = () => number;

export function prng(seed: number): Rand {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const gauss = (r: Rand) => Math.sqrt(-2 * Math.log(r() + 1e-9)) * Math.cos(2 * Math.PI * r());

function inSphere(r: Rand, radius: number): [number, number, number] {
  // Uniform in a ball, slightly denser at the core so it reads as a volume.
  const u = Math.pow(r(), 0.45);
  const th = r() * Math.PI * 2;
  const ph = Math.acos(2 * r() - 1);
  return [radius * u * Math.sin(ph) * Math.cos(th), radius * u * Math.cos(ph), radius * u * Math.sin(ph) * Math.sin(th)];
}

type Seg = [number[], number[]];

function alongSegments(r: Rand, n: number, segs: Seg[], thick: number, out: Float32Array, offset: number) {
  const lens = segs.map(([a, b]) => Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]));
  const total = lens.reduce((s, l) => s + l, 0);
  for (let i = 0; i < n; i++) {
    let pick = r() * total;
    let k = 0;
    while (pick > lens[k] && k < segs.length - 1) pick -= lens[k++];
    const [a, b] = segs[k];
    const t = r();
    const j = (offset + i) * 3;
    out[j] = a[0] + (b[0] - a[0]) * t + gauss(r) * thick;
    out[j + 1] = a[1] + (b[1] - a[1]) * t + gauss(r) * thick;
    out[j + 2] = a[2] + (b[2] - a[2]) * t + gauss(r) * thick;
  }
}

/** 0 · The sextant of the logo: arc with ticks, two radii and the index arm. */
function sextant(n: number, r: Rand) {
  const out = new Float32Array(n * 3);
  const apex = [0, 4.6, 0];
  const R = 8.8;
  const at = (a: number, rad = R) => [Math.sin(a) * rad, apex[1] - Math.cos(a) * rad, 0];
  const segs: Seg[] = [];
  const A = Math.PI / 4.4;
  for (let i = 0; i < 40; i++) segs.push([at(-A + (2 * A * i) / 40), at(-A + (2 * A * (i + 1)) / 40)]);
  for (let i = 0; i <= 12; i++) segs.push([at(-A + (2 * A * i) / 12), at(-A + (2 * A * i) / 12, R - 0.7)]);
  segs.push([apex, at(-A)], [apex, at(A)], [apex, at(A * 0.35, R + 0.4)]);
  const ball = Math.floor(n * 0.08);
  alongSegments(r, n - ball, segs, 0.3, out, 0);
  for (let i = n - ball; i < n; i++) {
    const [x, y, z] = inSphere(r, 0.7);
    out.set([x + apex[0], y + apex[1], z], i * 3);
  }
  return out;
}

/** 1 · A soft cloud: what a job title alone tells you. */
function cloud(n: number, r: Rand) {
  const out = new Float32Array(n * 3);
  const puffs = [[0, 0, 0, 3.4], [-3.2, -0.6, 0.4, 2.6], [3.3, -0.4, -0.3, 2.7], [-1.4, 1.9, 0, 2.4], [1.8, 1.6, 0.5, 2.3], [-5.2, -1.3, 0, 1.6], [5.3, -1.2, 0.2, 1.7]];
  const vol = puffs.map((p) => p[3] ** 3);
  const total = vol.reduce((s, v) => s + v, 0);
  for (let i = 0; i < n; i++) {
    let pick = r() * total;
    let k = 0;
    while (pick > vol[k] && k < puffs.length - 1) pick -= vol[k++];
    const [cx, cy, cz, rad] = puffs[k];
    const [x, y, z] = inSphere(r, rad);
    out.set([cx + x, cy + y * 0.8, cz + z], i * 3);
  }
  return out;
}

/** 2 · Salary bands as bars. */
function bars(n: number, r: Rand) {
  const out = new Float32Array(n * 3);
  const heights = [2.4, 4.2, 7.2, 8.6, 5.6, 3.2, 1.8];
  const w = 0.8;
  const gap = 2;
  const vol = heights.map((h) => h);
  const total = vol.reduce((s, v) => s + v, 0);
  for (let i = 0; i < n; i++) {
    let pick = r() * total;
    let k = 0;
    while (pick > vol[k] && k < heights.length - 1) pick -= vol[k++];
    const x = (k - (heights.length - 1) / 2) * gap + (r() - 0.5) * w;
    const y = -4.3 + r() * heights[k];
    const z = (r() - 0.5) * w;
    out.set([x, y, z], i * 3);
  }
  return out;
}

/** 3 · Skills graph: communities as clusters, links between them. */
function graph(n: number, r: Rand) {
  const out = new Float32Array(n * 3);
  const nodes: number[][] = [];
  for (let i = 0; i < 10; i++) {
    const a = (i / 10) * Math.PI * 2 + r() * 0.3;
    const rad = 3.2 + r() * 2.6;
    nodes.push([Math.cos(a) * rad, (r() - 0.5) * 6.5, Math.sin(a) * rad * 0.6]);
  }
  const segs: Seg[] = [];
  nodes.forEach((a, i) => {
    const b = nodes[(i + 1) % nodes.length];
    const c = nodes[(i + 3) % nodes.length];
    segs.push([a, b]);
    if (i % 2 === 0) segs.push([a, c]);
  });
  const inNodes = Math.floor(n * 0.55);
  for (let i = 0; i < inNodes; i++) {
    const c = nodes[i % nodes.length];
    const [x, y, z] = inSphere(r, 0.5 + (i % 3) * 0.25);
    out.set([c[0] + x, c[1] + y, c[2] + z], i * 3);
  }
  alongSegments(r, n - inNodes, segs, 0.06, out, inNodes);
  return out;
}

/** 4 · A CV: page outline, text lines and a match badge. */
function document(n: number, r: Rand) {
  const out = new Float32Array(n * 3);
  const W = 3.4;
  const H = 4.6;
  const frame: Seg[] = [[[-W, -H, 0], [W, -H, 0]], [[W, -H, 0], [W, H, 0]], [[W, H, 0], [-W, H, 0]], [[-W, H, 0], [-W, -H, 0]]];
  const lines: Seg[] = [];
  for (let i = 0; i < 9; i++) {
    const y = H - 1.6 - i * 0.82;
    const len = i === 0 ? 3.2 : 2.2 + ((i * 37) % 10) / 3;
    lines.push([[-W + 0.8, y, 0], [-W + 0.8 + len, y, 0]]);
  }
  const badge: Seg[] = [];
  for (let i = 0; i < 24; i++) {
    const a0 = (i / 24) * Math.PI * 2;
    const a1 = ((i + 1) / 24) * Math.PI * 2;
    badge.push([[W - 0.2 + Math.cos(a0) * 1.4, H - 0.4 + Math.sin(a0) * 1.4, 0.3], [W - 0.2 + Math.cos(a1) * 1.4, H - 0.4 + Math.sin(a1) * 1.4, 0.3]]);
  }
  const a = Math.floor(n * 0.3);
  const b = Math.floor(n * 0.5);
  alongSegments(r, a, frame, 0.07, out, 0);
  alongSegments(r, b, lines, 0.09, out, a);
  alongSegments(r, n - a - b, badge, 0.1, out, a + b);
  return out;
}

export function buildShapes(n: number) {
  const r = prng(20261119);
  return [sextant(n, r), cloud(n, r), bars(n, r), graph(n, r), document(n, r)];
}
