import Link from "next/link";

const audiences = [
  {
    title: "Candidatos",
    body: "Sube tu CV y mira qué vacantes se parecen de verdad a tu perfil, con su porcentaje de coincidencia y el enlace para postularte.",
  },
  {
    title: "Empleadores",
    body: "Compara salarios, modalidades y habilidades pedidas por segmento ocupacional y ciudad antes de publicar una vacante.",
  },
  {
    title: "Programas académicos",
    body: "Identifica qué habilidades demanda el mercado por nivel educativo y dónde están las brechas de formación.",
  },
];

const steps = [
  ["Captura", "Vacantes del Servicio Público de Empleo y portales como LinkedIn e Indeed, con un esquema común."],
  ["Texto", "Extracción de habilidades con la taxonomía europea ESCO, temas y detección de duplicados."],
  ["Segmentos", "Perfiles ocupacionales agrupados por lo que piden las descripciones, no por el título."],
  ["Señales", "Estimación salarial, grafo de habilidades y rutas de transición entre ocupaciones."],
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Demanda laboral colombiana, medida desde el texto de las vacantes</p>
        <h1>El título dice “analista junior”. La descripción dice todo lo demás.</h1>
        <p className="lead">
          SEXTANTE convierte miles de vacantes colombianas en datos estructurados: qué habilidades se piden,
          cuánto se paga y qué perfiles existen realmente. Y compara tu CV contra todo eso.
        </p>
        <div className="hero-actions">
          <Link href="/cv" className="cta">Analizar mi CV</Link>
          <Link href="/dashboard" className="cta-ghost">Explorar el dashboard</Link>
        </div>
      </section>

      <section className="grid-3">
        {audiences.map((a) => (
          <article key={a.title} className="card">
            <h3>{a.title}</h3>
            <p>{a.body}</p>
          </article>
        ))}
      </section>

      <section className="steps">
        <h2>Cómo funciona</h2>
        <ol>
          {steps.map(([title, body], i) => (
            <li key={title}>
              <span className="step-n">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <h3>{title}</h3>
                <p>{body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
