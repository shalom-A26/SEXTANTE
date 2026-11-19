import type { Metadata } from "next";
import { Hanken_Grotesk, IBM_Plex_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";
import { SystemBackdrop } from "@/components/system-backdrop";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

const grotesk = Hanken_Grotesk({ subsets: ["latin"], weight: ["300", "400", "500"], variable: "--font-sans" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], weight: ["400", "500"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "SEXTANTE: el mercado laboral colombiano, leído desde el texto",
  description:
    "Habilidades, salarios y perfiles ocupacionales extraídos de vacantes colombianas. Sube tu CV y descubre a qué vacantes te pareces.",
};

const LINKS = [
  ["Dashboard", "/dashboard"],
  ["Cómo funciona", "/#como-funciona"],
  ["Dataset en Hugging Face", "https://huggingface.co/datasets/pxtron/vacantes-colombia"],
  ["Analizar mi CV", "/cv"],
];

function Glyph() {
  // A sextant: arc, two radii and the index arm.
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="glyph">
      <path d="M4 18 A 11 11 0 0 1 20 18" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 4 L4 18 M12 4 L20 18 M12 4 L15 18" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <circle cx="12" cy="4" r="1.8" fill="currentColor" />
    </svg>
  );
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={cn("dark", grotesk.variable, mono.variable)}>
      <body>
        <TooltipProvider delayDuration={120}>
        <SystemBackdrop />
        <header className="topbar">
          <nav className="nav-left label">
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/#como-funciona">Cómo funciona</Link>
          </nav>
          <Link href="/" className="brand"><Glyph />SEXTANTE</Link>
          <nav className="nav-right">
            <Link href="/cv" className="roll-pill">
              <span className="roll" data-text="Analizar mi CV ↪">Analizar mi CV ↪</span>
            </Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="footer">
          <span className="pill">Empieza aquí</span>
          <Link href="/cv" className="footer-cta display">
            Analiza <span className="arrow">↪</span> <em>tu CV</em>
          </Link>
          <div className="footer-grid">
            <p className="label">
              Proyecto académico de la Universidad Tecnológica de Bolívar con vacantes públicas del SPE y portales de empleo.
              Tu CV se procesa en memoria y no se guarda.
            </p>
            <ul className="footer-links">
              {LINKS.map(([label, href], i) => (
                <li key={label}>
                  <span className="label">[{String(i + 1).padStart(2, "0")}]</span>
                  <a href={href} {...(href.startsWith("http") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{label}</a>
                </li>
              ))}
            </ul>
          </div>
        </footer>
        <Toaster position="bottom-right" />
        </TooltipProvider>
      </body>
    </html>
  );
}
