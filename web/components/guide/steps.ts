import { type Dashboard } from "@/lib/api";

export type Metric = { label: string; value: number; format?: (value: number) => string };

export type Step = {
  key: string;
  title: string;
  lead: string;
  inside: string[];
  formula: string;
  params: string;
  metrics?: (data: Dashboard) => Metric[];
};

const percent = (value: number) => `${Math.round(value * 100)}%`;
const decimal = (value: number) => value.toFixed(2);

// The whole pipeline, stage by stage (pipeline/, sextante_analysis/, sextante_api/).
export const STEPS: Step[] = [
  {
    key: "capture",
    title: "Captura y esquema canónico",
    lead: "Cada 12 horas bajamos la exportación oficial del SPE y cada 30 minutos consultamos portales como LinkedIn e Indeed. Cada fuente nombra sus campos a su manera.",
    inside: [
      "Todo se traduce a un mismo esquema de 17 columnas en un orden fijo: el contrato que leen todas las etapas.",
      "captured_at se estampa al capturar; published_at se guarda tal como lo da la fuente.",
      "Respetamos robots.txt, nos identificamos con un User-Agent propio y no guardamos datos de candidatos.",
    ],
    formula: "fila_canónica = normalize(renombrar(fila_fuente, mapa_fuente))\nvalidate(fila) ⇔ columnas == SCHEMA_17 (en orden)",
    params: "pipeline/schema.py · 17 columnas · SPE cada 12 h · JobSpy cada 30 min",
    metrics: (d) => [
      { label: "vacantes en el corpus", value: d.overview.postings },
      { label: "fuentes", value: d.overview.sources.length },
    ],
  },
  {
    key: "store",
    title: "Almacén que solo agrega",
    lead: "Una vacante ya vista nunca se reescribe: conserva la primera fecha en que la vimos. Si vuelve a llegar, se descarta la copia nueva.",
    inside: [
      "La clave es el código de vacante en el SPE y la URL en los portales.",
      "Por eso los archivos publicados en Hugging Face son inmutables y se particionan por fecha de captura.",
      "Mira la fila que llega repetida: misma URL, se queda la primera captura.",
    ],
    formula: "store = store ∪ { v ∈ nuevas | clave(v) ∉ store }\nclave(v) = vacancy_id  si fuente = SPE\n         = url         si no",
    params: "pipeline/store.py · append(keep=\"first\") · devuelve solo las filas nuevas",
  },
  {
    key: "repair",
    title: "Reparamos el texto dañado",
    lead: "Parte de la exportación llega doblemente codificada: “TÃ©cnico” era “Técnico”. Se repara antes de leer nada.",
    inside: [
      "El patrón Ã+byte delata UTF-8 leído como cp1252.",
      "Se vuelve a bytes con cp1252 y se decodifica como UTF-8, hasta dos rondas.",
      "Si el texto ya está sano, pasa intacto.",
    ],
    formula: "while patrón_mojibake(t) and rondas < 2:\n    t = t.encode(\"cp1252\").decode(\"utf-8\")",
    params: "sextante_analysis/cleaning.py · repair_mojibake",
  },
  {
    key: "clean",
    title: "Limpiamos y normalizamos",
    lead: "Minúsculas, sin tildes, solo palabras. Después quitamos lo que no describe el trabajo: palabras vacías y frases de plantilla.",
    inside: [
      "Normalización NFKD: “Logística” y “logistica” son el mismo token.",
      "Las palabras vacías (de, la, para…) no aportan significado.",
      "Las plantillas (“empresa líder del sector”, “¡postúlate ya!”, horario, prestaciones) se repiten en miles de avisos y deformarían los grupos.",
    ],
    formula: "tokens = [^\\W_]+ ( NFKD(casefold(t)) sin diacríticos )\ntokens = [w for w in tokens if w ∉ stopwords_es ∪ plantilla]",
    params: "taxonomy.py · normalize_text · lista de plantilla en cleaning.py",
  },
  {
    key: "skills",
    title: "Reconocemos habilidades ESCO",
    lead: "Buscamos en cada descripción las habilidades de ESCO, la taxonomía europea, en español y con sinónimos colombianos.",
    inside: [
      "Un trie de tokens recorre el texto desde cada palabra; siempre gana la coincidencia más larga (“excel avanzado” antes que “excel”).",
      "Los sinónimos conectan “Power BI” o “facturación electrónica” con su habilidad ESCO.",
      "Una lista de alias ambiguos evita falsos positivos.",
    ],
    formula: "for i in posiciones(texto):\n    nodo = trie.raíz; j = i\n    while tokens[j] ∈ nodo: nodo = nodo[tokens[j]]; j += 1\n    if nodo.habilidad: emitir(más_larga); i = j",
    params: "taxonomy.py · EscoMatcher · ESCO v1.2.1 (aquí, un extracto de 23 habilidades)",
    metrics: (d) => [
      { label: "habilidades distintas detectadas", value: d.overview.skills_detected },
      ...(d.overview.skill_mentions ? [{ label: "menciones", value: d.overview.skill_mentions }] : []),
    ],
  },
  {
    key: "duplicates",
    title: "Detectamos duplicados por texto",
    lead: "La misma vacante aparece en varios portales con otra clave. La encontramos por parecido del texto, no por el título.",
    inside: [
      "Cada descripción se parte en fragmentos de 3 palabras (shingles).",
      "MinHash resume cada conjunto en 64 números: la fracción de mínimos iguales estima el Jaccard.",
      "LSH propone candidatos con Jaccard estimado ≥ 0,70 sin comparar todos contra todos; se confirman con coseno TF-IDF ≥ 0,90.",
    ],
    formula: "J(A,B) = |A ∩ B| / |A ∪ B| ≈ P[minhash(A) = minhash(B)]\ncandidato ⇔ Ĵ ≥ 0,70 (LSH)\nduplicado ⇔ cos(tfidf_A, tfidf_B) ≥ 0,90",
    params: "duplicates.py · shingles de 3 · MinHash(num_perm=64, seed=42) · umbral 0,90",
    metrics: (d) => d.overview.duplicate_postings
      ? [
        { label: "vacantes con posible duplicado", value: d.overview.duplicate_postings },
        { label: "grupos de duplicados", value: d.overview.duplicate_groups ?? 0 },
      ]
      : d.overview.duplicate_candidates ? [{ label: "pares candidatos", value: d.overview.duplicate_candidates }] : [],
  },
  {
    key: "tfidf",
    title: "Convertimos texto en vectores",
    lead: "Cada vacante se vuelve un vector: pesa más una palabra frecuente en esa vacante y rara en las demás.",
    inside: [
      "Palabras sueltas y pares de palabras (1–2 gramas).",
      "Cada vector se normaliza a largo 1: el coseno entre dos vectores mide su parecido.",
      "En el corpus real, un término debe aparecer en al menos 2 vacantes (min_df=2); aquí, con seis filas, basta una.",
    ],
    formula: "tfidf(t, d) = tf(t, d) · (ln((1 + N) / (1 + df(t))) + 1)\nv_d ← v_d / ‖v_d‖₂     cos(a, b) = a · b",
    params: "features.py · TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_df=0.98)",
  },
  {
    key: "topics",
    title: "Descubrimos temas",
    lead: "NMF descompone la matriz de vectores en temas: grupos de términos que suelen aparecer juntos, y cuánto de cada tema tiene cada vacante.",
    inside: [
      "X ≈ W · H, todo no negativo: H dice qué términos forman cada tema; W, la mezcla de temas de cada vacante.",
      "Se ajusta con actualizaciones multiplicativas desde una semilla fija.",
      "En el corpus real se buscan 12 temas; aquí 2.",
    ],
    formula: "X ≈ W · H\nH ← H ∘ (WᵀX) / (WᵀWH)\nW ← W ∘ (XHᵀ) / (WHHᵀ)",
    params: "features.py · NMF(n_components=12, random_state=42)",
  },
  {
    key: "segments",
    title: "Formamos segmentos ocupacionales",
    lead: "Agrupamos por lo que piden, no por cómo se llaman. Así “Analista junior” cae donde corresponde.",
    inside: [
      "SVD proyecta los vectores a pocas dimensiones (aquí, 2 para dibujarlos).",
      "K-Means forma los grupos minimizando la distancia a su centro.",
      "La silueta (−1 a 1) dice qué tan separados quedan; con ella elegimos k y comparamos métodos.",
    ],
    formula: "Z = SVD_k(X)\nmin Σ_c Σ_{x∈c} ‖x − μ_c‖²   (K-Means)\nsilueta(i) = (b − a) / máx(a, b)",
    params: "features.py · KMeans(n_clusters=8, n_init=10, random_state=42) · comparison.py",
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
    title: "Estimamos el rango salarial",
    lead: "Las vacantes publican rangos oficiales, no cifras exactas. Un modelo aprende a predecir el rango a partir del texto.",
    inside: [
      "El punto medio del rango solo ubica la vacante en su banda del SPE; nunca se muestra como salario.",
      "Una regresión logística multiclase (softmax) se entrena con las filas que sí traen rango y predice las que no.",
      "Se evalúa con validación cruzada contra la clase mayoritaria; aquí se entrena en tu navegador con 5 filas.",
    ],
    formula: "banda = searchsorted([1,5M, 2M, 3M, 4M, 6M], (mín + máx) / 2)\nP(banda = k | x) = softmax(Wx + b)_k",
    params: "supervised.py · LogisticRegression(C=2.0) · StratifiedKFold",
    metrics: (d) => {
      const c = d.salaries.models.classification;
      return c && !c.skipped && c.within_one_band != null ? [
        { label: "F1 macro del modelo", value: c.macro_f1, format: decimal },
        { label: "F1 macro clase mayoritaria", value: c.baseline_majority_macro_f1, format: decimal },
        { label: "acierta el rango o el vecino", value: c.within_one_band, format: percent },
      ] : [];
    },
  },
  {
    key: "graph",
    title: "Conectamos habilidades y ocupaciones",
    lead: "Dos habilidades pedidas en la misma vacante quedan unidas. De ese grafo salen familias de habilidades y caminos entre ocupaciones.",
    inside: [
      "Louvain agrupa habilidades moviendo cada nodo a la comunidad que más sube la modularidad Q.",
      "PageRank mide qué tan central es cada habilidad (el tamaño del nodo).",
      "Dijkstra encuentra la ruta más corta entre segmentos usando 1 − similitud de sus habilidades.",
    ],
    formula: "w(a,b) = #vacantes que piden a y b\nQ = 1/2m Σ [A_ij − k_i k_j / 2m] δ(c_i, c_j)\nruta = Dijkstra(segmentos, 1 − similitud)",
    params: "graph.py · MIN_COOCCURRENCE=2 (aquí 1) · louvain(seed=42) · pagerank",
    metrics: (d) => [
      { label: "habilidades en el grafo", value: Number(d.graph.metrics.skill_nodes ?? d.graph.nodes.length) },
      ...(d.graph.metrics.skill_modularity != null
        ? [{ label: "modularidad", value: Number(d.graph.metrics.skill_modularity), format: decimal }] : []),
    ],
  },
  {
    key: "cv",
    title: "Comparamos tu CV",
    lead: "Tu CV recorre el mismo camino: se limpia, se vectoriza con el mismo vocabulario y se detectan sus habilidades. Edítalo y mira cómo cambia el resultado.",
    inside: [
      "Mitad parecido de texto (coseno relativo a la vacante más parecida), mitad cobertura de las habilidades que pide cada vacante.",
      "Lo que la vacante pide y tu CV no menciona es tu brecha.",
      "En /cv el texto se procesa en memoria y se descarta con la respuesta.",
    ],
    formula: "match = ½ · cos(cv, v) / máx_v cos(cv, ·)\n      + ½ · |S_cv ∩ S_v| / |S_v|",
    params: "sextante_api/insights.py · match_cv",
  },
];
