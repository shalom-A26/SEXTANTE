"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { pct, type Dashboard, type SkillPivot } from "@/lib/api";
import { segmentName, segmentNames } from "@/lib/dashboard";
import { pivotOrigins, pivotTargets } from "@/lib/skills";

/** Pick an origin profile and see its nearest profiles: skills already shared and skills still missing. */
export function SkillPivots({ pivots, segments }: { pivots: SkillPivot[]; segments: Dashboard["segments"] }) {
  const names = segmentNames(segments);
  const origins = pivotOrigins(pivots, segments, names);
  const [picked, setPicked] = useState<number | null>(null);
  const from = picked ?? origins[0]?.id;
  if (from === undefined) return null;
  const targets = pivotTargets(pivots, from);
  return (
    <div className="pivots">
      <h4>Para pivotar entre roles</h4>
      <p className="muted">Comparación entre perfiles del mercado, no con tu CV. Elige un perfil de origen: verás los perfiles más cercanos, qué habilidades piden ambos y cuáles pide el destino que el origen casi no pide.</p>
      <Select value={String(from)} onValueChange={(v) => setPicked(Number(v))}>
        <SelectTrigger className="pivot-select w-full" aria-label="Perfil de origen"><SelectValue /></SelectTrigger>
        <SelectContent>
          {origins.map((o) => <SelectItem key={o.id} value={String(o.id)}>{o.name}</SelectItem>)}
        </SelectContent>
      </Select>
      <ul className="pivot-list">
        {targets.map((t) => (
          <li key={t.to_segment}>
            <p className="pivot-head">
              <strong>{segmentName(names, t.to_segment)}</strong>
              <span className="label">cercanía {pct(t.similarity)}</span>
            </p>
            {t.shared.length > 0 && (
              <p className="chips small"><span className="label">Piden ambos:</span>
                {t.shared.map((s) => <Badge key={s} variant="outline" className="chip have">{s}</Badge>)}
              </p>
            )}
            {t.missing.length > 0 && (
              <p className="chips small"><span className="label">Para dar el salto:</span>
                {t.missing.map((s) => <Badge key={s} variant="outline" className="chip miss">{s}</Badge>)}
              </p>
            )}
            {t.shared.length === 0 && t.missing.length === 0 && (
              <p className="muted small">
                {t.similarity >= 0.7
                  ? "Piden casi las mismas habilidades: el cambio depende más de la experiencia que de aprender algo nuevo."
                  : "No hay habilidades específicas que destaquen entre estos dos perfiles."}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
