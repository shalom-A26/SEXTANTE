#!/usr/bin/env bash
# Captura manual de vacantes (uso local/desarrollo; la captura automática corre
# en GitHub Actions: .github/workflows/captura_6h.yml, cada 6 h → Hugging Face).
# - Restaura el corpus acumulado desde Hugging Face (sin este paso no hay
#   acumulación: la memoria persistente vive en HF, no en el disco local).
# - SPE: export oficial total → store canónico parquet (append-only por CODIGO_VACANTE).
# - Corpus curado (El Empleo + LinkedIn): append + dedupe por url.
# - Copia snapshot con marca de tiempo a data/snapshots/.
# - Emite el dataset por semanas al directorio Hugging Face.
set -euo pipefail

cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=data/snapshots/captura.log
mkdir -p data/snapshots

echo "[$(date '+%Y-%m-%d %H:%M:%S')] restaurando corpus desde HF..." >> "$LOG"
"$PY" -m src.extraccion.sync_hf --pull --repo pxtron/vacantes-colombia >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] captura SPE..." >> "$LOG"
"$PY" -m src.extraccion.corpus --fuentes spe --snapshot >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] captura corpus curado..." >> "$LOG"
"$PY" -m src.extraccion.corpus --fuentes linkedin elempleo --snapshot >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] emisión dataset semanal..." >> "$LOG"
"$PY" -m src.extraccion.emitir_dataset >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] captura completada." >> "$LOG"

# El cron local está desactivado (la captura automática la hace GitHub Actions).
# Para re-ejecutar el cron local (solo por desarrollo):
#   crontab -e  →  añadir:  0 */6 * * * cd "$HOME/Documents/SEXTANTE" && ./scripts/capturar_6h.sh