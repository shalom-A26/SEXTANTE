"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { GlowButton } from "@/components/glow-button";
import { CountUp } from "@/components/motion";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { gsap, MOTION_OK, useGSAP } from "@/components/motion/gsap";
import { getDashboard, type Dashboard } from "@/lib/api";

import { analyze, BANDS, cleanTokens, dijkstra, repairMojibake, tokenize, type Analysis } from "./pipeline";
import { RAW_FIELDS, RECAPTURE, ROWS, SAMPLE_CV, type Row } from "./rows";
import { Flow } from "./flow";
import { PipelineMap } from "./pipeline-map";
import { LAYERS, STEPS, type Layer } from "./steps";

const SEG_COLORS = ["#e0761b", "#2f8f7f", "#c8445a", "#6f55c4", "#b8860b"];
const CANONICAL = ["vacancy_id", "source", "url", "title", "company", "city", "department", "published_at", "description",
  "salary_text", "salary_min", "salary_max", "contract_type", "work_modality", "education_level", "experience_text", "captured_at"];
const pad = (n: number, w = 3) => String(n).padStart(w, "0");
const pct = (v: number) => `${Math.round(v * 100)}%`;
// What changes when the row crosses into a new layer.
const ENTER: Record<Layer, string> = {
  bronze: "la vacante queda guardada tal cual llegó",
  silver: "aquí el texto deja de ser crudo: se repara, se limpia y se enriquece",
  gold: "de filas limpias a modelos y agregados listos para consumir",
  serve: "la API usa el oro para responder a tu CV",
};
const key = (r: Row) => (r.source === "spe" ? r.vacancy_id : r.url);

/** Words of the raw text, flagged when the mojibake repair changed them. */
function RepairedText({ text }: { text: string }) {
  return <>{text.split(" ").map((w, i) => {
    const fixed = repairMojibake(w);
    return <span key={i}>{fixed !== w ? <mark className="gd-fixed" title={`antes: ${w}`}>{fixed}</mark> : w} </span>;
  })}</>;
}

function CleanText({ text }: { text: string }) {
  return <>{cleanTokens(text).map((t, i) => <span key={i} className={`gd-tok ${t.kind}`}>{t.t} </span>)}</>;
}

function SkillText({ text, hits }: { text: string; hits: Analysis["hits"][number] }) {
  const tokens = tokenize(text);
  const out: React.ReactNode[] = [];
  let i = 0;
  for (const h of hits) {
    if (h.start > i) out.push(<span key={`t${i}`}>{tokens.slice(i, h.start).join(" ")} </span>);
    out.push(<mark key={`h${h.start}`} className="gd-skill" title={h.skill}>{tokens.slice(h.start, h.end).join(" ")}</mark>, " ");
    i = h.end;
  }
  if (i < tokens.length) out.push(<span key="end">{tokens.slice(i).join(" ")}</span>);
  return <>{out}</>;
}

function Bars({ items, max, format = pct }: { items: [string, number][]; max?: number; format?: (v: number) => string }) {
  const top = max ?? Math.max(...items.map(([, v]) => v), 1e-9);
  return (
    <ul className="gd-bars">
      {items.map(([label, v]) => (
        <li key={label}><span>{label}</span><i><b style={{ width: `${Math.max(2, (v / top) * 100)}%` }} /></i><small className="mono">{format(v)}</small></li>
      ))}
    </ul>
  );
}

