"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Floating orb in the corner: a shortcut to the CV analysis from anywhere. */
export function Orb() {
  if (usePathname() === "/cv") return null;
  return (
    <Link href="/cv" className="orb" aria-label="Analizar mi CV">
      <span className="orb-ball" aria-hidden="true" />
      <span className="orb-label mono">Analiza tu CV</span>
    </Link>
  );
}
