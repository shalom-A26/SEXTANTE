import Link from "next/link";

import { DuskField, GlowFigure, SextantScale } from "@/components/field";
import { ScanCard, SkillsCard } from "@/components/hero-cards";

const audiences = [
  ["Si buscas empleo", "Mira qué vacantes se parecen de verdad a tu perfil y qué habilidades te faltan para la que quieres."],
  ["Si contratas", "Compara salarios, modalidades y habilidades pedidas en tu sector antes de publicar."],
  ["Si formas talento", "Ve qué piden las empresas según el nivel educativo y dónde están las brechas."],
];

const steps = [
  ["Reunimos vacantes", "Del Servicio Público de Empleo y de portales como LinkedIn e Indeed, en un formato común."],
  ["Leemos la descripción", "Extraemos habilidades con la taxonomía europea ESCO y detectamos vacantes duplicadas."],
  ["Agrupamos perfiles", "Formamos segmentos ocupacionales por lo que piden las vacantes, no por su título."],
  ["Medimos señales", "Estimamos salarios y trazamos rutas entre ocupaciones a partir de habilidades compartidas."],
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <DuskField />
        <div className="hero-veil" />
        <div className="hero-grid">
          <div className="hero-side">
            <SkillsCard />
          </div>
          <div className="hero-center">
            <h1>El mercado laboral, leído desde el texto</h1>
            <div className="horizon-stage">
              <SextantScale />
              <span className="marker left"><i />Alta demanda</span>
              <span className="marker right"><i />Baja demanda</span>
              <GlowFigure />
              <Link href="/cv" className="cta">Analizar mi CV</Link>
            </div>
          </div>
          <div className="hero-side right">
            <ScanCard />
          </div>
        </div>
      </section>

      <section className="about">
        <div className="about-arc" aria-hidden="true" />
        <div className="about-grid">
          <ul className="audiences">
            {audiences.map(([title, body]) => (
              <li key={title}><h3>{title}</h3><p>{body}</p></li>
            ))}
          </ul>
          <div className="about-center">
            <span className="kicker">Sobre SEXTANTE</span>
            <p className="statement">
              Un título como “Analista junior” esconde trabajos muy distintos. Leemos miles de vacantes colombianas
              para saber qué se pide, cuánto se paga y dónde encaja tu perfil.
            </p>
          </div>
          <div className="sources">
            <span className="kicker">Datos de</span>
            <strong>Servicio Público de Empleo</strong>
            <strong>LinkedIn</strong>
            <strong>Indeed</strong>
          </div>
        </div>
      </section>

      <section className="how" id="como-funciona">
        <h2>Cómo funciona</h2>
        <ol>
          {steps.map(([title, body], i) => (
            <li key={title}>
              <span className="step-n">{i + 1}</span>
              <h3>{title}</h3>
              <p>{body}</p>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