/** The extra column the current step adds to the dataset table. */
function StepCell({ step, a, i }: { step: string; a: Analysis; i: number }) {
  const r = a.repaired[i];
  switch (step) {
    case "capture": return <span className="mono">{r.source} · {r.salary_text}</span>;
    case "store": return <span className="mono gd-key">{key(ROWS[i])}</span>;
    case "repair": return <span>{r.title}</span>;
    case "clean": {
      const all = tokenize(`${r.title} ${r.description}`).length;
      return <span className="mono">{all} → <b>{a.tokens[i].length}</b> tokens</span>;
    }
    case "skills": return <span className="gd-chips">{a.skills[i].map((s) => <em key={s}>{s}</em>)}</span>;
    case "duplicates": {
      const p = a.pairs.filter((x) => x.i === i || x.j === i).sort((x, y) => y.estimate - x.estimate)[0];
      const other = p.i === i ? p.j : p.i;
      return <span className={`mono ${p.duplicate ? "gd-dup" : ""}`}>{p.duplicate ? "duplicado de" : "más parecida:"} fila {other + 1} · Ĵ {p.estimate.toFixed(2)} · cos {p.cosine.toFixed(2)}</span>;
    }
    case "tfidf": return <span className="mono">{[...a.tfidf.vectors[i]].sort((x, y) => y[1] - x[1]).slice(0, 3).map(([t, w]) => `${t} ${w.toFixed(2)}`).join(" · ")}</span>;
    case "topics": {
      const w = a.topics.weights[i];
      return <span className="gd-mix"><i style={{ width: `${w[0] * 100}%` }} /><i style={{ width: `${w[1] * 100}%` }} /><small className="mono">T1 {pct(w[0])} · T2 {pct(w[1])}</small></span>;
    }
    case "segments": {
      const c = a.clusters.labels[i];
      return <span className="gd-seg" style={{ "--c": SEG_COLORS[c % SEG_COLORS.length] } as React.CSSProperties}>Segmento {c + 1}</span>;
    }
    case "salary": {
      const band = a.bands[i];
      const probs = a.logistic.probs[i];
      const best = probs.indexOf(Math.max(...probs));
      return band != null
        ? <span className="mono">{BANDS[band]} <small>(dato)</small></span>
        : <span className="mono gd-pred">≈ {BANDS[a.logistic.classes[best]]} · {pct(probs[best])}</span>;
    }
    case "graph": return <span className="gd-chips">{a.skills[i].map((s) => (
      <em key={s} style={{ "--c": SEG_COLORS[(a.communities.community.get(s) ?? 0) % SEG_COLORS.length] } as React.CSSProperties} className="tinted">{s}</em>
    ))}</span>;
    case "cv": {
      const m = a.matches[i];
      return <span className="gd-match"><i><b style={{ width: `${m.score}%` }} /></i><span className="mono">{m.score}%</span></span>;
    }
  }
  return null;
}

