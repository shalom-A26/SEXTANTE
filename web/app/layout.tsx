import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "SEXTANTE — demanda laboral en Colombia",
  description:
    "Habilidades, salarios y perfiles ocupacionales extraídos de vacantes colombianas. Sube tu CV y descubre a qué vacantes te pareces.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">SEXTANTE</Link>
          <nav>
            <Link href="/dashboard">Dashboard</Link>
            <Link href="/cv" className="cta-small">Analizar mi CV</Link>
          </nav>
        </header>
        <main>{children}</main>
        <footer className="footer">
          Proyecto académico · Universidad Tecnológica de Bolívar · Datos públicos de vacantes (SPE y portales de empleo).
          Tu CV se procesa en memoria y no se almacena.
        </footer>
      </body>
    </html>
  );
}
