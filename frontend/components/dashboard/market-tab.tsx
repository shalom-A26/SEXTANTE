import { Scatter, SkillGraph } from "@/components/charts";
import type { Dashboard } from "@/lib/api";
import { segmentNames } from "@/lib/dashboard";
import { CommunityStructure, STRUCTURE_METRICS } from "./community-structure";
import { Panel } from "./panel";
import { ClusteringTable, GraphMetrics, TechDetails } from "./tech-details";
import { TopicsPanel } from "./topics-panel";

export function MarketTab({ data }: { data: Dashboard }) {
  const names = segmentNames(data.segments);
  return (
    <div className="grid-1">
      <Panel title="Grafo de habilidades" note="Habilidades que aparecen juntas en las mismas vacantes; color = comunidad (grupo de habilidades que suelen pedirse juntas, nombrado en la leyenda por sus habilidades principales); tamaño = PageRank. Pasa el cursor o enfoca un nodo con el teclado; Enter lo fija.">
        <SkillGraph nodes={data.graph.nodes} edges={data.graph.edges} communities={data.graph.communities} />
      </Panel>
      <CommunityStructure data={data} />
      <TopicsPanel topics={data.topics} names={names} />
      <TechDetails title="Detalle técnico: métricas del grafo de habilidades">
        <GraphMetrics metrics={data.graph.metrics} omit={STRUCTURE_METRICS} />
      </TechDetails>
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
