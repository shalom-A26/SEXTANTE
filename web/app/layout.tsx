import type { Metadata } from "next";
import { Hanken_Grotesk, IBM_Plex_Mono, Instrument_Serif } from "next/font/google";
import Link from "next/link";

import "./globals.css";
import "./design.css";
import { GlowButton } from "@/components/glow-button";
import { Glyph } from "@/components/glyph";
import { FlickerLink } from "@/components/shell/flicker-link";
import { Orb } from "@/components/shell/orb";
import { SoundToggle } from "@/components/shell/sound-toggle";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const grotesk = Hanken_Grotesk({ subsets: ["latin"], weight: ["300", "400", "500"], variable: "--font-sans" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });
const serif = Instrument_Serif({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-serif" });

export const metadata: Metadata = {
  title: "SEXTANTE: el mercado laboral colombiano, leído desde el texto",
  description:
    "Habilidades, salarios y perfiles ocupacionales extraídos de vacantes colombianas. Sube tu CV y descubre a qué vacantes te pareces.",
};

const SECTIONS = [
  ["Inicio", "/"],
  ["Dashboard", "/dashboard"],
  ["Cómo funciona", "/#como-funciona"],
  ["Analizar mi CV", "/cv"],
];
const DATA = [
  ["Hugging Face", "https://huggingface.co/datasets/pxtron/vacantes-colombia"],
  ["Servicio Público de Empleo", "https://www.serviciodeempleo.gov.co/"],
];

const pad = (i: number) => `[${String(i + 1).padStart(2, "0")}]`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={cn(grotesk.variable, mono.variable, serif.variable)}>
      <body>
        <TooltipProvider delayDuration={120}>
          <header className="topbar">
            <Link href="/" className="brand" aria-label="SEXTANTE, inicio"><Glyph /><span>sextan<b>te</b></span></Link>
            <nav className="nav" aria-label="Principal">
              <FlickerLink href="/dashboard">Dashboard</FlickerLink>
              <FlickerLink href="/#como-funciona">Cómo funciona</FlickerLink>
              <FlickerLink href="/#perfiles">Perfiles</FlickerLink>
            </nav>
            <SoundToggle />
            <GlowButton href="/cv" size="sm">Analiza tu CV</GlowButton>
          </header>
          <main>{children}</main>
          <footer className="footer">
            <div className="footer-main">
              <Link href="/cv" className="footer-cta">
                <span className="pill">Empieza aquí</span>
                <span className="display"><i>Analiza</i> tu CV<br />y encuentra<br />tu lugar</span>
              </Link>
              <div className="footer-side">
                <p className="mono">¿Tienes un CV? Te mostramos a qué vacantes colombianas te pareces, qué te falta y hacia dónde moverte.</p>
                <div className="footer-cols">
                  <div>
                    <h4>Secciones ↘</h4>
                    <ul>{SECTIONS.map(([l, h], i) => <li key={l}><span className="label">{pad(i)}</span><Link href={h} className="mono">{l}</Link></li>)}</ul>
                  </div>
                  <div>
                    <h4>Datos ↘</h4>
                    <ul>{DATA.map(([l, h], i) => (
                      <li key={l}><span className="label">{pad(i)}</span><a href={h} className="mono" target="_blank" rel="noopener noreferrer">{l} ↗</a></li>
                    ))}</ul>
                  </div>
                </div>
              </div>
            </div>
            <div className="footer-bottom label">
              <span>SEXTANTE · Universidad Tecnológica de Bolívar</span>
              <span>Tu CV se procesa en memoria y no se guarda</span>
            </div>
          </footer>
          <Orb />
          <Toaster position="bottom-left" />
        </TooltipProvider>
      </body>
    </html>
  );
}
