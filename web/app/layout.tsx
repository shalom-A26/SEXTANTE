import type { Metadata } from "next";
import { Hanken_Grotesk } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const grotesk = Hanken_Grotesk({ subsets: ["latin"], weight: ["300", "400", "500"], variable: "--font" });

export const metadata: Metadata = {
  title: "SEXTANTE: el mercado laboral colombiano, leído desde el texto",
  description:
    "Habilidades, salarios y perfiles ocupacionales extraídos de vacantes colombianas. Sube tu CV y descubre a qué vacantes te pareces.",
};

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
    <html lang="es" className={grotesk.variable}>
      <body>
        <header className="topbar">
          <nav className="nav-left">
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/#como-funciona">Cómo funciona</Link>
          </nav>
          <Link href="/" className="brand"><Glyph />SEXTANTE</Link>
          <nav className="nav-right">
            <Link href="/cv" className="underline">Analizar mi CV</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="footer">
          Proyecto académico de la Universidad Tecnológica de Bolívar con vacantes públicas del SPE y portales de empleo.
          Tu CV se procesa en memoria y no se guarda.
        </footer>
      </body>
    </html>
  );
}
