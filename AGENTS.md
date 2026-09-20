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
HF_TOKEN=hf_xxx .venv/bin/python -m src.extraccion.emitir_dataset --hf-upload --hf-repo USUARIO/vacantes-colombia

# Captura periódica cada 6 h
./scripts/capturar_6h.sh   # cron: 0 */6 * * * (ver comentario dentro del script)

# Validación del corpus (EDA)
.venv/bin/jupyter nbconvert --to notebook --execute --inplace notebooks/eda_validacion.ipynb
```

No hay suite de tests ni linter configurada aún.

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

## Dominio / glosario

- **Vacante/oferta**: publicación de empleo con descripción en texto libre.
- **Esquema canónico**: las 17 columnas documentadas en el README.
- **Portal/fuente**: sitio del que se extrae (p. ej. `elempleo`, `linkedin`, `spe`).
- **Corpus curado**: conjunto acumulado en `data/raw/vacantes.csv`.
- **Corpus grande**: `data/raw/spe/vacantes_spe.parquet` (export oficial SPE, ~246.5k vacantes únicas acumuladas).
- Habilidades → taxonomía ESCO (referencia futura, no aplicada aún).

## Arquitectura actual

- `src/extraccion/esquema.py` — contrato de 17 columnas.
- `src/extraccion/base.py` — sesión HTTP ética (User-Agent, pausas, reintentos),
  estructura de `data/`, guardado incremental con dedupe.
- `src/extraccion/corpus.py` — orquestador CLI (`python -m src.extraccion.corpus`);
  flag `--snapshot` para cortes con marca de tiempo en `data/snapshots/`.
- `src/extraccion/emitir_dataset.py` — consolida corpus grande + curado y emite
  a DuckDB local (`data/duckdb/sextante.duckdb`, tabla `vacantes`) y a un
  directorio de dataset Hugging Face (`data/emitido/vacantes-colombia/`).
  `--hf-upload` publica un dataset privado (requiere `HF_TOKEN`).
- `src/extraccion/portales/spe.py` — export oficial total del SPE (job asíncrono `/backbue/v1`)
  → esquema canónico → parquet. `verify=False` solo como reintento ante TLS intermitente del portal.
- `src/extraccion/portales/elempleo.py` — listado HTML + detalle JSON-LD `JobPosting`.
- `src/extraccion/portales/linkedin_jobspy.py` — JobSpy (`python-jobspy`) → esquema canónico.
- `scripts/capturar_6h.sh` — captura SPE + curado + emisión, con `--snapshot`.
- `notebooks/eda_validacion.ipynb` — valida esquema y cobertura del corpus.

## Estado y pendientes

- ✅ **Corpus grande** SPE: `data/raw/spe/vacantes_spe.parquet` (~246.5k vacantes únicas
  acumuladas, ~285k filas por export, 2021–2026, cobertura ~100% en descripción/nivel
  educativo/departamento/contrato/salario/experiencia).
- ✅ Corpus curado ~231 vacantes (El Empleo + LinkedIn). Fuentes: ver `docs/viabilidad_fuentes.md`.
- ✅ Captura periódica: `scripts/capturar_6h.sh` (cron `0 */6 * * *` activado y validado).
- ✅ Emisión: DuckDB local (`data/duckdb/sextante.duckdb`) y dataset HF en `data/emitido/`.
- ✅ Dataset HF privado publicado: `pxtron/vacantes-colombia` (ver HF_TOKEN rotado para re-subidas).
- Pendientes: los módulos `procesamiento/`, `analisis/`, `grafos/`.
- Documentar decisiones que afecten al modelo de dominio en el README o en
  `docs/` (viabilidad, nuevo esquema de columnas). Mantener `requirements.txt` al día.

## Documentación (bilingüe)

- `README.md` / `README.en.md` — descripción, uso y estado (español ✔ / inglés).
- `docs/arquitectura.md` / `docs/architecture.en.md` — modelo C4 (contexto, contenedores,
  componentes, despliegue), flujos, secuencias y modelo de datos; **todos los diagramas en Mermaid**.
- `docs/viabilidad_fuentes.md` / `docs/viabilidad_fuentes.en.md` — estudio de fuentes (español ✔ / inglés).
- Regla: al cambiar arquitectura o diagramas, actualizar ambas versiones (mantener sincronía).