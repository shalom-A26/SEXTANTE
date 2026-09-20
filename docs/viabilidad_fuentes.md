# Viabilidad de fuentes de datos

Fecha de la sonda: 2026-09-20.
Herramientas: `python-jobspy` 1.1.13, `requests` 2.x. Volúmenes bajos de prueba.

## Resumen

| Fuente | ¿Viable? | Detalle | Prioridad piloto |
| --- | --- | --- | --- |
| **SPE – export oficial** (`buscadordeempleo.gov.co`) | ✔ Sí | Export CSV total de vacantes vía API `/backbue/v1` (job asíncrono oficial). ~285k filas → ~196.8k vacantes únicas; cobertura 100% de campos clave. | 1 |
| **LinkedIn** (vía JobSpy) | ✔ Sí | Listado + descripción completa. 10/10 en prueba. | 2 |
| **El Empleo** (`elempleo.com.co`) | ✔ Sí | Listado HTML público + detalle en JSON-LD `JobPosting`. 20 ofertas únicas por página SEO. | 3 |
| **Computrabajo** | ✘ No | `robots.txt` y página responden 403. Bloqueo agresivo (Cloudflare). No viable sin evasión. | — |
| **Indeed** (vía JobSpy) | ✘ No | `IndeedException: bad response with status code: 403`. | — |
| **Glassdoor** (vía JobSpy) | ✘ No | `KeyError: 'GLASSDOOR'`. | — |

## Detalle por fuente

### 1. SPE – export oficial (`buscadordeempleo.gov.co`) — fuente maestra

El buscador de vacantes del SPE es una SPA en `https://www.buscadordeempleo.gov.co/` que consume una API REST en `https://www.buscadordeempleo.gov.co/backbue/v1`.

Hallazgos de la sonda (2026-09-20):

- La página **no** es scraping: el portal ofrece su propio export masivo. Desde la interfaz web se descarga con el botón *"CSV (Se exportan todas las vacantes)"*; el flujo usa un job asíncrono:
  1. `POST /vacantes/export/csv/async` → `{jobId}` (202 queued).
  2. `GET  /vacantes/export/csv/async/{jobId}/status` → `processing` → `completed`.
  3. `GET  /vacantes/export/csv/async/{jobId}/download` → CSV (~415 MB, UTF-8 con BOM).
- Resultado (2026-09-20): **284.958 filas** en el CSV → **196.783 vacantes únicas** por `CODIGO_VACANTE` (el export contiene ~88k filas duplicadas del mismo código; se deduplican).
- **Cobertura 100%** en las 20.000 vacantes muestreadas (y `100%` global): `TITULO_VACANTE`, `DESCRIPCION_VACANTE`, `NIVEL_ESTUDIOS`, `RANGO_SALARIAL`, `DEPARTAMENTO`, `MUNICIPIO`, `TIPO_CONTRATO`, `NOMBRE_PRESTADOR`, `FECHA_PUBLICACION`, `MESES_EXPERIENCIA_CARGO`, `TELETRABAJO`, `SECTOR_ECONOMICO`, `URL_DETALLE_VACANTE`.
- Histórico: publicaciones desde **2021-06-25** hasta la fecha de captura (actualización continua; `max_date` vía `GET /vacantes/date`).
- Licencia: datos de vacantes del servicio público de empleo, publicado por el Estado; no contiene datos personales de candidatos. Considerado uso legítimo y ético (fuente oficial = piso de legitimidad).
- Salario numérico: `RANGO_SALARIAL` es un **bucket** (p. ej. `$1.500.001 - $2.000.000`, `A Convenir`, `Mayor de $15.000.001`). El módulo SPE lo convierte a `salario_min`/`salario_max` (~78% con valor numérico).
- `URL_DETALLE_VACANTE` apunta a la oferta original (computrabajo ~192k, elempleo ~36k, SPE ~30k, magneto ~21k, etc.) — el SPE agrega vacantes de múltiples portales.
- Nota ética: se descarga con el mecanismo oficial de exportación (3 peticiones HTTP por captura completa), sin evasión.

Implementación: `src/extraccion/portales/spe.py`, orquestado con `python -m src.extraccion.corpus --fuentes spe`. Almacenamiento: `data/raw/spe/vacantes_spe.parquet` (dedupe por `id_vacante`, no por `url`).

### 2. LinkedIn vía JobSpy (`pip install python-jobspy`)

JobSpy agrega vacantes de varios portales en un solo `DataFrame` normalizado.

