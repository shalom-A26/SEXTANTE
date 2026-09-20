# SEXTANTE

Plataforma de analítica y minería de datos para navegar el mercado laboral colombiano a través de habilidades, perfiles, salarios y tendencias de demanda.

## Descripción

Los requisitos reales de un cargo no siempre pueden conocerse a partir del título de la vacante. Un título como "Analista junior" puede representar trabajos con funciones y requisitos muy diferentes, y la información relevante suele estar en la descripción de la oferta, escrita como texto libre, sin una taxonomía uniforme y con vocabulario inconsistente. Esto dificulta medir qué habilidades solicita realmente el mercado, cuánto se paga por ellas y cómo se relacionan los perfiles ocupacionales.

SEXTANTE desarrolla un flujo de procesamiento que recopila vacantes laborales publicadas en Colombia y transforma sus descripciones en datos estructurados para:

- Identificar habilidades demandadas (referencia a la taxonomía abierta ESCO).
- Analizar patrones salariales.
- Agrupar perfiles ocupacionales semejantes.
- Detectar patrones o anomalías en la demanda laboral.
- Construir un grafo de habilidades y ocupaciones para estudiar relaciones, comunidades y rutas de transición laboral.

## Integrantes

| Nombre | Código |
| --- | --- |
| Alejandro Patrón Montero | T00078181 |
| Shalom Jhoana Arrieta Marrugo | T00082962 |
| Karla Andrea Barraza Torres | T00082880 |
| Katlyn Gutiérrez Cardona | T00082259 |

*Universidad Tecnológica de Bolívar — Análítica y Minería de Datos (Proyecto final)*

## Objetivo

Desarrollar una solución de analítica y minería de datos que permita comprender las necesidades del mercado laboral colombiano mediante el procesamiento de vacantes, especialmente de sus descripciones textuales, para identificar las habilidades más demandadas, caracterizar perfiles ocupacionales y analizar patrones salariales y de demanda útiles para candidatos, empleadores y programas académicos.

## Estado actual

- ✅ **Pipeline de extracción funcional** (`src/extraccion/`): recolecta vacantes desde **SPE** (export oficial), **El Empleo** y **LinkedIn** (vía JobSpy) y las normaliza al **esquema canónico de 17 columnas**.
- ✅ **Corpus grande SPE**: `data/raw/spe/vacantes_spe.parquet` (~196.8k vacantes únicas, 2021–2026, descripción + nivel educativo + departamento + rango salarial + contrato + experiencia; ~107 MB, dedupe por `CODIGO_VACANTE`).
- ✅ **Corpus curado**: `data/raw/vacantes.csv` (~224 vacantes de El Empleo + LinkedIn, sin duplicados).
- ✅ **Captura periódica**: `scripts/capturar_12h.sh` + modo `--snapshot` (cortes con marca de tiempo en `data/snapshots/`).
- ✅ **Almacenamiento**: DuckDB local (`data/duckdb/sextante.duckdb`, tabla `vacantes`) y dataset Hugging Face listo para publicar (`data/emitido/vacantes-colombia/`, shards parquet + dataset card).
- ✅ **Sonda de viabilidad** de fuentes: `docs/viabilidad_fuentes.md`.
- ✅ **EDA de validación**: `notebooks/eda_validacion.ipynb` (verifica el esquema y la cobertura de campos).
- ⏳ Siguiente: crear el dataset privado en Hugging Face (subir con `HF_TOKEN`), y EDA/NLP (habilidades ESCO) sobre el corpus grande.

## Metodología

- Análisis exploratorio de datos y preparación de variables.
- Reducción de dimensionalidad con técnicas como PCA, t-SNE o UMAP.
- Métodos supervisados para tareas de estimación o clasificación (p. ej., salario esperado).
- Métodos no supervisados de agrupamiento: K-Means, agrupamiento jerárquico y DBSCAN.
- Minería de texto y procesamiento de lenguaje natural: limpieza, normalización, TF-IDF, modelado de tópicos y representaciones vectoriales (Word2Vec, transformadores en español).
- Extracción de información desde fuentes web.
- Analítica de redes y grafos mediante comunidades, centralidad y algoritmos de rutas o conexión.
- Procesamiento distribuido con Apache Spark cuando el volumen de datos lo justifique.
- Ética de datos, privacidad, transparencia y uso responsable de los resultados como ejes transversales.

## Fuentes de datos

| Fuente | Estado | Detalle |
| --- | --- | --- |
| **SPE – export oficial** (`buscadordeempleo.gov.co`) | ✔ Activa | Export CSV total de vacantes vía API `/backbue/v1` (job asíncrono). ~285k filas → ~196.8k únicas. Cobertura 100% en descripción, departamento, nivel educativo, contrato, salario, experiencia. |
| **El Empleo** (`elempleo.com/co/`) | ✔ Activa | HTML público (robots.txt permisivo) + detalle JSON-LD `JobPosting`. |
| **LinkedIn** (vía JobSpy) | ✔ Activa | `python-jobspy`; descripciones completas sin autenticación. |
| Computrabajo / Indeed / Glassdoor | ✘ No viable | Bloqueos 403; se descartan sin evasión (ética). |

