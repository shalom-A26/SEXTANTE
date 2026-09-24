# AGENTS.md — Guía para agentes de IA que trabajan en SEXTANTE

Proyecto académico de analítica y minería de datos sobre el mercado laboral
colombiano (vacantes → habilidades, salarios, perfiles, grafos).

## Comandos útiles

```bash
# Entorno
.venv/bin/python --version        # Python ≥ 3.10 (venv creado con uv)
uv pip install -r requirements.txt

# Extracción de vacantes
# Corpus curado (El Empleo + LinkedIn) → data/raw/vacantes.csv
.venv/bin/python -m src.extraccion.corpus --todo
# Corpus grande SPE (export oficial total) → data/raw/spe/vacantes_spe.parquet
.venv/bin/python -m src.extraccion.corpus --fuentes spe
.venv/bin/python -m src.extraccion.corpus --fuentes spe --spe-csv vacantes_spe_latest.csv   # reusa CSV descargado

# Emisión del dataset unificado (DuckDB local + directorio Hugging Face)
.venv/bin/python -m src.extraccion.emitir_dataset
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.emitir_dataset --hf-upload --hf-repo pxtron/vacantes-colombia

# Restaurar el corpus acumulado desde Hugging Face (memoria persistente)
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.sync_hf --pull --repo pxtron/vacantes-colombia
# Sembrar HF con los stores locales (primera corrida / tras recrear el dataset)
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.sync_hf --push --repo pxtron/vacantes-colombia

# Captura manual local (desarrollo; la automática corre en GitHub Actions)
./scripts/capturar_6h.sh   # uses local stores + snapshots; see script header

# Validación del corpus (EDA)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/eda_validacion.ipynb

# Analítica (dataset privado HF; autenticar con `hf auth login` o HF_TOKEN)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/dashboard_metricas.ipynb

# Grafo (requiere paquete CSV oficial ESCO español en data/referencias/esco/)
.venv/bin/python -m src.grafos.construir_grafo --repo pxtron/vacantes-colombia --esco-dir data/referencias/esco
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/grafo_habilidades_ocupaciones.ipynb
```

La **captura automática** corre en GitHub Actions: `.github/workflows/captura_6h.yml`
(cron `0 5,11,17,23 * * *` UTC = 00/06/12/18 hora de Colombia; también se puede
disparar manualmente con `workflow_dispatch`). El cron local está desactivado.

La capa analítica incluye pruebas con `python -m unittest discover -s tests`;
el pipeline de extracción aún no tiene una suite propia ni linter configurado.

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
4. **Guardado**:
   - Corpus curado (elempleo/linkedin): `src.extraccion.base.guardar_lotes()`
     (append + dedupe por `url`) en `data/raw/vacantes.csv`.
   - SPE: `src.extraccion.portales.spe.guardar_parquet()` → `data/raw/spe/vacantes_spe.parquet`
     con dedupe por `id_vacante` (`CODIGO_VACANTE`: varias vacantes distintas
     del SPE pueden compartir `url` del prestador).
5. Duplicados entre fuentes: distinguir con `portal`; el dedupe por defecto es `url`
   (salvo SPE, que usa `CODIGO_VACANTE`).
6. **Memoria persistente = Hugging Face** (`pxtron/vacantes-colombia`, carpeta `store/`):
   antes de capturar hay que restablecer el corpus acumulado con
   `sync_hf.py --pull`; `emitir_dataset.py` reescribe `store/` junto con el dataset
   unificado. El runner de GitHub Actions es efímero: sin este paso no hay acumulación.
7. **Secrets**: `HF_TOKEN` vive como secret del repositorio (GitHub). Nunca pegar
   tokens por el chat ni committearlos; al rotarlos, actualizar el secret.

## Dominio / glosario

- **Vacante/oferta**: publicación de empleo con descripción en texto libre.
- **Esquema canónico**: las 17 columnas documentadas en el README.
- **Portal/fuente**: sitio del que se extrae (p. ej. `elempleo`, `linkedin`, `spe`).
- **Corpus curado**: conjunto acumulado en `data/raw/vacantes.csv`.
- **Corpus grande**: `data/raw/spe/vacantes_spe.parquet` (export oficial SPE, ~246.5k vacantes únicas acumuladas).
- Habilidades → taxonomía ESCO (extracción inicial por menciones explícitas;
  pendiente evaluación y NLP contextual).

