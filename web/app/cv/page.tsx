"use client";

import { useRef, useState } from "react";
import { toast } from "sonner";

import { Meter } from "@/components/charts";
import { ScanCard } from "@/components/hero-cards";
import { CountUp, Magnetic, Reveal, SplitHeading } from "@/components/motion";
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from "@/components/motion/gsap";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { cop, matchCv, pct, type CvResult, type SegmentAdvice } from "@/lib/api";

export default function CvPage() {
  const [result, setResult] = useState<CvResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"file" | "text">("file");
  const [fileName, setFileName] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  // Swapping between file and text: the new field grows in.
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      gsap.from(".cv-input", { height: 0, opacity: 0, duration: 0.6, ease: "power3.out", clearProps: "height" });
    });
  }, { dependencies: [mode], scope: formRef });

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (mode === "file") form.delete("text");
    else form.delete("file");
    if (form.get("modality") === "any") form.delete("modality");
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = await matchCv(form);
      setResult(body);
      toast.success("CV analizado", { description: `${body.matches.length} vacantes coinciden con tu perfil.` });
    } catch (e) {
      const message = (e as Error).message;
      setError(message);
      toast.error("No pudimos analizar tu CV", { description: message });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="cv">
      <section className="cv-intro">
        <SplitHeading as="h1" onScroll={false}>¿A qué vacantes se parece tu perfil?</SplitHeading>
        <Reveal delay={0.4}>
          <p className="lead">
            Comparamos tu CV con las vacantes del corpus: texto y habilidades ESCO. Te mostramos las vacantes más afines con su
            porcentaje de coincidencia, los nichos donde tu perfil encaja, las rutas para cambiar de rol y las habilidades que te faltan.
          </p>
          <p className="muted">Tu CV se procesa en memoria y se descarta con la respuesta: no se guarda ni se registra.</p>
        </Reveal>
      </section>

      <Reveal delay={0.6}>
        <form className="cv-form" onSubmit={submit} ref={formRef}>
          <ToggleGroup type="single" value={mode} onValueChange={(v) => v && setMode(v as "file" | "text")}
            className="segmented" aria-label="Cómo quieres enviar tu CV">
            <ToggleGroupItem value="file">Subir archivo</ToggleGroupItem>
            <ToggleGroupItem value="text">Pegar texto</ToggleGroupItem>
          </ToggleGroup>
          {mode === "file" ? (
            <label className={`drop cv-input${dragging ? " dragging" : ""}${fileName ? " has-file" : ""}`}
              onDragEnter={() => setDragging(true)} onDragLeave={() => setDragging(false)} onDrop={() => setDragging(false)}>
              <input type="file" name="file" accept=".pdf,.docx,.txt" required
                onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)} />
              <span className="drop-title">{fileName ?? "Arrastra tu CV aquí o haz clic para elegirlo"}</span>
              <span className="muted">PDF, DOCX o TXT · máx. 5 MB</span>
            </label>
          ) : (
            <Textarea name="text" rows={8} minLength={30} required className="cv-input cv-textarea"
              placeholder="Pega aquí tu experiencia, formación y habilidades…" />
          )}
          <div className="filters">
            <Input name="city" placeholder="Ciudad (opcional)" className="field-input" />
            <Select name="modality" defaultValue="any">
              <SelectTrigger className="field-input w-full"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="any">Cualquier modalidad</SelectItem>
                <SelectItem value="Presencial">Presencial</SelectItem>
                <SelectItem value="Remoto">Remoto</SelectItem>
                <SelectItem value="Híbrido">Híbrido</SelectItem>
              </SelectContent>
            </Select>
            <Magnetic>
              <Button type="submit" className="cta" disabled={loading}>{loading ? "Analizando…" : "Analizar CV"}</Button>
            </Magnetic>
          </div>
          {error && <p className="notice error">{error}</p>}
        </form>
      </Reveal>

      {loading && (
        <div className="cv-loading" role="status">
          <ScanCard standalone />
          <p className="muted">Leyendo tu CV y comparándolo con miles de vacantes…</p>
        </div>
      )}
      {result && <Results result={result} />}
    </div>
  );
}

function Results({ result }: { result: CvResult }) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(() => {
    gsap.matchMedia().add(MOTION_OK, () => {
      const q = gsap.utils.selector(ref);
      gsap.to(window, { scrollTo: { y: ref.current!, offsetY: 90 }, duration: 1.3, ease: "power3.inOut", delay: 0.1 });
      gsap.timeline()
        .from(q(".profile"), { y: 40, opacity: 0, filter: "blur(8px)", duration: 1 })
        .from(q(".profile .chip"), { scale: 0.4, opacity: 0, duration: 0.6, ease: "back.out(3)", stagger: 0.05 }, 0.3)
        .from(q(".profile-row > div"), { y: 20, opacity: 0, stagger: 0.12, duration: 0.8 }, 0.5);
      ScrollTrigger.batch(q(".match"), {
        start: "top 92%", once: true,
        onEnter: (batch) => gsap.from(batch, { y: 50, opacity: 0, duration: 0.9, stagger: 0.08, ease: "expo.out" }),
      });
      gsap.from(q(".advice"), {
        y: 30, opacity: 0, duration: 0.9, stagger: 0.1,
        scrollTrigger: { trigger: q(".advice-grid")[0], start: "top 85%", once: true },
      });
    });
  }, { scope: ref });

  return (
    <div className="results" ref={ref}>
      <section className="panel profile">
        <h3>Tu perfil</h3>
        {result.cv_skills.length ? (
          <p className="chips">{result.cv_skills.map((s) => <Badge key={s} variant="outline" className="chip">{s}</Badge>)}</p>
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
              <strong><CountUp value={result.salary_estimate.salary_estimate_cop} format={(v) => cop(v)} /></strong>
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
                  {m.matched_skills.map((s) => <Badge key={s} variant="outline" className="chip have">✓ {s}</Badge>)}
                  {m.missing_skills.slice(0, 4).map((s) => <Badge key={s} variant="outline" className="chip miss">+ {s}</Badge>)}
                </span>
              </div>
              <a className="apply" href={m.url} target="_blank" rel="noopener noreferrer">Postularme</a>
            </li>
          ))}
        </ul>
      </section>

      <div className="grid-2 advice-grid">
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
          {advice.gaps.map((g) => <Badge key={g.skill} variant="outline" className="chip miss">+ {g.skill} · {pct(g.share)}</Badge>)}
        </p>
      )}
    </article>
  );
}
