"use client";

import { useState } from "react";

import { Meter } from "@/components/charts";
import { cop, matchCv, pct, type CvResult, type SegmentAdvice } from "@/lib/api";

export default function CvPage() {
  const [result, setResult] = useState<CvResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"file" | "text">("file");

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (mode === "file") form.delete("text");
    else form.delete("file");
    setLoading(true);
    setError(null);
    try {
      setResult(await matchCv(form));
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="cv">
      <section className="cv-intro">
        <h1>¿A qué vacantes se parece tu perfil?</h1>
        <p className="lead">
          Comparamos tu CV con las vacantes del corpus: texto y habilidades ESCO. Te mostramos las vacantes más afines con su
          porcentaje de coincidencia, los nichos donde tu perfil encaja, las rutas para cambiar de rol y las habilidades que te faltan.
        </p>
        <p className="muted">Tu CV se procesa en memoria y se descarta con la respuesta: no se guarda ni se registra.</p>
      </section>

      <form className="cv-form" onSubmit={submit}>
        <div className="segmented">
          <button type="button" className={mode === "file" ? "active" : ""} onClick={() => setMode("file")}>Subir archivo</button>
          <button type="button" className={mode === "text" ? "active" : ""} onClick={() => setMode("text")}>Pegar texto</button>
        </div>
        {mode === "file" ? (
          <label className="drop">
            <input type="file" name="file" accept=".pdf,.docx,.txt" required />
            <span>PDF, DOCX o TXT · máx. 5 MB</span>
          </label>
        ) : (
          <textarea name="text" rows={8} minLength={30} required placeholder="Pega aquí tu experiencia, formación y habilidades…" />
        )}
        <div className="filters">
          <input name="city" placeholder="Ciudad (opcional)" />
          <select name="modality" defaultValue="">
            <option value="">Cualquier modalidad</option>
            <option>Presencial</option>
            <option>Remoto</option>
            <option>Híbrido</option>
          </select>
          <button className="cta" disabled={loading}>{loading ? "Analizando…" : "Analizar CV"}</button>
        </div>
        {error && <p className="notice error">{error}</p>}
      </form>

      {result && <Results result={result} />}
    </div>
  );
}

function Results({ result }: { result: CvResult }) {
  return (
    <div className="results">
      <section className="panel">
        <h3>Tu perfil</h3>
        {result.cv_skills.length ? (
          <p className="chips">{result.cv_skills.map((s) => <span key={s}>{s}</span>)}</p>
        ) : (
          <p className="muted">No detectamos habilidades del catálogo ESCO presentes en el corpus; el resultado usa solo similitud de texto.</p>
        )}
        <div className="profile-row">
          {result.current_segment && (
            <div><span className="muted">Segmento más cercano</span><strong>{result.current_segment.name}</strong></div>
          )}
          {result.salary_estimate && (
            <div>
              <span className="muted">Salario estimado para tu perfil</span>
              <strong>{cop(result.salary_estimate.salary_estimate_cop)}</strong>
              {result.salary_estimate.salary_band && <small>banda {result.salary_estimate.salary_band}</small>}
            </div>
          )}
        </div>
      </section>

      <section>
        <h2>Vacantes que coinciden con tu perfil</h2>
        <p className="muted">{result.method}</p>
        <ul className="matches">
          {result.matches.map((m) => (
            <li key={`${m.source}-${m.vacancy_id}`} className="match">
              <Meter value={m.match} />
              <div className="match-body">
                <a href={m.url} target="_blank" rel="noopener noreferrer"><strong>{m.title}</strong></a>
                <span className="muted">
                  {[m.company, m.city, m.work_modality].filter(Boolean).join(", ")} en {m.source}
                  {m.salary_min ? ` · ${cop(m.salary_min)}${m.salary_max ? `–${cop(m.salary_max)}` : ""}` : ""}
                </span>
                <span className="chips small">
                  {m.matched_skills.map((s) => <span key={s} className="have">✓ {s}</span>)}
                  {m.missing_skills.slice(0, 4).map((s) => <span key={s} className="miss">+ {s}</span>)}
                </span>
              </div>
              <a className="apply" href={m.url} target="_blank" rel="noopener noreferrer">Postularme</a>
            </li>
          ))}
        </ul>
      </section>

      <div className="grid-2">
        <section className="panel">
          <h3>Nichos donde tu perfil encaja</h3>
          {result.niches.map((n) => <Advice key={n.segment} advice={n} />)}
        </section>
        <section className="panel">
          <h3>¿Cambiar de rol?</h3>
          {result.pivots.length ? result.pivots.map((p) => <Advice key={p.segment} advice={p} />) : (
            <p className="muted">Tu perfil está muy concentrado en un segmento; no hay pivotes cercanos con afinidad suficiente.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function Advice({ advice }: { advice: SegmentAdvice }) {
  return (
    <article className="advice">
      <header>
        <strong>{advice.name}</strong>
        <Meter value={advice.affinity} label={`Afinidad ${advice.affinity}%`} />
      </header>
      <p className="muted">
        {advice.postings.toLocaleString("es-CO")} vacantes · salario mediano {cop(advice.median_salary)} · cubres {advice.skill_coverage.toFixed(0)}% de sus habilidades clave
      </p>
      {advice.route && advice.route.length > 2 && (
        <p className="route">Ruta: {advice.route.map((r) => r.name).join(" → ")}</p>
      )}
      {advice.gaps.length > 0 && (
        <p className="chips small">
          {advice.gaps.map((g) => <span key={g.skill} className="miss">+ {g.skill} · {pct(g.share)}</span>)}
        </p>
      )}
    </article>
  );
}
