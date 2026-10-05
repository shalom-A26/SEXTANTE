# AGENTS.md — Guía para agentes de IA que trabajan en SEXTANTE

Proyecto académico de analítica y minería de datos sobre el mercado laboral
colombiano (vacantes → habilidades, salarios, perfiles, grafos).

## Comandos útiles

```bash
# Entorno
.venv/bin/python --version        # Python ≥ 3.10 (venv creado con uv)
uv pip install -r requirements.txt            # pipeline de captura (pineado; lo que corre el cron)
uv pip install -r requirements-notebooks.txt  # + notebooks, src/analisis, src/grafos

# Extracción de vacantes
# Corpus curado (El Empleo + LinkedIn) → data/raw/vacantes.csv
.venv/bin/python -m src.extraccion.corpus --todo
# Corpus grande SPE (export oficial total) → data/raw/spe/vacantes_spe.parquet
.venv/bin/python -m src.extraccion.corpus --fuentes spe
.venv/bin/python -m src.extraccion.corpus --fuentes spe --spe-csv vacantes_spe_latest.csv   # reusa CSV descargado

# Emisión del dataset por semanas de captura (directorio Hugging Face)
.venv/bin/python -m src.extraccion.emitir_dataset
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.emitir_dataset --hf-upload --hf-repo pxtron/vacantes-colombia

# Restaurar el corpus acumulado desde Hugging Face (memoria persistente).
# Recompone los stores desde data/semana-*.parquet y deja data/raw/_publicado.json.
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.sync_hf --pull --repo pxtron/vacantes-colombia

# Captura manual local (desarrollo; la automática corre en GitHub Actions)
./scripts/capturar_6h.sh   # pull → SPE → curado → emisión; see script header

# Validación del corpus (EDA)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/eda_validacion.ipynb

# Analítica (dataset privado HF; autenticar con `hf auth login` o HF_TOKEN)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/dashboard_metricas.ipynb

# Grafo (vocabulario endógeno; sin datos de referencia externos)
.venv/bin/python -m src.grafos.construir_grafo --repo pxtron/vacantes-colombia
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/grafo_habilidades_ocupaciones.ipynb
```

Las pruebas de todo el pipeline (incluidas emisión y sincronización HF) corren con
`python -m unittest discover -s tests`. No hay linter configurado.

La **captura automática** corre en GitHub Actions: `.github/workflows/captura_6h.yml`
(cron `0 5,11,17,23 * * *` UTC = 00/06/12/18 hora de Colombia; también se puede
disparar manualmente con `workflow_dispatch`). El cron local está desactivado. El
planificador no respeta el minuto: medido sobre 20 corridas de septiembre–octubre
de 2026 los desvíos van de −3,4 h a +2,6 h, con una ventana ciega de ~8,8 h.

## Reglas del proyecto (críticas)

1. **Contrato de datos**: todo módulo que produzca vacantes debe emitir el
   **esquema canónico de 17 columnas** de `src/extraccion/esquema.py`, en el
   orden exacto. Usar `normalizar()` antes de guardar y `validar()` para verificar.
2. **Ética de datos (sin excepciones)**:
   - No romper `robots.txt`. Sin evasión de bloqueos, login/cookies personales ni proxies.
   - No recopilar datos personales de candidatos.
   - `User-Agent` identificable: `SEXTANTE-UTB-university-research/1.0 (...)`.
   - Throttling en peticiones (pausa mínima definida en `src/extraccion/base.py`).
- Al añadir una nueva fuente: primero viabilidad (robots/ToS/estructura) y
      registrarla en `docs/viabilidad_fuentes.md` (+ `docs/viabilidad_fuentes.en.md`).
3. **Fechas**: `fecha_captura` siempre se estampa con `%Y-%m-%d %H:%M:%S`;
   `fecha_publicacion` queda tal cual la da la fuente (formato variable).
   Como los stores son append-only, `fecha_captura` es la **primera** vez que
   vimos la vacante: no la sobrescribir nunca.
4. **Guardado (append-only, `keep="first"`)**: una vacante ya presente **no se
   reescribe**. Es la condición para que los archivos semanales sean inmutables.
   - Corpus curado (elempleo/linkedin): `src.extraccion.base.guardar_lotes()`
     (append + dedupe por `url`) en `data/raw/vacantes.csv`.
   - SPE: `src.extraccion.portales.spe.guardar_parquet()` → `data/raw/spe/vacantes_spe.parquet`
     con dedupe por `id_vacante` (`CODIGO_VACANTE`: varias vacantes distintas
     del SPE pueden compartir `url` del prestador). Devuelve cuántas filas son
     nuevas, no el total.
