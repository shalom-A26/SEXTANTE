import { cop, type Dashboard } from "@/lib/api";

export type Metric = { label: string; value: number; format?: (value: number) => string };

export type Step = {
  key: string;
  title: string;
  lead: string;
  inside: string[];
  algorithm: string;
  metrics?: (data: Dashboard) => Metric[];
};

const percent = (value: number) => `${Math.round(value * 100)}%`;
const decimal = (value: number) => value.toFixed(2);

// What the system really does, stage by stage (see pipeline/, sextante_analysis/, sextante_api/).
export const STEPS: Step[] = [
  {
    key: "capture",
    title: "Reunimos las vacantes",
    lead: "Cada 12 horas descargamos la exportación oficial del Servicio Público de Empleo y cada 30 minutos consultamos portales como LinkedIn e Indeed.",
    inside: [
      "Todas las fuentes se traducen a un mismo esquema de 17 columnas: título, descripción, ciudad, salario, modalidad…",
      "Los almacenes solo agregan: una vacante ya vista nunca se reescribe y conserva la fecha en que la vimos por primera vez.",
      "Se deduplica por código de vacante (SPE) o por URL (portales).",
      "Se publica en Hugging Face, particionado por semana o día de captura.",
    ],
    algorithm: "store = store ∪ { v ∈ nuevas | clave(v) ∉ store }\nclave(v) = vacancy_id  si fuente = SPE\n         = url         si no",
    metrics: (d) => [
      { label: "vacantes en el corpus", value: d.overview.postings },
      { label: "fuentes", value: d.overview.sources.length },
    ],
  },
  {
    key: "clean",
    title: "Limpiamos el texto",
    lead: "Parte de la exportación llega con caracteres dañados y las descripciones repiten plantillas que no dicen nada del trabajo.",
    inside: [
      "Reparamos el texto doblemente codificado: “TÃ©cnico” vuelve a ser “Técnico”.",
      "Normalizamos mayúsculas, tildes y espacios.",
      "Quitamos palabras de plantilla (horario, salario, prestaciones, contrato) para que no definan los grupos.",
    ],
    algorithm: "while patrón_mojibake(t):\n    t = t.encode(\"cp1252\").decode(\"utf-8\")\ntokens = [w for w in t if w ∉ stopwords_es ∪ plantilla]",
  },
  {
    key: "skills",
    title: "Reconocemos habilidades",
    lead: "Leemos cada descripción buscando las 13.939 habilidades de ESCO, la taxonomía europea de competencias, en español.",
    inside: [
      "Un trie de tokens encuentra frases exactas y siempre gana la coincidencia más larga.",
      "Un diccionario de sinónimos colombianos conecta “Excel avanzado”, “facturación” o “Power BI” con su habilidad ESCO.",
      "Una lista de alias ambiguos evita falsos positivos (“transporte” no es logística, “operación” no es cirugía).",
    ],
    algorithm: "for i in posiciones(texto):\n    nodo = trie.raíz; j = i\n    while tokens[j] ∈ nodo: nodo = nodo[tokens[j]]; j += 1\n    if nodo.habilidad: emitir(más_larga)",
    metrics: (d) => [
      { label: "habilidades distintas detectadas", value: d.overview.skills_detected },
      ...(d.overview.skill_mentions ? [{ label: "menciones", value: d.overview.skill_mentions }] : []),
    ],
  },
  {
    key: "duplicates",
    title: "Detectamos duplicados",
    lead: "La misma vacante aparece publicada varias veces o en varios portales. Las encontramos por parecido de texto, no por título.",
    inside: [
      "Cada descripción se parte en fragmentos (shingles) y se resume con una firma MinHash.",
      "LSH agrupa las firmas parecidas sin comparar todas contra todas.",
      "Los candidatos se confirman con similitud coseno sobre TF-IDF.",
    ],
    algorithm: "J(A,B) ≈ P[minhash(A) = minhash(B)]\ncandidatos = LSH(firmas, bandas)\nduplicado ⇔ cos(tfidf_A, tfidf_B) ≥ umbral",
    metrics: (d) => d.overview.duplicate_candidates
      ? [{ label: "pares candidatos", value: d.overview.duplicate_candidates }] : [],
  },
  {
    key: "tfidf",
    title: "Convertimos texto en vectores",
    lead: "Cada vacante se vuelve un vector donde pesan más las palabras propias de esa vacante que las comunes a todas.",
    inside: [
      "TF-IDF con palabras sueltas y pares de palabras, hasta 50.000 términos.",
      "El vocabulario se ajusta sobre una muestra de 120.000 vacantes para controlar la memoria.",
      "NMF descompone la matriz en temas: grupos de términos que aparecen juntos.",
    ],
    algorithm: "tfidf(t, d) = tf(t, d) · log(N / df(t))\nX ≈ W · H   (NMF, temas = filas de H)",
  },
  {
    key: "segments",
    title: "Formamos segmentos ocupacionales",
    lead: "Agrupamos las vacantes por lo que piden, no por cómo se llaman. Así “Analista junior” cae donde corresponde.",
    inside: [
      "SVD reduce los vectores a pocas dimensiones.",
      "K-Means forma los segmentos; los comparamos con Ward y DBSCAN usando la silueta.",
      "Cada segmento se nombra con su título limpio más frecuente.",
    ],
    algorithm: "Z = SVD_k(X)\nmin Σ_c Σ_{x∈c} ‖x − μ_c‖²   (K-Means)\nsilueta = (b − a) / max(a, b)",
    metrics: (d) => {
      const kmeans = d.clustering_comparison.methods?.kmeans?.silhouette_cosine;
      return [
        { label: "segmentos", value: d.overview.segments },
        ...(kmeans != null ? [{ label: "silueta K-Means", value: kmeans, format: decimal }] : []),
      ];
    },
  },
  {
    key: "salary",
    title: "Estimamos salarios",
    lead: "Con las vacantes que publican salario entrenamos modelos que lo estiman a partir del texto y del contexto.",
    inside: [
      "Regresión Ridge sobre el logaritmo del salario, con TF-IDF más ciudad, modalidad, contrato y educación.",
      "Una regresión logística clasifica la vacante en banda baja, media o alta.",
      "Todo se evalúa con validación cruzada de 5 particiones contra una línea base ingenua.",
    ],
    algorithm: "ŷ = exp(w·x + b),  w = argmin ‖Xw − log y‖² + α‖w‖²\nP(banda | x) = softmax(Vx)",
    metrics: (d) => {
      const m = d.salaries.models;
      return [
        ...(m.regression ? [
          { label: "error medio del modelo", value: m.regression.mae_cop, format: cop },
          { label: "error prediciendo la mediana", value: m.regression.baseline_median_mae_cop, format: cop },
        ] : []),
        ...(m.classification && !m.classification.skipped
          ? [{ label: "acierto en banda", value: m.classification.accuracy, format: percent }] : []),
      ];
    },
  },
  {
    key: "graph",
    title: "Conectamos habilidades y ocupaciones",
    lead: "Dos habilidades pedidas en la misma vacante quedan unidas. De ese grafo salen familias de habilidades y caminos entre ocupaciones.",
    inside: [
      "Las comunidades se detectan con Louvain, que maximiza la modularidad.",
      "PageRank y betweenness señalan las habilidades más centrales y las que hacen de puente.",
      "Las rutas entre segmentos se calculan con Dijkstra sobre la similitud de sus habilidades.",
    ],
    algorithm: "w(a,b) = #vacantes que piden a y b\nQ = 1/2m Σ [A_ij − k_i k_j / 2m] δ(c_i, c_j)\nruta = Dijkstra(segmentos, 1 − similitud)",
    metrics: (d) => [
      { label: "habilidades en el grafo", value: Number(d.graph.metrics.skill_nodes ?? d.graph.nodes.length) },
      ...(d.graph.metrics.skill_communities != null
        ? [{ label: "comunidades", value: Number(d.graph.metrics.skill_communities) }] : []),
      ...(d.graph.metrics.skill_modularity != null
        ? [{ label: "modularidad", value: Number(d.graph.metrics.skill_modularity), format: decimal }] : []),
    ],
  },
  {
    key: "cv",
    title: "Comparamos tu CV",
    lead: "Tu CV pasa por el mismo camino: lo leemos, detectamos tus habilidades y lo comparamos con las vacantes más recientes.",
    inside: [
      "El texto se extrae en memoria (PDF, DOCX o TXT) y se descarta con la respuesta.",
      "La coincidencia mezcla el parecido de texto con cuántas habilidades de la vacante tienes.",
      "Los nichos y pivotes salen de los segmentos; las brechas, de las habilidades que piden al menos el 15% de sus vacantes y que no aparecen en tu CV.",
    ],
    algorithm: "match = ½ · cos(cv, v) / máx_v cos(cv, ·)\n      + ½ · |S_cv ∩ S_v| / |S_v|",
  },
];
