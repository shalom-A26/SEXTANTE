import type { Metadata } from "next";
import { Fragment_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";
import "./design.css";
import { GlowButton } from "@/components/glow-button";
import { ChartBackdrop } from "@/components/shell/chart-backdrop";
import { FlickerLink } from "@/components/shell/flicker-link";
import { Orb } from "@/components/shell/orb";
import { SoundToggle } from "@/components/shell/sound-toggle";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Wordmark } from "@/components/wordmark";
import { cn } from "@/lib/utils";

// Boska (display serif) and Switzer (text) come from Fontshare's CDN: the ITF
// licence allows web use but not redistributing the files in this repo.
const FONTSHARE = "https://api.fontshare.com/v2/css?f[]=boska@400,500,400i&f[]=switzer@300,400,500&display=swap";
const mono = Fragment_Mono({ subsets: ["latin"], weight: "400", style: ["normal", "italic"], variable: "--font-mono" });

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
    <html lang="es" className={cn(mono.variable)}>
      <head>
        <link rel="preconnect" href="https://api.fontshare.com" />
        <link rel="preconnect" href="https://cdn.fontshare.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href={FONTSHARE} />
      </head>
      <body>
        <TooltipProvider delayDuration={120}>
          <ChartBackdrop />
          <header className="topbar">
            <Link href="/" className="brand" aria-label="SEXTANTE, inicio"><Wordmark /></Link>
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
