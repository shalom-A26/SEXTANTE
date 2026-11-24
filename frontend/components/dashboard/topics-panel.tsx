import { Badge } from "@/components/ui/badge";
import { pct, type Topic } from "@/lib/api";
import { segmentName } from "@/lib/dashboard";
import { formatCount, topicsEnriched, topicTerms, topicTitle } from "@/lib/skills";
import { Panel } from "./panel";
import { TechDetails } from "./tech-details";

const INTRO = "Un tema es un patrón que se repite en cómo están escritas las vacantes: palabras que suelen aparecer juntas. Sirve para ver qué tipos de trabajo dominan el texto, más allá de los cargos.";

function TopicCard({ topic: t, names }: { topic: Topic; names: Record<number, string> }) {
  const terms = topicTerms(t.terms);
  return (
    <li className="topic-card">
      <div className="topic-head">
        <strong>{topicTitle(t)}</strong>
        {t.share != null && <span className="topic-share">{pct(t.share)} <small className="label">de las vacantes</small></span>}
      </div>
      {t.share != null && (
        <span className="barlist-track" aria-hidden><span className="barlist-fill" style={{ width: `${Math.min(100, 100 * t.share)}%` }} /></span>
      )}
      {t.postings != null && <p className="label topic-n">{formatCount(t.postings)} vacantes</p>}
      {!!t.top_titles?.length && <p><span className="label">Cargos típicos:</span> {t.top_titles.slice(0, 4).join(", ")}</p>}
      {!!t.top_segments?.length && (
        <p><span className="label">Perfiles donde aparece:</span>{" "}
          {t.top_segments.slice(0, 3).map((s) => `${segmentName(names, s.segment)} (${pct(s.share)})`).join(", ")}
        </p>
      )}
      {!!t.top_skills?.length && (
        <p className="chips"><span className="label">Habilidades asociadas:</span>
          {t.top_skills.slice(0, 6).map((k) => <Badge key={k} variant="outline" className="chip">{k}</Badge>)}
        </p>
      )}
      {terms.length > 0 && (
        <p className="chips small topic-terms">{terms.map((w) => <Badge key={w} variant="outline" className="chip">{w}</Badge>)}</p>
      )}
    </li>
  );
}

/** NMF topics as cards for an HR reader; without the enriched fields it falls back to a collapsed term list. */
export function TopicsPanel({ topics, names }: { topics?: Topic[]; names: Record<number, string> }) {
  if (!topics?.length) return null;
  if (!topicsEnriched(topics)) {
    return (
      <TechDetails title="Detalle técnico: temas del texto (NMF)">
        <p className="muted">{INTRO} Señal exploratoria (NMF), no categorías validadas.</p>
        <ul className="topic-list">
          {topics.map((t) => (
            <li key={t.topic_id}>
              <strong>{topicTitle(t)}</strong>
              <p className="chips small">{topicTerms(t.terms).map((w) => <Badge key={w} variant="outline" className="chip">{w}</Badge>)}</p>
            </li>
          ))}
        </ul>
      </TechDetails>
    );
  }
  const sorted = [...topics].sort((a, b) => (b.share ?? 0) - (a.share ?? 0));
  return (
    <Panel title="Temas del texto" note={INTRO}>
      <ul className="topic-cards">
        {sorted.map((t) => <TopicCard key={t.topic_id} topic={t} names={names} />)}
      </ul>
      <p className="muted footnote">Temas extraídos automáticamente del texto (NMF sobre TF-IDF): una señal exploratoria, no categorías validadas. Las palabras pequeñas son los términos que definen cada tema.</p>
    </Panel>
  );
}
