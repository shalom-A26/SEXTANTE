// Procedural dusk field: sky, horizon glow and grass blades drawn in SVG.
// Deterministic (seeded) so server and client render the same markup.

function prng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const W = 1440;
const H = 900;
const HORIZON = 470;
const LAYERS = [
  { color: "#d9917e", width: 0.9, opacity: 0.55 },
  { color: "#b4614b", width: 1.2, opacity: 0.7 },
  { color: "#8c3f2e", width: 1.6, opacity: 0.85 },
  { color: "#5e2420", width: 2.2, opacity: 0.95 },
];

const BANDS = 6; // horizontal slices per depth layer, so the wind can move them out of phase

function blades() {
  const rand = prng(1453);
  const groups = LAYERS.map(() => Array.from({ length: BANDS }, () => [] as string[]));
  for (let i = 0; i < 760; i++) {
    const depth = Math.pow(rand(), 1.6); // more blades far away
    const y = HORIZON + 6 + depth * (H - HORIZON);
    const x = rand() * W;
    const height = 8 + depth * 120 * (0.6 + rand() * 0.6);
    const lean = (rand() - 0.35) * height * 0.55; // wind from the left
    const layer = Math.min(LAYERS.length - 1, Math.floor(depth * LAYERS.length));
    const band = Math.min(BANDS - 1, Math.floor((x / W) * BANDS));
    groups[layer][band].push(
      `M${x.toFixed(1)} ${y.toFixed(1)}Q${(x + lean * 0.3).toFixed(1)} ${(y - height * 0.6).toFixed(1)} ${(x + lean).toFixed(1)} ${(y - height).toFixed(1)}`,
    );
  }
  return groups.map((bands) => bands.map((paths) => paths.join("")));
}

const BLADES = blades();

export function DuskField() {
  return (
    <svg className="field" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9c5468" />
          <stop offset="0.45" stopColor="#c27f88" />
          <stop offset="0.85" stopColor="#e3b0a0" />
          <stop offset="1" stopColor="#efc6ae" />
        </linearGradient>
        <linearGradient id="ground" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#a8594a" />
          <stop offset="0.35" stopColor="#7d3428" />
          <stop offset="1" stopColor="#2e1211" />
        </linearGradient>
        <radialGradient id="sun" cx="0.5" cy="1" r="0.6">
          <stop offset="0" stopColor="#ffe2c8" stopOpacity="0.85" />
          <stop offset="1" stopColor="#ffe2c8" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f3c9b2" stopOpacity="0.55" />
          <stop offset="1" stopColor="#f3c9b2" stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect width={W} height={HORIZON} fill="url(#sky)" />
      <ellipse className="sun" cx={W / 2} cy={HORIZON} rx={W * 0.55} ry={220} fill="url(#sun)" />
      <path d={`M0 ${HORIZON - 18} Q 360 ${HORIZON - 34} 820 ${HORIZON - 14} T ${W} ${HORIZON - 22} V ${HORIZON} H 0 Z`} fill="#b86f6c" opacity="0.5" />
      <rect y={HORIZON} width={W} height={H - HORIZON} fill="url(#ground)" />
      <rect y={HORIZON} width={W} height={60} fill="url(#haze)" />
      {BLADES.map((bands, layer) => (
        <g key={layer} className="blades" data-layer={layer} stroke={LAYERS[layer].color}
          strokeWidth={LAYERS[layer].width} opacity={LAYERS[layer].opacity} fill="none" strokeLinecap="round">
          {bands.map((d, band) => d && <path key={band} className="blade" d={d} />)}
        </g>
      ))}
      <rect className="dusk-shade" width={W} height={H} fill="#2e1211" opacity="0" />
    </svg>
  );
}

