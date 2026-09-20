# Viabilidad de fuentes de datos

Fecha de la sonda: 2026-09-20.
Herramientas: `python-jobspy` 1.1.13, `requests` 2.x. Volúmenes bajos de prueba.

## Resumen

| Fuente | ¿Viable? | Detalle | Prioridad piloto |
| --- | --- | --- | --- |
| **LinkedIn** (vía JobSpy) | ✔ Sí | Listado + descripción completa. 10/10 en prueba. | 1 |
| **El Empleo** (`elempleo.com.co`) | ✔ Sí | Listado HTML público + detalle en JSON-LD `JobPosting`. 20 ofertas únicas por página SEO. | 2 |
| **Computrabajo** | ✘ No | `robots.txt` y página responden 403. Bloqueo agresivo (Cloudflare). No viable sin evasión. | — |
| **Indeed** (vía JobSpy) | ✘ No | `IndeedException: bad response with status code: 403`. | — |
| **Glassdoor** (vía JobSpy) | ✘ No | `KeyError: 'GLASSDOOR'`. | — |
| **SPE – datos abiertos** | ⚠ Pendiente | Portal oficial existe y publica datos abiertos, pero no se localizó en el catálogo Socrata un dataset de vacantes con descripción libre. Explorar en Fase 2. | 3 |

## Detalle por fuente

### 1. LinkedIn vía JobSpy (`pip install python-jobspy`)

JobSpy agrega vacantes de varios portales en un solo `DataFrame` normalizado.

- Instalado: `python-jobspy` 1.1.13 (Python ≥ 3.10).
- Prueba: `scrape_jobs(site_name=["linkedin"], search_term="analista", location="Colombia", results_wanted=10)` → **10 filas, 9 con descripción completa**.
- Columnas que entrega el `DataFrame`: `job_url`, `site`, `title`, `company`, `location`, `job_type`, `date_posted`, `interval`, `min_amount`, `max_amount`, `currency`, `is_remote`, `num_urgent_words`, `benefits`, `emails`, `description`.
- Notas:
  - La API de la versión instalada **no** acepta `hours_old`, `linkedin_fetch_description` ni `description_format` (firmado de esta versión).
  - LinkedIn busca de forma global: con `location="Colombia"` aparecen ofertas remotas globales ejecutables desde Colombia.
  - Indeed → 403. Glassdoor → KeyError. Se descartan en el motor JobSpy.

### 2. El Empleo (`elempleo.com/co/`)

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

### 3. Computrabajo — descartado

- `co.computrabajo.com/robots.txt` → `403 Forbidden`.
- Home y listados también bloqueados. El proveedor bloquea clientes que no son navegadores.
- Para un proyecto con ética de datos como eje transversal, descartado (no se usarán técnicas de evasión).

### 4. SPE – datos abiertos — pendiente de exploración

- Portal oficial: `serviciodeempleo.gov.co/transparencia-e-informacion/informes-de-interes/publicacion-de-datos-abiertos` y dashboard agregado `dataempleo.serviciodeempleo.gov.co` (no contiene vacantes individuales con descripción).
- Búsqueda en el catálogo Socrata de `datos.gov.co` (“ofertas de empleo”, “vacantes”) no devolvió un dataset de vacantes con descripción libre. Los datasets OPE encontrados son de la Alcaldía de Medellín (atenciones/vinculados), sin texto de oferta.
- **Acción Fase 2**: identificar el dataset oficial de vacantes del SPE (o su API) o descartar formalmente.

## Criterios éticos adoptados (eje transversal del curso)

1. **Respetar `robots.txt`** y términos de uso de cada portal.
2. **No** usar login/cookies personales, proxies ni técnicas de evasión de bloqueos.
3. **Volumen controlado** con throttling (pausa entre peticiones) para no afectar los portales.
4. **`User-Agent` identificable** con el proyecto: `SEXTANTE-UTB-university-research/1.0 (...)`.
5. Usar la fuente **oficial (SPE)** como piso de legitimidad del dataset cuando esté disponible.
6. **No recopilar datos personales** de candidatos; solo información pública de las ofertas.
7. Documentar la procedencia de cada registro en el campo `portal` + `url`.

## Decisión de piloto

Construir el motor de extracción con **JobSpy → LinkedIn** (rápido, DataFrame normalizado, descripciones completas) y **El Empleo** (HTML + JSON-LD, robots abierto, sin login), con el esquema canónico de 17 columnas definido en `src/extraccion/esquema.py`.