5. Duplicados entre fuentes: distinguir con `portal`; el dedupe por defecto es `url`
   (salvo SPE, que usa `CODIGO_VACANTE`).
6. **Memoria persistente = Hugging Face** (`pxtron/vacantes-colombia`, archivos
   `data/semana-*.parquet`): antes de capturar hay que recomponer los stores con
   `sync_hf.py --pull`; `emitir_dataset.py` los vuelve a publicar. El runner de
   GitHub Actions es efímero: sin este paso no hay acumulación.
   - El dataset se particiona por **semana de `fecha_captura`**, no de
     `fecha_publicacion`. Archivar por fecha de publicación obligaría a reabrir
     archivos ya publicados y a re-subirlos.
   - `_salida_estable()` fija tipos y orden de filas: contenido idéntico debe dar
     bytes idénticos, o `upload_folder` vuelve a subir el archivo y el ahorro se
     pierde. Si se toca esa función, hay tests que lo cubren.
   - Nunca borrar rutas del layout anterior (`store/`, `train-*`) sin que conste
     que el corpus fue restaurado; `_store_restaurado()` es esa red de seguridad.
7. **Fallos visibles**: `corpus.py` sale con código 1 si una fuente solicitada
   falla, y `emitir_dataset` escribe `estado.json` con los conteos de la corrida.
   No reintroducir ramas de resumen que solo comparen contra el total local.
8. **Secrets**: `HF_TOKEN` vive como secret del repositorio (GitHub). Nunca pegar
   tokens por el chat ni committearlos; al rotarlos, actualizar el secret.

## Dominio / glosario

- **Vacante/oferta**: publicación de empleo con descripción en texto libre.
- **Esquema canónico**: las 17 columnas documentadas en el README.
- **Portal/fuente**: sitio del que se extrae (p. ej. `elempleo`, `linkedin`, `spe`).
- **Corpus curado**: conjunto acumulado en `data/raw/vacantes.csv`.
- **Corpus grande**: `data/raw/spe/vacantes_spe.parquet` (export oficial SPE, 319.765 vacantes únicas acumuladas).
- **Semana de captura**: semana ISO (lunes a domingo) del `fecha_captura`; unidad de
  partición del dataset publicado (`semana-AAAA-Wnn.parquet`).
- Habilidades → **vocabulario endógeno**: n-gramas de las propias descripciones
  filtrados por señal ocupacional (sin taxonomía externa); queda pendiente el
  NLP contextual y la homologación ocupacional.

## Arquitectura actual

- `src/extraccion/esquema.py` — contrato de 17 columnas.
- `src/extraccion/base.py` — sesión HTTP ética (User-Agent, pausas, reintentos),
  estructura de `data/`, guardado append-only con dedupe.
- `src/extraccion/corpus.py` — orquestador CLI (`python -m src.extraccion.corpus`);
  flag `--snapshot` para cortes con marca de tiempo en `data/snapshots/`.
  Sale con código 1 si alguna fuente solicitada falla.
- `src/extraccion/sync_hf.py` — `--pull` recompone los dos stores desde los
  `data/semana-*.parquet` publicados (fallback al layout `store/` para datasets
  no migrados) y escribe `data/raw/_publicado.json` con los conteos previos.
- `src/extraccion/emitir_dataset.py` — consolida corpus grande + curado, agrupa por
  semana de captura y emite el directorio Hugging Face
  (`data/emitido/vacantes-colombia/`: parquet semanales + dataset card + `estado.json`).
  `--hf-upload` publica a un dataset privado (requiere `HF_TOKEN`), omitiendo lo que
  ya está en el repo, y migra el layout anterior solo si el corpus fue restaurado.
  **No reintroducir DuckDB**: era write-only y quedó retirado el 2026-10-04.
- `src/extraccion/portales/spe.py` — export oficial total del SPE (job asíncrono `/backbue/v1`)
  → esquema canónico → parquet. `verify=False` solo como reintento ante TLS intermitente del portal.
