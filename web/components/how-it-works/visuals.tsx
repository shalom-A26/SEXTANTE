"use client";

// One small scene per pipeline stage. Each exports its markup; the timeline
// that plays it lives in `timelines` below, keyed by the same step key.
import { PALETTE } from "@/components/charts";
import { gsap } from "@/components/motion/gsap";

function prng(seed: number) {
  return () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Deterministic layouts (identical on server and client).
const rand = prng(20261101);
const CLUSTERS = [[95, 90], [300, 85], [110, 225], [295, 220]];
const CLUSTER_DOTS = Array.from({ length: 44 }, (_, i) => {
  const c = i % CLUSTERS.length;
  const angle = rand() * Math.PI * 2;
  const radius = 8 + rand() * 34;
  return {
    c, sx: 20 + rand() * 360, sy: 20 + rand() * 260,
    x: CLUSTERS[c][0] + Math.cos(angle) * radius, y: CLUSTERS[c][1] + Math.sin(angle) * radius,
  };
});
const SALARY_DOTS = Array.from({ length: 30 }, () => {
  const x = 40 + rand() * 320;
  return { x, y: 250 - (x - 40) * 0.55 + (rand() - 0.5) * 70 };
});
const GRAPH_NODES = Array.from({ length: 14 }, (_, i) => {
  const community = i % 3;
  const center = [[110, 110], [290, 105], [200, 230]][community];
  const angle = (i / 14) * Math.PI * 6 + rand();
  return { x: center[0] + Math.cos(angle) * (30 + rand() * 25), y: center[1] + Math.sin(angle) * (30 + rand() * 20), community };
});
const GRAPH_EDGES = GRAPH_NODES.flatMap((a, i) => GRAPH_NODES.slice(i + 1).map((b, j) => ({ a, b, k: i + j + 1 })))
  .filter(({ a, b }) => (a.community === b.community ? rand() < 0.55 : rand() < 0.07));

const DEFAULT_TERMS = ["call center", "atención cliente", "ventas", "facturación", "excel", "turnos"];

export function Visual({ stepKey, terms }: { stepKey: string; terms: string[] }) {
  switch (stepKey) {
    case "capture":
      return (
        <svg viewBox="0 0 400 300" className="viz">
          {["SPE", "LinkedIn", "Indeed"].map((source, i) => (
            <g key={source}>
              <text x="18" y={78 + i * 80} className="viz-label">{source}</text>
              {[0, 1, 2].map((k) => (
                <circle key={k} className="flow-dot" data-row={i} cx="92" cy={74 + i * 80} r="4"
                  fill={PALETTE[i]} />
              ))}
            </g>
          ))}
          <rect x="240" y="40" width="140" height="220" rx="6" className="viz-frame" />
          {Array.from({ length: 8 }, (_, r) => (
            <rect key={r} className="table-row" x="252" y={56 + r * 25} width={116} height="12" rx="3" />
          ))}
          <text x="240" y="285" className="viz-caption">17 columnas · append-only</text>
        </svg>
      );
    case "clean":
      return (
        <div className="viz viz-html">
          <p className="scramble" data-broken="TÃ©cnico en GestiÃ³n LogÃ­stica">Técnico en Gestión Logística</p>
          <p className="viz-caption">texto reparado (cp1252 → UTF-8)</p>
          <div className="stop-words">
            {["horario", "salario", "prestaciones", "contrato", "turnos"].map((w) => <span key={w}>{w}</span>)}
          </div>
          <p className="viz-caption">palabras de plantilla que se ignoran</p>
        </div>
      );
    case "skills":
      return (
        <div className="viz viz-html">
          <p className="sentence">
            Buscamos auxiliar con experiencia en <mark>atención al cliente</mark>, manejo de <mark>Excel avanzado</mark> y
            capacidad de <mark>trabajo en equipo</mark> para el área de <mark>facturación</mark>.
          </p>
          <div className="skill-chips">
            {["servicio al cliente", "hojas de cálculo", "trabajar en equipo", "procedimientos de facturación"].map((s) => (
              <span key={s}>{s}</span>
            ))}
          </div>
          <p className="viz-caption">ESCO v1.2.1 · coincidencia más larga</p>
        </div>
      );
    case "duplicates":
      return (
        <div className="viz viz-html dup-stage">
          <div className="dup-card a"><b>Asesor comercial</b><i /><i /><i style={{ width: "60%" }} /></div>
          <div className="dup-card b"><b>Asesor comercial - Bogotá</b><i /><i /><i style={{ width: "55%" }} /></div>
          <p className="dup-score"><span className="dup-value">94%</span> similitud</p>
        </div>
      );
    case "tfidf":
      return (
        <div className="viz viz-html">
          <ul className="term-bars">
            {(terms.length ? terms : DEFAULT_TERMS).slice(0, 6).map((term, i) => (
              <li key={term}><span>{term}</span><i style={{ width: `${92 - i * 13}%` }} /></li>
            ))}
          </ul>
          <p className="viz-caption">pesos TF-IDF de un segmento real</p>
        </div>
      );
    case "segments":
      return (
        <svg viewBox="0 0 400 300" className="viz">
          {CLUSTER_DOTS.map((d, i) => (
            <circle key={i} className="seg-dot" cx={d.x} cy={d.y} r="4.5" fill={PALETTE[d.c]}
              data-sx={d.sx} data-sy={d.sy} data-x={d.x} data-y={d.y} data-c={PALETTE[d.c]} />
          ))}
          {CLUSTERS.map(([x, y], i) => (
            <g key={i} className="centroid">
              <line x1={x - 8} y1={y} x2={x + 8} y2={y} /><line x1={x} y1={y - 8} x2={x} y2={y + 8} />
            </g>
          ))}
        </svg>
      );
    case "salary":
      return (
        <svg viewBox="0 0 400 300" className="viz">
          <path d="M40 20 V260 H380" className="viz-axis" />
          {SALARY_DOTS.map((d, i) => <circle key={i} className="sal-dot" cx={d.x} cy={d.y} r="3.5" />)}
          <line className="reg-line" x1="40" y1="250" x2="370" y2="69" />
          <text x="46" y="34" className="viz-label">log(salario)</text>
          <text x="300" y="285" className="viz-label">texto + contexto</text>
        </svg>
      );
    case "graph":
      return (
        <svg viewBox="0 0 400 300" className="viz">
          {GRAPH_EDGES.map(({ a, b }, i) => (
            <line key={i} className="g-edge" x1={a.x} y1={a.y} x2={b.x} y2={b.y} />
          ))}
          {GRAPH_NODES.map((n, i) => (
            <circle key={i} className="g-node" cx={n.x} cy={n.y} r={5 + (i % 4) * 2} fill={PALETTE[n.community + 1]} />
          ))}
        </svg>
      );
    case "cv":
      return (
        <div className="viz viz-html cv-viz">
          <div className="cv-doc"><i /><i className="hit" /><i /><i className="hit" /><i /><span className="cv-beam" /></div>
          <div className="cv-meter"><span className="cv-fill" /><b className="cv-value">92%</b></div>
          <p className="viz-caption">½ texto + ½ habilidades</p>
        </div>
      );
    default:
      return null;
  }
}

// Builds the (paused) timeline that plays a scene; `el` is the scene's wrapper.
export function buildTimeline(stepKey: string, el: HTMLElement): gsap.core.Timeline {
  const q = gsap.utils.selector(el);
  const tl = gsap.timeline({ paused: true, defaults: { ease: "expo.out" } });
  switch (stepKey) {
    case "capture":
      tl.from(q(".table-row"), { scaleX: 0, transformOrigin: "0 50%", duration: 0.6, stagger: 0.12 }, 0.2);
      q(".flow-dot").forEach((dot, i) => {
        tl.fromTo(dot, { x: 0, opacity: 0 }, {
          keyframes: [{ opacity: 1, duration: 0.15 }, { x: 160, duration: 0.9, ease: "power2.in" }, { opacity: 0, duration: 0.15 }],
          repeat: -1, repeatDelay: 0.6,
        }, (i % 3) * 0.35 + Number(dot.getAttribute("data-row")) * 0.2);
      });
      break;
    case "clean": {
      const target = q(".scramble")[0];
      const fixed = target.textContent ?? "";
      tl.set(target, { textContent: target.getAttribute("data-broken") ?? "" }, 0)
        .to(target, {
        duration: 1.8, scrambleText: { text: fixed, chars: "ÃÂ©³¡€", speed: 0.4 },
        ease: "none",
      }, 0.3)
        .from(q(".stop-words span"), { y: 14, opacity: 0, stagger: 0.08, duration: 0.6 }, 0.5)
        .to(q(".stop-words span"), { textDecorationColor: "#f0928e", opacity: 0.35, stagger: 0.12, duration: 0.5 }, 1.8);
      break;
    }
    case "skills":
      tl.from(q("mark"), { backgroundSize: "0% 100%", duration: 0.7, stagger: 0.35, ease: "power2.inOut" }, 0.3)
        .from(q(".skill-chips span"), { y: 18, scale: 0.6, opacity: 0, duration: 0.6, ease: "back.out(2.5)", stagger: 0.35 }, 0.6);
      break;
    case "duplicates": {
      const counter = { v: 0 };
      tl.fromTo(q(".dup-card.a"), { x: -60, rotate: -6 }, { x: 0, rotate: -2, duration: 1.4 }, 0)
        .fromTo(q(".dup-card.b"), { x: 60, rotate: 6 }, { x: 0, rotate: 3, duration: 1.4 }, 0)
        .to(counter, {
          v: 94, duration: 1.6, ease: "power2.out",
          onUpdate: () => { const v = q(".dup-value")[0]; if (v) v.textContent = `${Math.round(counter.v)}%`; },
        }, 0.3);
      break;
    }
    case "tfidf":
      tl.from(q(".term-bars i"), { scaleX: 0, transformOrigin: "0 50%", duration: 1.2, stagger: 0.12 }, 0.2)
        .from(q(".term-bars span"), { x: -12, opacity: 0, stagger: 0.12, duration: 0.6 }, 0.1);
      break;
    case "segments":
      tl.fromTo(q(".seg-dot"), {
        attr: { cx: (_: number, t: Element) => Number(t.getAttribute("data-sx")), cy: (_: number, t: Element) => Number(t.getAttribute("data-sy")) },
        fill: "#ecc0a8",
      }, {
        attr: { cx: (_: number, t: Element) => Number(t.getAttribute("data-x")), cy: (_: number, t: Element) => Number(t.getAttribute("data-y")) },
        fill: (_: number, t: Element) => t.getAttribute("data-c") ?? "#ecc0a8",
        duration: 1.8, ease: "power3.inOut", stagger: { amount: 0.5, from: "random" },
      }, 0.2)
        .from(q(".centroid"), { scale: 0, transformOrigin: "50% 50%", duration: 0.6, ease: "back.out(3)", stagger: 0.1 }, 1.6);
      break;
    case "salary":
      tl.from(q(".viz-axis"), { drawSVG: 0, duration: 0.8 }, 0)
        .from(q(".sal-dot"), { scale: 0, transformOrigin: "50% 50%", duration: 0.5, ease: "back.out(3)", stagger: { amount: 0.8, from: "random" } }, 0.3)
        .from(q(".reg-line"), { drawSVG: 0, duration: 1.2, ease: "power2.inOut" }, 1.1);
      break;
    case "graph":
      tl.from(q(".g-node"), { scale: 0, transformOrigin: "50% 50%", duration: 0.6, ease: "back.out(3)", stagger: 0.06 }, 0)
        .from(q(".g-edge"), { drawSVG: 0, duration: 0.9, stagger: { amount: 0.9, from: "random" } }, 0.4);
      break;
    case "cv": {
      const counter = { v: 0 };
      tl.fromTo(q(".cv-beam"), { top: "0%" }, { top: "100%", duration: 1.2, ease: "power1.inOut" }, 0)
        .from(q(".cv-doc .hit"), { backgroundColor: "rgba(251,241,236,0.25)", duration: 0.4, stagger: 0.3 }, 0.3)
        .from(q(".cv-fill"), { scaleX: 0, transformOrigin: "0 50%", duration: 1.4, ease: "power3.out" }, 1)
        .to(counter, {
          v: 92, duration: 1.4, ease: "power3.out",
          onUpdate: () => { const v = q(".cv-value")[0]; if (v) v.textContent = `${Math.round(counter.v)}%`; },
        }, 1);
      break;
    }
  }
  return tl;
}