function Viz({ step, a, sel, rows, cv, setCv }: { step: string; a: Analysis; sel: number; rows: Row[]; cv: string; setCv: (v: string) => void }) {
  const r = a.repaired[sel];
  switch (step) {
    case "capture": {
      const map = RAW_FIELDS[rows[sel].source];
      return (
        <div className="gd-viz-grid">
          <div>
            <p className="label">Campos de {rows[sel].source.toUpperCase()} → esquema</p>
            <ul className="gd-map">{Object.entries(map).map(([from, to]) => <li key={from}><code>{from}</code><span>→</span><code>{to}</code></li>)}</ul>
          </div>
          <div>
            <p className="label">Las 17 columnas canónicas</p>
            <p className="gd-chips">{CANONICAL.map((c) => <em key={c} className={Object.values(map).includes(c as keyof Row) ? "on" : ""}>{c}</em>)}</p>
          </div>
        </div>
      );
    }
    case "store": {
      const incoming = [...ROWS, RECAPTURE];
      const seen = new Set<string>();
      return (
        <ul className="gd-store">
          {incoming.map((row, i) => {
            const k = key(row);
            const fresh = !seen.has(k);
            seen.add(k);
            return <li key={i} className={fresh ? "" : "dropped"}><span className="mono">{row.captured_at}</span><code>{k}</code><b>{fresh ? "nueva → se guarda" : "ya existe → se descarta"}</b></li>;
          })}
        </ul>
      );
    }
    case "repair": {
      const word = rows[sel].title.split(" ").find((w) => repairMojibake(w) !== w) ?? ROWS[0].title.split(" ")[0];
      const bytes = [...word].map((ch) => ch.codePointAt(0)!);
      return (
        <div className="gd-bytes">
          <p className="label">Por dentro de “{word}”</p>
          <div>{[...word].map((ch, i) => <span key={i}><b>{ch === "­" ? "SHY" : ch}</b><small className="mono">{bytes[i].toString(16).toUpperCase().padStart(2, "0")}</small></span>)}</div>
          <p className="mono">bytes cp1252 → decodificados como UTF-8 → <b>{repairMojibake(word)}</b></p>
        </div>
      );
    }
    case "clean": {
      const t = cleanTokens(`${r.title} ${r.description}`);
      const n = (k: string) => t.filter((x) => x.kind === k).length;
      return <Bars items={[["tokens totales", t.length], ["palabras vacías", n("stop")], ["plantilla", n("template")], ["se conservan", n("keep")]]} format={(v) => String(v)} />;
    }
    case "skills": {
      const hits = a.hits[sel];
      return (
        <div>
          <p className="label">Recorrido del trie en la fila {sel + 1}</p>
          <ol className="gd-trie">{hits.map((h) => {
            const toks = tokenize(r.description).slice(h.start, h.end);
            return <li key={h.start}>{toks.map((t, j) => <code key={j}>{t}</code>)}<span>→</span><b>{h.skill}</b></li>;
          })}</ol>
        </div>
      );
    }
    case "duplicates": {
      const p = a.pairs.filter((x) => x.i === sel || x.j === sel).sort((x, y) => y.estimate - x.estimate)[0];
      const other = p.i === sel ? p.j : p.i;
      const A = a.sigs[sel], B = a.sigs[other];
      return (
        <div>
          <p className="label">Firmas MinHash · fila {sel + 1} vs fila {other + 1}</p>
          <div className="gd-sig">{A.map((v, i) => <i key={i} className={v === B[i] ? "eq" : ""} title={v === B[i] ? "mínimo igual" : "distinto"} />)}</div>
          <dl className="gd-kv">
            <dt>Ĵ estimado (MinHash)</dt><dd>{p.estimate.toFixed(2)} {p.estimate >= 0.7 ? "≥ 0,70 → candidato LSH" : "< 0,70"}</dd>
            <dt>Jaccard exacto</dt><dd>{p.jaccard.toFixed(2)} ({a.shingles[sel].length} vs {a.shingles[other].length} shingles)</dd>
            <dt>Coseno TF-IDF</dt><dd>{p.cosine.toFixed(2)} {p.cosine >= 0.9 ? "≥ 0,90 → duplicado" : "< 0,90"}</dd>
          </dl>
        </div>
      );
    }
    case "tfidf":
      return (
        <div className="gd-viz-grid">
          <div><p className="label">Términos de mayor peso · fila {sel + 1}</p><Bars items={[...a.tfidf.vectors[sel]].sort((x, y) => y[1] - x[1]).slice(0, 8)} format={(v) => v.toFixed(2)} max={1} /></div>
          <div>
            <p className="label">Coseno entre filas</p>
            <table className="gd-heat"><tbody>{a.sims.map((row, i) => (
              <tr key={i}>{row.map((v, j) => <td key={j} style={{ "--v": v } as React.CSSProperties} className={i === sel || j === sel ? "hl" : ""}>{v.toFixed(1)}</td>)}</tr>
            ))}</tbody></table>
          </div>
        </div>
      );
    case "topics":
      return (
        <div className="gd-viz-grid">
          {a.topics.topics.map((t, k) => (
            <div key={k}><p className="label">Tema {k + 1}</p><Bars items={t} format={(v) => v.toFixed(2)} /></div>
          ))}
        </div>
      );
    case "segments": {
      const pts = a.projection;
      const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
      const sx = (x: number) => 30 + ((x - Math.min(...xs)) / ((Math.max(...xs) - Math.min(...xs)) || 1)) * 340;
      const sy = (y: number) => 200 - ((y - Math.min(...ys)) / ((Math.max(...ys) - Math.min(...ys)) || 1)) * 170;
      return (
        <div className="gd-viz-grid">
          <svg viewBox="0 0 400 230" className="gd-scatter" role="img" aria-label="Proyección SVD de las filas">
            {pts.map((p, i) => (
              <g key={i} transform={`translate(${sx(p[0])} ${sy(p[1])})`}>
                <circle r={i === sel ? 11 : 8} fill={SEG_COLORS[a.clusters.labels[i] % SEG_COLORS.length]} />
                <text y="-14" textAnchor="middle">{i + 1}</text>
              </g>
            ))}
          </svg>
          <div>
            <p className="label">Silueta según k</p>
            <Bars items={a.sweep.map((s) => [`k = ${s.k}`, Math.max(0, s.silhouette)] as [string, number])} max={1} format={(v) => v.toFixed(2)} />
            <p className="label">gana k = {new Set(a.clusters.labels).size}</p>
          </div>
        </div>
      );
    }
    case "salary": {
      const probs = a.logistic.probs[sel];
      return (
        <div>
          <p className="label">P(banda | fila {sel + 1}) · softmax entrenada con {a.bands.filter((b) => b != null).length} filas</p>
          <Bars items={a.logistic.classes.map((c, k) => [BANDS[c], probs[k]])} max={1} />
        </div>
      );
    }
    case "graph": {
      const nodes = a.graph.nodes;
      const comms = [...new Set(nodes.map((n) => a.communities.community.get(n)!))];
      const pos = new Map(nodes.map((n) => {
        const c = a.communities.community.get(n)!;
        const members = nodes.filter((m) => a.communities.community.get(m) === c);
        const ca = (comms.indexOf(c) / comms.length) * Math.PI * 2;
        const ma = (members.indexOf(n) / members.length) * Math.PI * 2;
        return [n, [210 + Math.cos(ca) * 120 + Math.cos(ma) * 46, 150 + Math.sin(ca) * 95 + Math.sin(ma) * 40]];
      }));
      const prMax = Math.max(...a.ranks.values());
      const selSeg = a.clusters.labels[sel];
      // The least similar segment: the longest pivot, routed through the skills graph.
      const target = a.segIds.reduce((far, seg) => (a.segSim[selSeg][seg] < a.segSim[selSeg][far] ? seg : far), selSeg);
      const route = dijkstra(a.segSim, selSeg, target).path;
      return (
        <div className="gd-viz-grid">
          <svg viewBox="0 0 420 300" className="gd-graph" role="img" aria-label="Grafo de habilidades">
            {a.graph.edges.map((e, i) => { const p = pos.get(e.a)!, q = pos.get(e.b)!; return <line key={i} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]} strokeWidth={e.w} />; })}
            {nodes.map((n) => { const p = pos.get(n)!; return (
              <g key={n} transform={`translate(${p[0]} ${p[1]})`} className={a.skills[sel].includes(n) ? "hl" : ""}>
                <circle r={4 + (a.ranks.get(n)! / prMax) * 9} fill={SEG_COLORS[a.communities.community.get(n)! % SEG_COLORS.length]} />
                <text y={-12} textAnchor="middle">{n}</text>
              </g>
            ); })}
          </svg>
          <div>
            <dl className="gd-kv">
              <dt>Comunidades (Louvain)</dt><dd>{comms.length}</dd>
              <dt>Modularidad Q</dt><dd>{a.communities.modularity.toFixed(2)}</dd>
              <dt>Más central (PageRank)</dt><dd>{[...a.ranks].sort((x, y) => y[1] - x[1])[0][0]}</dd>
            </dl>
            <p className="label">Ruta desde el segmento {selSeg + 1}</p>
            <p className="mono">{route.length > 1 ? route.map((seg) => `Segmento ${seg + 1}`).join(" → ") : "sin otra ocupación conectada"}</p>
          </div>
        </div>
      );
    }
    case "cv": {
      const m = a.matches[sel];
      return (
        <div className="gd-viz-grid">
          <label className="gd-cv">
            <span className="label">Tu CV (edítalo)</span>
            <textarea value={cv} onChange={(e) => setCv(e.target.value)} rows={7} />
          </label>
          <div>
            <p className="label">Fila {sel + 1}: {m.score}% de coincidencia</p>
            <dl className="gd-kv">
              <dt>Texto (coseno relativo)</dt><dd>{pct(m.text)}</dd>
              <dt>Cobertura de habilidades</dt><dd>{m.coverage == null ? "—" : pct(m.coverage)}</dd>
            </dl>
            <p className="gd-chips">{m.matched.map((s) => <em key={s} className="have">✓ {s}</em>)}{m.missing.map((s) => <em key={s} className="miss">+ {s}</em>)}</p>
          </div>
        </div>
      );
    }
  }
  return null;
}

