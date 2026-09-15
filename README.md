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

- **`vacantes.csv`**: muestra inicial de 300 vacantes laborales colombianas con 17 variables (título, empresa, ubicación, descripción, salario, contrato, modalidad, etc.). Se ampliará durante el curso.
- Fuentes complementarias (desarrollo futuro): Servicio Público de Empleo, GEIH (DANE), CIUO-08 A.C., SNIES, OLE, DIVIPOLA, ESCO y O*NET.

## Estructura del proyecto

```
SEXTANTE/
├── README.md
├── data/               # Datos crudos y procesados
├── notebooks/          # Jupyter notebooks (EDA, modelado, tópicos)
├── src/                # Código fuente del proyecto
│   ├── extraccion/     # Recolección de vacantes (web scraping)
│   ├── procesamiento/  # Limpieza, normalización, NLP, embeddings
│   ├── analisis/       # EDA, clustering, tópicos, modelos
│   └── grafos/         # Grafo habilidades-ocupaciones
├── docs/               # Documentación del proyecto
└── requirements.txt    # Dependencias de Python
```

## Alcance

El sistema presenta tendencias, brechas y señales estadísticas; **no** tiene como propósito calificar personas, empresas ni instituciones educativas.