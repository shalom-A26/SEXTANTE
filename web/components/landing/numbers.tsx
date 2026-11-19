"use client";

import { useEffect, useState } from "react";

import { CountUp, Reveal, SplitHeading } from "@/components/motion";
import { getDashboard, type Dashboard } from "@/lib/api";

// The corpus in figures, listed like an awards table: label · [count].
export function Numbers() {
  const [data, setData] = useState<Dashboard | null>(null);
  useEffect(() => {
    getDashboard().then(setData).catch(() => setData(null));
  }, []);
  if (!data) return null;

  const o = data.overview;
  const rows: [string, number][] = [
    ["Vacantes en el corpus", o.postings],
    ["Con salario publicado", o.with_salary],
    ["Habilidades ESCO detectadas", o.skills_detected],
    ["Segmentos ocupacionales", o.segments],
    ...o.sources.map((s): [string, number] => [`Fuente · ${s.label}`, s.count]),
  ];

  return (
    <section className="block numbers">
      <div className="numbers-head">
        <SplitHeading className="display">El corpus <span className="arrow">↪</span> en cifras</SplitHeading>
        <p className="label">
          {data.run.synthetic ? "Datos sintéticos de demostración" : `Total · ${o.postings.toLocaleString("es-CO")} vacantes`}
        </p>
      </div>
      <Reveal className="ledger" stagger={0.06}>
        {rows.map(([label, value]) => (
          <div className="ledger-row" key={label}>
            <span>{label}</span>
            <span className="label">[<CountUp value={value} />]</span>
          </div>
        ))}
      </Reveal>
    </section>
  );
}