- Instalado: `python-jobspy` 1.1.13 (Python ≥ 3.10).
- Prueba: `scrape_jobs(site_name=["linkedin"], search_term="analista", location="Colombia", results_wanted=10)` → **10 filas, 9 con descripción completa**.
- Columnas que entrega el `DataFrame`: `job_url`, `site`, `title`, `company`, `location`, `job_type`, `date_posted`, `interval`, `min_amount`, `max_amount`, `currency`, `is_remote`, `num_urgent_words`, `benefits`, `emails`, `description`.
- Notas:
  - La API de la versión instalada **no** acepta `hours_old`, `linkedin_fetch_description` ni `description_format` (firmado de esta versión).
  - LinkedIn busca de forma global: con `location="Colombia"` aparecen ofertas remotas globales ejecutables desde Colombia.
  - Indeed → 403. Glassdoor → KeyError. Se descartan en el motor JobSpy.

### 3. El Empleo (`elempleo.com/co/`)

- `robots.txt` accesible y permisivo (solo bloquea rutas de administración y privadas → `Disallow: */Admin/`, `*/Management/`, etc.).
- Listado público: `https://www.elempleo.com/co/ofertas-empleo/` y variantes SEO por ciudad o cargo:
  - `.../co/ofertas-empleo/bogota`, `.../medellin`, `.../trabajo-analista`, etc.
  - Cada página contiene **20 ofertas únicas** (identificador numérico al final de `/co/ofertas-trabajo/<slug>-<id>`).
- Tarjetas de listado: atributo `data-url` (enlace de la oferta) y `data-ga4-offerdata` (JSON con `id`, `title`, `company`, `location`, `salary` como texto).
- Detalle de cada oferta: bloque `JSON-LD application/ld+json` de tipo `JobPosting` con:
  - `title`, `description`, `datePosted`, `validThrough`
  - `employmentType` (`CONTRACTOR`, `FULL_TIME`, ...)
  - `hiringOrganization.name`
  - `baseSalary`: `currency=COP`, `minValue`, `maxValue`, `unitText=MONTH`
  - `jobLocationType` (`TELECOMMUTE`, ...)
  - `jobLocation.address` (generalmente solo país `CO`; la ciudad viene en la tarjeta del listado).
- Web API (`/co/api/joboffers/findbyfilter`) devuelve `401 Authorization has been denied` → **no se usa** (evitar evasión/auth frágil).

### 4. Computrabajo — descartado

- Los datos `robots.txt` y página responden 403.
- Home y listados también bloqueados. El proveedor bloquea clientes que no son navegadores.
- Para un proyecto con ética de datos como eje transversal, descartado (no se usarán técnicas de evasión).

### 5. SPE – datos abiertos en datos.gov.co — descartado como vía

- `serviciodeempleo.gov.co/transparencia-e-informacion/.../publicacion-de-datos-abiertos` enlaza al catálogo Socrata de `datos.gov.co` para la entidad "Servicio Publico de Empleo".
- El catálogo Socrata de datos.gov.co **no** contiene un dataset de vacantes con descripción libre (solo registros de atenciones/vinculados de OPE de Medellín y agregados de desempleo).
- Conclusión: la vía correcta para el SPE es el **export oficial de `buscadordeempleo.gov.co`** (ver sección 1), no datos.gov.co.

## Criterios éticos adoptados (eje transversal del curso)

1. **Respetar `robots.txt`** y términos de uso de cada portal.
2. **No** usar login/cookies personales, proxies ni técnicas de evasión de bloqueos.
3. **Volumen controlado** con throttling (pausa entre peticiones) para no afectar los portales.
4. **`User-Agent` identificable** con el proyecto: `SEXTANTE-UTB-university-research/1.0 (...)`.
5. Usar la fuente **oficial (SPE)** como piso de legitimidad del dataset cuando esté disponible.
6. **No recopilar datos personales** de candidatos; solo información pública de las ofertas.
7. Documentar la procedencia de cada registro en el campo `portal` + `url`.

## Decisión de piloto

Construir el motor de extracción con **SPE (export oficial)** como fuente maestra de volumen (corpus grande en parquet), más **JobSpy → LinkedIn** (rápido, DataFrame normalizado, descripciones completas) y **El Empleo** (HTML + JSON-LD, robots abierto, sin login), todos normalizados al esquema canónico de 17 columnas definido en `src/extraccion/esquema.py`.