## Arquitectura actual

- `src/extraccion/esquema.py` — contrato de 17 columnas.
- `src/extraccion/base.py` — sesión HTTP ética (User-Agent, pausas, reintentos),
  estructura de `data/`, guardado incremental con dedupe.
- `src/extraccion/corpus.py` — orquestador CLI (`python -m src.extraccion.corpus`);
  flag `--snapshot` para cortes con marca de tiempo en `data/snapshots/`.
- `src/extraccion/sync_hf.py` — sincroniza con HF: `--pull` restaura el corpus
  acumulado (`store/`) hacia `data/raw/` antes de capturar; `--push` siembra/actualiza
  los stores locales en HF (primera corrida o tras recrear el dataset).
- `src/extraccion/emitir_dataset.py` — consolida corpus grande + curado y emite
  a DuckDB local (`data/duckdb/sextante.duckdb`, tabla `vacantes`) y a un
  directorio de dataset Hugging Face (`data/emitido/vacantes-colombia/`).
  `--hf-upload` sube a un dataset privado (requiere `HF_TOKEN`) e incluye la
  carpeta `store/` (stores canónicos) para que HF sea la memoria persistente.
- `src/extraccion/portales/spe.py` — export oficial total del SPE (job asíncrono `/backbue/v1`)
  → esquema canónico → parquet. `verify=False` solo como reintento ante TLS intermitente del portal.
- `src/extraccion/portales/elempleo.py` — listado HTML + detalle JSON-LD `JobPosting`.
- `src/extraccion/portales/linkedin_jobspy.py` — JobSpy (`python-jobspy`) → esquema canónico.
- `.github/workflows/captura_6h.yml` — captura automática cada 6 h en GitHub Actions
  (pull de HF → SPE → curado → emisión/upload; `HF_TOKEN` desde secrets; summary en la corrida).
- `scripts/capturar_6h.sh` — captura manual local (SPE + curado + emisión, con `--snapshot`).
- `notebooks/eda_validacion.ipynb` — valida esquema y cobertura del corpus.
- `src/analisis/` — acceso de solo lectura a shards HF y métricas laborales.
- `src/procesamiento/habilidades.py` — menciones explícitas contra ESCO español.
- `src/grafos/` — tablas bipartitas, similitud, comunidades y transiciones exploratorias.
- `notebooks/dashboard_metricas.ipynb` / `grafo_habilidades_ocupaciones.ipynb` — narrativas analíticas.

## Estado y pendientes

- **Corpus grande** SPE: `data/raw/spe/vacantes_spe.parquet` (~246.5k vacantes únicas
  acumuladas, ~285k filas por export, 2021–2026, cobertura ~100% en descripción/nivel
  educativo/departamento/contrato/salario/experiencia).
- Corpus curado ~231 vacantes (El Empleo + LinkedIn). Fuentes: ver `docs/viabilidad_fuentes.md`.
- Captura automática: **GitHub Actions** `.github/workflows/captura_6h.yml` cada 6 h
  (cron local desactivado; `scripts/capturar_6h.sh` queda para uso manual).
- Emisión: DuckDB local (`data/duckdb/sextante.duckdb`) y dataset HF en `data/emitido/`.
- Memoria persistente: dataset HF privado `pxtron/vacantes-colombia` (shards + carpeta `store/`).
- Pendientes: evaluar la extracción ESCO, homologar ocupaciones y avanzar hacia
  NLP contextual/modelos salariales.
- Documentar decisiones que afecten al modelo de dominio en el README o en
  `docs/` (viabilidad, nuevo esquema de columnas). Mantener `requirements.txt` al día.

## Documentación (bilingüe)

- `README.md` / `README.en.md` — descripción, uso y estado (español / inglés).
- `docs/arquitectura.md` / `docs/architecture.en.md` — modelo C4 (contexto, contenedores,
  componentes, despliegue), flujos, secuencias y modelo de datos; **todos los diagramas en Mermaid**.
- `docs/viabilidad_fuentes.md` / `docs/viabilidad_fuentes.en.md` — estudio de fuentes (español / inglés).
- Regla: al cambiar arquitectura o diagramas, actualizar ambas versiones (mantener sincronía).
