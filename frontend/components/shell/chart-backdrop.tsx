"use client";

import { useRef } from "react";

import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { prng } from "@/components/world/shapes";

// A nautical chart behind every page (a sextant's natural habitat): warm dusk
// wash, soft sun blobs, topographic contours, a graticule labelled with
// Colombian coordinates, a compass rose and film grain. Decorative only.

const W = 1600;
const H = 1000;

function contours() {
  const r = prng(1810);
  const hills = [
    { x: 260, y: 240, rings: 9, step: 34 },
    { x: 1280, y: 760, rings: 11, step: 30 },
    { x: 980, y: 180, rings: 6, step: 38 },
  ];
  const paths: string[] = [];
  for (const h of hills) {
    const phases = [r() * 6.28, r() * 6.28, r() * 6.28];
    for (let i = 1; i <= h.rings; i++) {
      const pts: string[] = [];
      for (let k = 0; k <= 96; k++) {
        const a = (k / 96) * Math.PI * 2;
        const wobble = 1 + 0.16 * Math.sin(3 * a + phases[0]) + 0.09 * Math.sin(5 * a + phases[1] + i * 0.3) + 0.05 * Math.sin(9 * a + phases[2]);
        const rad = i * h.step * wobble;
        pts.push(`${(h.x + Math.cos(a) * rad * 1.25).toFixed(1)},${(h.y + Math.sin(a) * rad).toFixed(1)}`);
      }
      paths.push(`M${pts.join("L")}Z`);
    }
  }
  return paths;
}

const CONTOURS = contours();
const LATS = ["12°N", "10°N", "8°N", "6°N", "4°N", "2°N"];
const LONS = ["79°W", "77°W", "75°W", "73°W", "71°W", "69°W", "67°W"];

export function ChartBackdrop() {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      const scroll = { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 1.2 };
      gsap.to(q(".cb-contours"), { y: -120, ease: "none", scrollTrigger: scroll });
      gsap.to(q(".cb-rose"), { rotate: 90, svgOrigin: "1440 160", ease: "none", scrollTrigger: scroll });
    });
  }, { scope: ref });

  return (
    <div className="chart-backdrop" ref={ref} aria-hidden="true">
      <i className="cb-blob sun" /><i className="cb-blob rose" /><i className="cb-blob mauve" />
      <svg className="cb-chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid slice">
        <defs>
          <filter id="cb-grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" /><feColorMatrix values="0 0 0 0 0.18  0 0 0 0 0.07  0 0 0 0 0.07  0 0 0 0.55 0" /></filter>
        </defs>
        <g className="cb-grid">
          {LONS.map((l, i) => {
            const x = 110 + i * 230;
            return <g key={l}><line x1={x} y1="0" x2={x} y2={H} /><text x={x + 6} y={H - 14}>{l}</text></g>;
          })}
          {LATS.map((l, i) => {
            const y = 90 + i * 170;
            return <g key={l}><line x1="0" y1={y} x2={W} y2={y} /><text x="14" y={y - 6}>{l}</text></g>;
          })}
        </g>
        <g className="cb-contours">{CONTOURS.map((d, i) => <path key={i} d={d} className={i % 4 === 0 ? "major" : ""} />)}</g>
        <g className="cb-rose" transform="translate(1440 160)">
          <circle r="64" /><circle r="46" />
          <path d="M0 -78 L9 0 L0 78 L-9 0 Z M-78 0 L0 -9 L78 0 L0 9 Z" />
          <path d="M-40 -40 L5 -5 L40 40 L-5 5 Z M40 -40 L5 5 L-40 40 L-5 -5 Z" className="minor" />
          <text y="-86" textAnchor="middle">N</text>
        </g>
        <rect width={W} height={H} filter="url(#cb-grain)" className="cb-grain" />
      </svg>
    </div>
  );
}
