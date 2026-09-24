# Artefactos del grafo

Este directorio es generado por:

```bash
python -m src.grafos.construir_grafo \
  --repo pxtron/vacantes-colombia \
  --esco-dir data/referencias/esco
```

Salidas: `nodos.csv`, `aristas.csv`, `vacante_habilidad.parquet` y
`manifiesto.json`. Se ignoran en Git porque dependen de la revisión cambiante del
dataset de Hugging Face; el manifiesto conserva la trazabilidad de cada corrida.
