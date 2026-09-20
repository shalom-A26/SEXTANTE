# AGENTS.md — Guía para agentes de IA que trabajan en SEXTANTE

Proyecto académico de analítica y minería de datos sobre el mercado laboral
colombiano (vacantes → habilidades, salarios, perfiles, grafos).

## Comandos útiles

```bash
# Entorno
.venv/bin/python --version        # Python ≥ 3.10 (venv creado con uv)
uv pip install -r requirements.txt

# Extracción de vacantes (añade a data/raw/vacantes.csv)
.venv/bin/python -m src.extraccion.corpus --todo

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
     registrarla en `docs/viabilidad_fuentes.md`.
3. **Fechas**: `fecha_captura` siempre se estampa con `%Y-%m-%d %H:%M:%S`;
   `fecha_publicacion` queda tal cual la da la fuente (formato variable).
4. **Guardado**: usar `src.extraccion.base.guardar_lotes()` (append + dedupe por `url`).
5. Duplicados entre fuentes: distinguir con `portal`; el dedupe por defecto es `url`.

## Dominio / glosario

- **Vacante/oferta**: publicación de empleo con descripción en texto libre.
- **Esquema canónico**: las 17 columnas documentadas en el README.
- **Portal/fuente**: sitio del que se extrae (p. ej. `elempleo`, `linkedin`).
- **Corpus**: conjunto acumulado en `data/raw/vacantes.csv`.
- Habilidades → taxonomía ESCO (referencia futura, no aplicada aún).

## Arquitectura actual

- `src/extraccion/esquema.py` — contrato de 17 columnas.
- `src/extraccion/base.py` — sesión HTTP ética (User-Agent, pausas, reintentos),
  estructura de `data/`, guardado incremental con dedupe.
- `src/extraccion/corpus.py` — orquestador CLI (`python -m src.extraccion.corpus`).
- `src/extraccion/portales/elempleo.py` — listado HTML + detalle JSON-LD `JobPosting`.
- `src/extraccion/portales/linkedin_jobspy.py` — JobSpy (`python-jobspy`) → esquema canónico.
- `notebooks/eda_validacion.ipynb` — valida esquema y cobertura del corpus.

## Estado y pendientes

- ✅ Corpus inicial ~218 vacantes (El Empleo + LinkedIn). Fuentes: ver `docs/viabilidad_fuentes.md`.
- Pendientes: campos `departamento`, `nivel_educativo`, `experiencia_texto`
  (etapa NLP), salario numérico en LinkedIn, fuente SPE (datos abiertos),
  y los módulos `procesamiento/`, `analisis/`, `grafos/`.
- Documentar decisiones que afecten al modelo de dominio en el README o en
  `docs/` (viabilidad, nuevo esquema de columnas). Mantener `requirements.txt` al día.