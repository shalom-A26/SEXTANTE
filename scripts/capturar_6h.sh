#!/usr/bin/env bash
# Captura periódica de vacantes (diseñada para ejecutarse cada 6 horas).
# - SPE: export oficial total → store canónico parquet (incremental por CODIGO_VACANTE).
# - Corpus curado (El Empleo + LinkedIn): append + dedupe por url.
# - Copia snapshot con marca de tiempo a data/snapshots/.
# - Emite el dataset unificado a DuckDB + directorio Hugging Face (si está configurado).
set -euo pipefail

cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=data/snapshots/captura.log
mkdir -p data/snapshots

echo "[$(date '+%Y-%m-%d %H:%M:%S')] captura SPE..." >> "$LOG"
"$PY" -m src.extraccion.corpus --fuentes spe --snapshot >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] captura corpus curado..." >> "$LOG"
"$PY" -m src.extraccion.corpus --fuentes linkedin elempleo --snapshot >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] emisión dataset (DuckDB + HF)..." >> "$LOG"
"$PY" -m src.extraccion.emitir_dataset >> "$LOG" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] captura completada." >> "$LOG"

# Instalación del cron (cada 6 horas), como usuario actual:
#   crontab -e  →  añadir:  0 */6 * * * cd "$HOME/Documents/SEXTANTE" && ./scripts/capturar_6h.sh