/** "Cómo funciona": the whole pipeline applied, step by step, to a handful of rows, live in the browser. */
export function Guide() {
  const ref = useRef<HTMLElement>(null);
  const [step, setStep] = useState(0);
  const [rows, setRows] = useState<Row[]>(ROWS);
  const [cv, setCv] = useState(SAMPLE_CV);
  const [sel, setSel] = useState(1);
  const [editing, setEditing] = useState(false);
  const [data, setData] = useState<Dashboard | null>(null);
  const a = useMemo(() => analyze(rows, cv), [rows, cv]);
  const s = STEPS[step];
  const metrics = data && s.metrics ? s.metrics(data) : [];
  const early = step <= 4; // the description stays visible while text is being transformed

  useEffect(() => { getDashboard().then(setData).catch(() => setData(null)); }, []);
  useEffect(() => {
    const go = (e: Event) => setStep(Math.max(0, Math.min(STEPS.length - 1, (e as CustomEvent<number>).detail)));
    window.addEventListener("guide:goto", go);
    return () => window.removeEventListener("guide:goto", go);
  }, []);

  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      gsap.fromTo(q(".gd-band > *"), { autoAlpha: 0, y: 14 }, { autoAlpha: 1, y: 0, duration: 0.6, stagger: 0.05, ease: "expo.out" });
      // The output card slides in from the technique, like data moving through it.
      gsap.fromTo(q(".gd-flow > *"), { autoAlpha: 0, x: -24 }, { autoAlpha: 1, x: 0, duration: 0.7, stagger: 0.12, ease: "expo.out" });
      gsap.fromTo(q(".gd-viz > *, .gd-mini b"), { autoAlpha: 0, y: 12 }, { autoAlpha: 1, y: 0, duration: 0.6, stagger: 0.03, ease: "expo.out" });
    });
  }, { scope: ref, dependencies: [step] });

  const move = (d: number) => setStep((v) => Math.max(0, Math.min(STEPS.length - 1, v + d)));
  const layer = LAYERS[s.layer];
  const enters = step > 0 && STEPS[step - 1].layer !== s.layer ? LAYERS[STEPS[step - 1].layer] : null;

  return (
    <section className="guide" id="como-funciona" ref={ref}>
      <header className="gd-head">
        <span className="pill">Cómo funciona</span>
        <h2 className="display">El pipeline <i>en</i> capas</h2>
        <p className="lead">Seis vacantes de ejemplo (escritas para esta guía) atraviesan las tres capas del sistema. Cada cálculo es real y corre en tu navegador.</p>
        <div className="gd-legend">
          {(["bronze", "silver", "gold"] as const).map((id) => (
            <Tooltip key={id}>
              <TooltipTrigger asChild>
                <button type="button" className="gd-layer" style={{ "--lc": LAYERS[id].color } as React.CSSProperties}>
                  <i />{LAYERS[id].name} <span className="mono">{LAYERS[id].tag}</span>
                </button>
              </TooltipTrigger>
              <TooltipContent className="mono gd-tip">{LAYERS[id].files}</TooltipContent>
            </Tooltip>
          ))}
        </div>
      </header>

      <PipelineMap step={step} onStep={setStep} />

      <div className="gd-band" style={{ "--lc": layer.color } as React.CSSProperties} aria-live="polite">
        <span className="gd-layer static"><i />{layer.name}</span>
        <span className="mono gd-count">{pad(step + 1, 2)} / {STEPS.length}</span>
        <h3>{s.title}</h3>
        <p>{s.caption}</p>
        {enters && <p className="gd-enter mono">{enters.name} → {layer.name}: {ENTER[s.layer]}</p>}
        {metrics.length > 0 && (
          <dl className="gd-metrics">
            {metrics.map((m) => <div key={m.label}><dd><CountUp value={m.value} format={m.format} /></dd><dt>{m.label}{data?.run.synthetic ? " · demo" : ""}</dt></div>)}
          </dl>
        )}
        <div className="gd-nav">
          <GlowButton size="sm" onClick={() => move(-1)} disabled={step === 0}>Anterior</GlowButton>
          <GlowButton size="sm" solid onClick={() => move(1)} disabled={step === STEPS.length - 1}>Siguiente</GlowButton>
        </div>
      </div>

      <Flow step={s} a={a} rows={rows} sel={sel} cv={cv} />

      <div className="gd-stage">
        <div className="gd-viz g-card"><Viz step={s.key} a={a} sel={sel} rows={rows} cv={cv} setCv={setCv} /></div>
        <ol className="gd-minis" aria-label="Filas de ejemplo">
          {rows.map((row, i) => (
            <li key={row.vacancy_id}>
              <button type="button" className={`gd-mini g-card${i === sel ? " sel" : ""}`} onClick={() => setSel(i)} aria-pressed={i === sel}>
                <span className="mono">Fila {i + 1} · {row.source}</span>
                <strong>{step >= 2 ? a.repaired[i].title : row.title}</strong>
                <b><StepCell step={s.key} a={a} i={i} /></b>
              </button>
            </li>
          ))}
        </ol>
      </div>

      <div className="gd-more">
        <details className="g-card">
          <summary className="mono">Ver las 6 filas completas · editar</summary>
          <div className="gd-table">
            <div className="gd-table-head">
              <p className="label">Haz clic en una fila para seguirla</p>
              <button type="button" className="u-link mono" onClick={() => setEditing((v) => !v)}>{editing ? "Listo" : `Editar fila ${sel + 1}`}</button>
            </div>
            {editing && (
              <textarea className="gd-edit" value={rows[sel].description} rows={4} aria-label={`Descripción de la fila ${sel + 1}`}
                onChange={(e) => setRows((rs) => rs.map((r, i) => (i === sel ? { ...r, description: e.target.value } : r)))} />
            )}
            <table>
              <thead><tr><th>#</th><th>Vacante</th>{early && <th>Descripción</th>}<th>{s.short}</th></tr></thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={row.vacancy_id} className={i === sel ? "sel" : ""} onClick={() => setSel(i)}>
                    <td className="mono">{i + 1}</td>
                    <td><strong>{step >= 2 ? a.repaired[i].title : row.title}</strong><small className="mono">{row.source} · {row.city}</small></td>
                    {early && (
                      <td className="gd-desc">
                        {step <= 1 ? row.description : step === 2 ? <RepairedText text={row.description} />
                          : step === 3 ? <CleanText text={`${a.repaired[i].title} ${a.repaired[i].description}`} />
                            : <SkillText text={a.repaired[i].description} hits={a.hits[i]} />}
                      </td>
                    )}
                    <td className="gd-cell"><StepCell step={s.key} a={a} i={i} /></td>
                  </tr>
                ))}
                {s.key === "store" && (
                  <tr className="gd-dropped"><td className="mono">+</td><td><strong>{RECAPTURE.title}</strong><small className="mono">{RECAPTURE.source} · recapturada</small></td>
                    {early && <td className="gd-desc">{RECAPTURE.description}</td>}<td className="gd-cell mono">{key(RECAPTURE)} · ya existe</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </details>
        <details className="g-card">
          <summary className="mono">Más detalle de “{s.short}” · fórmula</summary>
          <p className="gd-lead">{s.lead}</p>
          <ul>{s.inside.map((line) => <li key={line}>{line}</li>)}</ul>
          <pre className="gd-formula"><code>{s.formula}</code></pre>
          <p className="label gd-params">{s.params}</p>
        </details>
      </div>
    </section>
  );
}
