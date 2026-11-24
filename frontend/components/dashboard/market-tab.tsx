import { Scatter, SkillGraph } from "@/components/charts";
import type { Dashboard } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { segmentNames, topicTerms } from "@/lib/dashboard";
import { Panel } from "./panel";
import { ClusteringTable, CorpusDetails, GraphMetrics, SourceDetails, TechDetails } from "./tech-details";

export function MarketTab({ data }: { data: Dashboard }) {
  const names = segmentNames(data.segments);
  return (
    <div className="grid-1">
      <Panel title="Grafo de habilidades" note="Habilidades que aparecen juntas en las mismas vacantes; color = comunidad (grupo de habilidades que suelen pedirse juntas, nombrado en la leyenda por sus habilidades principales); tamaño = PageRank. Pasa el cursor o enfoca un nodo con el teclado; Enter lo fija.">
        <SkillGraph nodes={data.graph.nodes} edges={data.graph.edges} communities={data.graph.communities} />
      </Panel>
      <TechDetails title="Detalle técnico: métricas del grafo de habilidades">
        <GraphMetrics metrics={data.graph.metrics} />
      </TechDetails>
      <TechDetails title="Detalle técnico: calidad y cobertura del corpus">
        <CorpusDetails overview={data.overview} />
        <SourceDetails overview={data.overview} />
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
      {(data.clustering_comparison.methods || data.projection?.length > 0) && (
        <TechDetails title="Detalle técnico: proyección de vacantes y comparación de métodos de agrupamiento">
          {data.projection?.length > 0 && (
            <div className="tech-block">
              <h4>Proyección de vacantes</h4>
              <p className="muted">TF-IDF reducido a 2D (SVD), color = segmento; clic en la leyenda para fijar un segmento</p>
              <Scatter points={data.projection} names={names} />
            </div>
          )}
          <ClusteringTable methods={data.clustering_comparison.methods} />
        </TechDetails>
      )}
    </div>
  );
}
