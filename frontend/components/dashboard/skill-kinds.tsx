"use client";

import { useState } from "react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { pct, type SkillKind, type SkillMetrics } from "@/lib/api";
import { segmentName } from "@/lib/dashboard";
import { formatCount, kindGroups } from "@/lib/skills";
import { Panel } from "./panel";

const KIND_COPY: Record<SkillKind, { title: string; note: string }> = {
  transversal: { title: "Transversales", note: "Aparecen con casi cualquier otra habilidad: sirven en muchos perfiles." },
  intermedia: { title: "Intermedias", note: "Se reparten entre varios perfiles sin dominar ninguno." },
  especializada: { title: "Especializadas", note: "Se concentran en un solo perfil: son su sello." },
};

/** Why a skill falls in its group, in one plain sentence. */
function detail(s: SkillMetrics, names: Record<number, string>) {
  const where = s.top_segment != null && s.top_segment_share != null
    ? `${pct(s.top_segment_share)} de sus vacantes están en ${segmentName(names, s.top_segment)}`
    : null;
  return [`se pide junto a ${formatCount(s.degree)} habilidades`, where, `n=${formatCount(s.postings)} vacantes`]
    .filter(Boolean).join(" · ");
}

// Controlled so the detail opens on hover, keyboard focus and tap alike (same as the bar rows).
function KindChip({ skill: s, names }: { skill: SkillMetrics; names: Record<number, string> }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger asChild>
        <button type="button" className={`chip kind-chip kind-${s.kind}`} onClick={() => setOpen((o) => !o)}>
          {s.skill_label}
          {s.kind === "especializada" && s.top_segment_share != null && <small> · {pct(s.top_segment_share)}</small>}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">{s.skill_label}: {detail(s, names)}</TooltipContent>
    </Tooltip>
  );
}

export function SkillKinds({ table, names }: { table?: SkillMetrics[]; names: Record<number, string> }) {
  const groups = kindGroups(table ?? []);
  if (!groups.length) return null;
  return (
    <Panel title="Transversales vs. especializadas" note="Las 30 habilidades más pedidas, según si sirven en casi cualquier perfil o se concentran en uno. Toca una para ver el detalle.">
      <div className="kind-groups">
        {groups.map((g) => (
          <div key={g.kind}>
            <h4>{KIND_COPY[g.kind].title} <small className="label">{g.skills.length}</small></h4>
            <p className="muted">{KIND_COPY[g.kind].note}</p>
            <p className="chips">
              {g.skills.map((s) => <KindChip key={s.esco_uri} skill={s} names={names} />)}
            </p>
          </div>
        ))}
      </div>
      <p className="muted">En las especializadas, el % es la parte de sus vacantes que cae en su perfil principal.</p>
    </Panel>
  );
}
