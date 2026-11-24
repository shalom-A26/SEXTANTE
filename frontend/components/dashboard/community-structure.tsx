import { CountUp } from "@/components/motion";
import { pct, type Dashboard } from "@/lib/api";
import { segmentName, segmentNames } from "@/lib/dashboard";
import { Panel } from "./panel";

// Rules of thumb, not hard cut-offs: Q >= 0.3 is the usual sign of clear community structure.
const CLEAR_Q = 0.3;
const HIGH_CLUSTERING = 0.5;
const LOW_CLUSTERING = 0.2;

/** Graph metrics shown in this panel; the technical detail leaves them out to avoid showing them twice. */
export const STRUCTURE_METRICS = ["density", "average_clustering"];

// Densities are often well under 1%: two significant digits instead of a flat "0%".
const smallPct = (x: number) => `${(100 * x).toLocaleString("es-CO", { maximumSignificantDigits: 2 })}%`;

function modularityText(q: number) {
  return q >= CLEAR_Q
    ? "Los grupos de habilidades están bien definidos: cada perfil tiene su propio paquete."
    : "Los grupos de habilidades se mezclan bastante: los perfiles comparten muchas habilidades.";
}

function clusteringText(c: number) {
  if (c >= HIGH_CLUSTERING) return "Alto: las empresas piden paquetes cerrados de habilidades que van siempre juntas.";
  if (c <= LOW_CLUSTERING) return "Bajo: las habilidades se combinan de forma dispersa, sin paquetes fijos.";
  return "Medio: hay paquetes de habilidades, pero con combinaciones variadas.";
}

/** PMI community structure vs. occupational segments, plus how tightly skills cluster. */
export function CommunityStructure({ data }: { data: Dashboard }) {
  const v = data.community_validation;
  const density = data.graph.metrics?.density;
  const clustering = data.graph.metrics?.average_clustering;
  const q = v?.pmi_modularity;
  const count = v?.pmi_communities ?? v?.communities?.length;
  const segments = v?.segments ?? [];
  if (q == null && !count && !segments.length && density == null && clustering == null) return null;

  const names = segmentNames(data.segments);
  const label = (id: number) => {
    const top = v?.communities?.find((c) => c.community === id)?.top_skills.slice(0, 2);
    return top?.length ? `${top.join(", ")}…` : `Grupo ${id + 1}`;
  };
  return (
    <Panel title="Estructura comunitaria" note="¿Las habilidades forman grupos claros que coinciden con los perfiles ocupacionales? Un grupo (comunidad) es un conjunto de habilidades que se piden juntas.">
      <dl className="stat-row">
        {count != null && count > 0 && (
          <div><dt>Grupos de habilidades</dt><dd><CountUp value={count} /></dd></div>
        )}
        {q != null && (
          <div>
            <dt>Qué tan separados están</dt>
            <dd><CountUp value={q} format={(x) => x.toFixed(2)} /></dd>
            <small>{modularityText(q)}</small>
          </div>
        )}
        {clustering != null && (
          <div>
            <dt>Qué tan cerrados son los paquetes</dt>
            <dd><CountUp value={clustering} format={(x) => x.toFixed(2)} /></dd>
            <small>{clusteringText(clustering)}</small>
          </div>
        )}
        {density != null && (
          <div>
            <dt>Conexiones existentes</dt>
            <dd><CountUp value={density} format={smallPct} /></dd>
            <small>De todas las parejas de habilidades posibles, cuántas aparecen juntas alguna vez.</small>
          </div>
        )}
      </dl>
      {segments.length > 0 && (
        <table className="table">
          <caption>Perfil → grupo de habilidades dominante (qué parte del perfil cae en ese grupo) · cuántos grupos usa</caption>
          <thead><tr><th>Perfil</th><th>Grupo dominante</th><th>Grupos usados</th></tr></thead>
          <tbody>
            {[...segments].sort((a, b) => b.dominant_share - a.dominant_share).map((s) => (
              <tr key={s.segment}>
                <td>{segmentName(names, s.segment)}</td>
                <td>{label(s.dominant_community)} <span className="label">({pct(s.dominant_share)})</span></td>
                <td>{s.communities_used}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="muted footnote">
        Técnico: grupos = comunidades Louvain sobre el grafo ponderado por PMI{v?.pmi_edges != null ? ` (${v.pmi_edges.toLocaleString("es-CO")} conexiones)` : ""};
        «qué tan separados» = modularidad Q (como regla práctica, Q ≥ {CLEAR_Q} suele indicar una estructura de comunidades clara);
        «qué tan cerrados» = coeficiente de agrupamiento promedio; «conexiones existentes» = densidad del grafo.
      </p>
    </Panel>
  );
}
