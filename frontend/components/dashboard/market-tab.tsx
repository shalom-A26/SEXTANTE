import { BarList, Scatter, SkillGraph } from "@/components/charts";
import type { Dashboard } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { neighbourBars, segmentNames, shareOfTotalBars, topicTerms } from "@/lib/dashboard";
import { Panel } from "./panel";
import { ClusteringTable, CorpusDetails, TechDetails } from "./tech-details";

export function MarketTab({ data }: { data: Dashboard }) {
  const names = segmentNames(data.segments);
  return (
    <div className="grid-1">
      <Panel title="Grafo de habilidades" note={`Habilidades que aparecen juntas en las mismas vacantes; color = comunidad (Louvain, modularidad ${data.graph.metrics.skill_modularity?.toFixed(2) ?? "—"}); tamaño = PageRank. Pasa el cursor o enfoca un nodo con el teclado; Enter lo fija.`}>
        <SkillGraph nodes={data.graph.nodes} edges={data.graph.edges} />
      </Panel>
      <div className="grid-2">
        <Panel title="Proyección de vacantes" note="TF-IDF reducido a 2D (SVD), color = segmento; clic en la leyenda para fijar un segmento">
          <Scatter points={data.projection} names={names} />
        </Panel>
        <Panel title="Fuente de las vacantes" note={`% de vacantes por fuente de captura (n=${data.overview.postings.toLocaleString("es-CO")}); lo que ves depende de lo que cada fuente publica`}>
          <BarList data={shareOfTotalBars(data.overview.sources, data.overview.postings)} unit="percent" />
        </Panel>
        <Panel title="Ocupaciones vecinas" note="Segmentos con perfiles de habilidades similares (similitud, 0-100%): rutas de transición">
          <BarList data={neighbourBars(data.graph.segment_links, names)} unit="percent" />
        </Panel>
      </div>
      <TechDetails title="Detalle técnico: calidad y cobertura del corpus">
        <CorpusDetails overview={data.overview} />
      </TechDetails>
      {data.topics?.length > 0 && (
        <TechDetails title="Detalle técnico: temas del texto (NMF)">
          <p className="muted">Grupos de términos que suelen aparecer juntos en las descripciones; señal exploratoria, no categorías validadas.</p>
          <ul className="topic-list">
            {data.topics.map((t) => (
              <li key={t.topic_id}>
                <span className="label">Tema {t.topic_id + 1}</span>
                <p className="chips small">{topicTerms(t.terms).map((w) => <Badge key={w} variant="outline" className="chip">{w}</Badge>)}</p>
              </li>
            ))}
          </ul>
        </TechDetails>
      )}
      {data.clustering_comparison.methods && (
        <TechDetails title="Detalle técnico: comparación de métodos de agrupamiento">
          <ClusteringTable methods={data.clustering_comparison.methods} />
        </TechDetails>
      )}
    </div>
  );
}
