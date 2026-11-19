import { BANDS, cleanTokens, type Analysis } from "./pipeline";
import { RAW_FIELDS, type Row } from "./rows";
import { LAYERS, type Step } from "./steps";

const pct = (v: number) => `${Math.round(v * 100)}%`;
const words = (text: string, n: number) => text.split(/\s+/).slice(0, n).join(" ") + (text.split(/\s+/).length > n ? "…" : "");
const Chips = ({ items, kind }: { items: string[]; kind?: string }) => (
  <span className="gd-chips">{items.map((s) => <em key={s} className={kind}>{s}</em>)}</span>
);

/** What goes into the technique and what comes out, for the selected row. */
function io(step: string, a: Analysis, rows: Row[], i: number, cv: string): [React.ReactNode, React.ReactNode] {
  const raw = rows[i];
  const r = a.repaired[i];
  switch (step) {
    case "capture": {
      const [field] = Object.entries(RAW_FIELDS[raw.source]).find(([, to]) => to === "title")!;
      return [<code key="i">{field}: “{raw.title}”</code>, <code key="o">title: “{raw.title}” · city · salary_text · …17</code>];
    }
    case "store": {
      const key = raw.source === "spe" ? raw.vacancy_id : raw.url;
      return [<code key="i">clave = {key}</code>, <span key="o">nueva → se guarda<br /><small className="mono">captured_at {raw.captured_at}</small></span>];
    }
    case "repair": return [<span key="i" className="gd-raw">{raw.title}</span>, <strong key="o">{r.title}</strong>];
    case "clean": {
      const t = cleanTokens(`${r.title} ${r.description}`);
      return [<span key="i">{words(`${r.title} ${r.description}`, 9)}</span>,
        <span key="o">{t.filter((x) => x.kind === "keep").slice(0, 8).map((x) => x.t).join(" · ")}…</span>];
    }
    case "skills": return [<span key="i">{a.tokens[i].slice(0, 10).join(" ")}…</span>, <Chips key="o" items={a.skills[i]} />];
    case "duplicates": {
      const p = a.pairs.filter((x) => x.i === i || x.j === i).sort((x, y) => y.estimate - x.estimate)[0];
      const other = p.i === i ? p.j : p.i;
      return [<span key="i">{a.shingles[i].length} shingles de 3 palabras</span>,
        p.duplicate ? <strong key="o" className="gd-dup">duplicado de la fila {other + 1}<br /><small className="mono">Ĵ {p.estimate.toFixed(2)} · cos {p.cosine.toFixed(2)}</small></strong>
          : <span key="o">sin duplicado<br /><small className="mono">más parecida: fila {other + 1} · Ĵ {p.estimate.toFixed(2)}</small></span>];
    }
    case "tfidf": return [<span key="i">{a.tokens[i].length} tokens limpios</span>,
      <span key="o" className="mono">{[...a.tfidf.vectors[i]].sort((x, y) => y[1] - x[1]).slice(0, 3).map(([t, w]) => `${t} ${w.toFixed(2)}`).join(" · ")}</span>];
    case "topics": {
      const w = a.topics.weights[i];
      return [<span key="i">vector de {a.tfidf.vectors[i].size} términos</span>, <span key="o" className="mono">Tema 1 {pct(w[0])} · Tema 2 {pct(w[1])}</span>];
    }
    case "segments": return [<span key="i">vector de {a.tfidf.vectors[i].size} términos</span>, <strong key="o">Segmento {a.clusters.labels[i] + 1}</strong>];
    case "salary": {
      const band = a.bands[i];
      const p = a.logistic.probs[i];
      const best = p.indexOf(Math.max(...p));
      return [<span key="i">{raw.salary_text}</span>, band != null
        ? <strong key="o">{BANDS[band]}<br /><small className="mono">banda leída del rango</small></strong>
        : <strong key="o" className="gd-pred">≈ {BANDS[a.logistic.classes[best]]}<br /><small className="mono">predicha · {pct(p[best])}</small></strong>];
    }
    case "graph": {
      const central = [...a.skills[i]].sort((x, y) => (a.ranks.get(y) ?? 0) - (a.ranks.get(x) ?? 0))[0];
      const comms = new Set(a.skills[i].map((s) => a.communities.community.get(s)));
      return [<Chips key="i" items={a.skills[i].slice(0, 4)} />, <span key="o">{comms.size} familia{comms.size > 1 ? "s" : ""} · más central: <strong>{central ?? "—"}</strong></span>];
    }
    case "cv": {
      const m = a.matches[i];
      return [<span key="i">{words(cv, 10)}</span>, <strong key="o">{m.score}% con la fila {i + 1}</strong>];
    }
  }
  return [null, null];
}

export function Flow({ step, a, rows, sel, cv }: { step: Step; a: Analysis; rows: Row[]; sel: number; cv: string }) {
  const [input, output] = io(step.key, a, rows, sel, cv);
  const color = LAYERS[step.layer].color;
  return (
    <div className="gd-flow" style={{ "--lc": color } as React.CSSProperties}>
      <div className="gd-io g-card"><span className="label">Entra · fila {sel + 1}</span><div>{input}</div></div>
      <span className="gd-arrow" aria-hidden="true" />
      <div className="gd-tech g-card">
        <span className="label">{LAYERS[step.layer].name} · técnica</span>
        <strong>{step.short}</strong>
        <span className="gd-param mono">{step.param}</span>
      </div>
      <span className="gd-arrow" aria-hidden="true" />
      <div className="gd-io out g-card"><span className="label">Sale</span><div>{output}</div></div>
    </div>
  );
}