- `src/extraccion/portales/elempleo.py` — listado HTML + detalle JSON-LD `JobPosting`.
- `src/extraccion/portales/linkedin_jobspy.py` — JobSpy (`python-jobspy`) → esquema canónico.
- `.github/workflows/captura_6h.yml` — captura automática cada 6 h en GitHub Actions
  (pull de HF → SPE → curado → emisión/upload; `HF_TOKEN` desde secrets; summary con
  crecimiento real y aviso si no hubo vacantes nuevas).
- `scripts/capturar_6h.sh` — captura manual local (pull → SPE → curado → emisión, con `--snapshot`).
- `notebooks/eda_validacion.ipynb` — valida esquema y cobertura del corpus.
- `tests/` — 38 pruebas: emisión, sincronización, migración de layout, store del
  SPE y SSL, grafo, habilidades y métricas. La emisión y la sincronización no
  tenían suite; ahora sí.
- `src/analisis/` — acceso de solo lectura a los parquet HF y métricas laborales.
- `src/procesamiento/habilidades.py` — vocabulario endógeno (n-gramas + señal ocupacional).
- `src/grafos/` — tablas bipartitas, similitud, comunidades y transiciones exploratorias.
- `notebooks/dashboard_metricas.ipynb` / `grafo_habilidades_ocupaciones.ipynb` — narrativas analíticas.

## Estado y pendientes

- **Corpus grande** SPE: `data/raw/spe/vacantes_spe.parquet` (319.765 vacantes únicas
  acumuladas, ~285k filas por export, 2021–2026, cobertura ~100% en descripción/nivel
  educativo/departamento/contrato/salario/experiencia).
- Corpus curado 2.548 vacantes (El Empleo + LinkedIn). Fuentes: ver `docs/viabilidad_fuentes.md`.
- **Dataset publicado**: 322.313 vacantes en el dataset HF privado
  `pxtron/vacantes-colombia`, en archivos semanales (3 a 2026-10-04).
- Captura automática: **GitHub Actions** `.github/workflows/captura_6h.yml` cada 6 h
  (cron local desactivado; `scripts/capturar_6h.sh` queda para uso manual).
- Memoria persistente: los parquet semanales del dataset HF; no hay base local
  (DuckDB retirado el 2026-10-04).
- Layout del dataset: una fila por semana de `fecha_captura`; las semanas ya
  cerradas no se vuelven a subir porque su contenido está congelado. `estado.json`
  y `_publicado.json` son de la corrida y se regeneran en cada captura.
- Cifras: ~35k vacantes nuevas por semana; el repo pasó de 650 MB de contenido
  (44 % muerto) a 166 MB. `used_storage` (~19 GB, mayormente historial que HF no
  libera) dejó de crecer; no baja con el borrado de archivos.
- Pendientes: homologar ocupaciones (es el cuello de botella: 157.172 de 195.175
  títulos normalizados aparecen una sola vez) y avanzar hacia NLP contextual y
  modelos salariales.
- Documentar decisiones que afecten al modelo de dominio en el README o en
  `docs/` (viabilidad, nuevo esquema de columnas). Mantener `requirements.txt` al día.
- `requirements.txt` está **pineado** y solo lleva lo del pipeline de captura
  (`src/extraccion` y el workflow). Lo de análisis y grafos quedó en
  `requirements-notebooks.txt`, sin pinear, para que el cron no instale jupyter
  ni matplotlib cada 6 h. `pyahocorasick` sigue en el core porque
  `src/procesamiento/habilidades.py` tiene tests en la suite.
- `src/extraccion/portales/spe.py` tiene dos cuidados no obvios, ambos con test
  en `tests/test_spe_store.py`: `contar_filas()` (un `pd.read_parquet` para
  contar filas puede abortar el proceso con exit 134 al apagar el intérprete,
  Arrow #34314) y el flag `_VERIFICAR_SSL` (la cadena CA del SPE está
  incompleta, así que el primer `SSLError` desactiva la verificación por el resto
  de la corrida).

## Documentación (bilingüe)

- `README.md` / `README.en.md` — descripción, uso y estado (español / inglés).
- `docs/arquitectura.md` / `docs/architecture.en.md` — modelo C4 (contexto, contenedores,
  componentes, despliegue), flujos, secuencias y modelo de datos; **todos los diagramas en Mermaid**.
- `docs/viabilidad_fuentes.md` / `docs/viabilidad_fuentes.en.md` — estudio de fuentes (español / inglés).
- Regla: al cambiar arquitectura o diagramas, actualizar ambas versiones (mantener sincronía).