La viabilidad completa y los motivos están en [`docs/viabilidad_fuentes.md`](docs/viabilidad_fuentes.md).

## Esquema canónico de vacantes (17 columnas)

Definido en `src/extraccion/esquema.py`; es el **único contrato de salida** de los colectores:

`id_vacante, portal, url, titulo, empresa, ciudad, departamento, fecha_publicacion, descripcion, salario_texto, salario_min, salario_max, tipo_contrato, modalidad, nivel_educativo, experiencia_texto, fecha_captura`

La fuente SPE llena de forma nativa los campos que antes estaban al 0% (`departamento`, `nivel_educativo`, `experiencia_texto`) y numéricos de salario (~78%).

## Estructura del proyecto

```
SEXTANTE/
├── README.md
├── AGENTS.md                # Guía para agentes de IA que trabajen en el repo
├── requirements.txt
├── scripts/
│   └── capturar_12h.sh      # captura periódica (SPE + curado + emisión; cron 0 */12 * * *)
├── data/
│   ├── raw/                 # vacantes.csv (corpus curado acumulado)
│   │   └── spe/             # vacantes_spe.parquet (corpus grande canónico) [+ csv export]
│   ├── procesados/          # datasets limpios/enriquecidos (uso futuro)
│   ├── snapshots/           # cortes con marca de tiempo de cada captura
│   ├── emitido/             # dataset listo para Hugging Face (parquet + card)
│   └── duckdb/              # sextante.duckdb (tabla vacantes, local)
├── notebooks/
│   └── eda_validacion.ipynb
├── src/
│   ├── extraccion/          # Pipeline de recolección y emisión
│   │   ├── esquema.py       #   contrato de 17 columnas
│   │   ├── base.py          #   HTTP ético, guardado + dedupe + snapshots
│   │   ├── corpus.py        #   orquestador (python -m ...)
│   │   ├── emitir_dataset.py#   DuckDB local + dataset Hugging Face
│   │   └── portales/
│   │       ├── spe.py               #   SPE (export oficial CSV → parquet canónico)
│   │       ├── elempleo.py          #   El Empleo (HTML + JSON-LD)
│   │       └── linkedin_jobspy.py   #   LinkedIn vía JobSpy
│   ├── procesamiento/       # Limpieza, normalización, NLP, embeddings (uso futuro)
│   ├── analisis/            # EDA, clustering, tópicos, modelos (uso futuro)
│   └── grafos/              # Grafo habilidades-ocupaciones (uso futuro)
└── docs/
    ├── integrantes.txt
    └── viabilidad_fuentes.md
```

## Uso

```bash
# 1. Entorno (Python ≥ 3.10; venv creado con uv en este ambiente)
uv venv                      # o: python -m venv .venv
uv pip install -r requirements.txt

# 2a. Corpus grande SPE (export oficial total; ~3 peticiones al portal)
.venv/bin/python -m src.extraccion.corpus --fuentes spe            # descarga export → parquet
.venv/bin/python -m src.extraccion.corpus --fuentes spe --spe-csv vacantes_spe_latest.csv  # reusa CSV
.venv/bin/python -m src.extraccion.corpus --fuentes spe --snapshot  # + snapshot con marca de tiempo

# 2b. Corpus curado y añadirlo a data/raw/vacantes.csv
.venv/bin/python -m src.extraccion.corpus                 # LinkedIn + El Empleo
.venv/bin/python -m src.extraccion.corpus --fuentes elempleo
.venv/bin/python -m src.extraccion.corpus --fuentes linkedin --linkedin-por-busqueda 25

# 2c. Emitir el dataset unificado (DuckDB local + directorio HF)
.venv/bin/python -m src.extraccion.emitir_dataset
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.emitir_dataset --hf-upload --hf-repo TU_USUARIO/vacantes-colombia  # dataset privado en HF

# 2d. Captura periódica cada 12 h (ver scripts/capturar_12h.sh para el cron)
./scripts/capturar_12h.sh

# 3. Validar el corpus (ejecutar el notebook)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/eda_validacion.ipynb
```

Cada corrida **añade** filas nuevas y estampa `fecha_captura`: `vacantes.csv` deduplica por `url`; el parquet del SPE deduplica por `id_vacante` (`CODIGO_VACANTE`).

## Ética de datos (eje transversal)

Ver criterios adoptados en `docs/viabilidad_fuentes.md`:

1. Respetar `robots.txt` y términos de uso de cada portal.
2. Sin login/cookies personales, proxies ni evasión de bloqueos.
3. Volumen controlado con throttling (pausa entre peticiones) y `User-Agent` identificable (`SEXTANTE-UTB-university-research/1.0`).
4. Fuente oficial (SPE) como piso de legitimidad cuando esté disponible.
5. Solo información pública de ofertas; sin datos personales de candidatos.
6. Procedencia registrada por registro en `portal` + `url`.

## Alcance

El sistema presenta tendencias, brechas y señales estadísticas; **no** tiene como propósito calificar personas, empresas ni instituciones educativas.