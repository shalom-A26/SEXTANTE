import { BarList } from "@/components/charts";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { pct, type Dashboard } from "@/lib/api";
import { bridgeBars, nearbySegments, segmentNames, shareOfTotalBars, skillBars, transversalBars } from "@/lib/dashboard";
import { Panel } from "./panel";

export function CandidatesTab({ data }: { data: Dashboard }) {
  const names = segmentNames(data.segments);
  const transversal = transversalBars(data.graph);
  const bridges = bridgeBars(data.graph);
  return (
    <div className="grid-1">
      <div className="grid-2">
        <Panel title="Habilidades más pedidas" note="% de vacantes que la mencionan">
          <BarList data={skillBars(data.top_skills)} unit="percent" />
        </Panel>
        <Panel title="Segmentos ocupacionales" note="Rango salarial más común (con su mediana) y habilidades distintivas">
          <Accordion type="single" collapsible className="segment-list">
            {data.segments.map((s) => {
              const nearby = nearbySegments(data.graph.segment_links, s.id, names);
              return (
                <AccordionItem key={s.id} value={String(s.id)}>
                  <AccordionTrigger className="segment-trigger">
                    <strong>{s.name}</strong>
                    <span>
                      {s.postings.toLocaleString("es-CO")} vacantes · {s.salary.mode
                        ? `${s.salary.mode}${s.salary.median ? ` (mediana ${s.salary.median})` : ""}`
                        : "sin salario publicado"}
                    </span>
                  </AccordionTrigger>
                  <AccordionContent>
                    <p className="chips">
                      {s.top_skills.map((k) => <Badge key={k.skill} variant="outline" className="chip">{k.skill} · {pct(k.share)}</Badge>)}
                    </p>
                    {nearby.length > 0 && (
                      <p className="nearby">
                        <span className="muted">Ocupaciones cercanas:</span>{" "}
                        {nearby.map((o) => `${o.name} (${pct(o.similarity)})`).join(", ")}
                      </p>
                    )}
                    <div className="segment-mix">
                      {([["Modalidad", s.modality], ["Nivel educativo", s.education], ["Ciudades", s.cities]] as const).map(([title, items]) => (
                        items?.length ? (
                          <div key={title}>
                            <h4>{title}</h4>
                            <BarList data={shareOfTotalBars(items, s.postings)} unit="percent" />
                          </div>
                        ) : null
                      ))}
                    </div>
                    <p className="muted">% de las {s.postings.toLocaleString("es-CO")} vacantes del segmento; solo las categorías más frecuentes, «Sin dato» incluido.</p>
                    {nearby.length > 0 && <p className="muted">Cercanía = similitud de perfiles de habilidades (0-100%): rutas de transición posibles.</p>}
                    <p className="muted">Términos: {s.terms.join(", ")}</p>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </Panel>
      </div>
      {(transversal.length > 0 || bridges.length > 0) && (
        <Panel title="Habilidades transversales y puente" note="Calculado sobre el grafo completo de habilidades que aparecen juntas en las vacantes.">
          <div className="rank-pair">
            {transversal.length > 0 && (
              <div>
                <h4>Transversales</h4>
                <p className="muted">Aparecen junto a más habilidades distintas: te abren más puertas. El número es cuántas.</p>
                <BarList data={transversal} unit="count" />
              </div>
            )}
            {bridges.length > 0 && (
              <div>
                <h4>Puente</h4>
                <p className="muted">Conectan áreas que casi no se tocan: te ayudan a cambiar de campo. La barra compara con la más puente.</p>
                <BarList data={bridges} unit="relative" />
              </div>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}
