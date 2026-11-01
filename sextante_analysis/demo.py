"""Synthetic demo corpus: run every stage and the API without HF access.

The rows are generated, clearly flagged as synthetic in the manifest
(``source.repo == "synthetic-demo"``), and never uploaded. They exist so the
pipeline, the API and the web app can be exercised end to end in a clean
clone and in CI.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.schema import COLUMNS

from .config import AnalysisConfig

ROLES: dict[str, dict] = {
    "Analista de datos": {
        "skills": ["Python", "SQL", "análisis de datos", "Power BI", "estadística",
                   "Excel avanzado", "visualización de datos", "machine learning"],
        "salary": (3_200_000, 7_500_000),
    },
    "Desarrollador de software": {
        "skills": ["JavaScript", "Python", "desarrollo web", "bases de datos", "Git",
                   "React", "APIs REST", "pruebas de software"],
        "salary": (4_000_000, 10_000_000),
    },
    "Auxiliar contable": {
        "skills": ["contabilidad", "Excel avanzado", "facturación", "conciliaciones bancarias",
                   "normas NIIF", "nómina", "impuestos"],
        "salary": (1_600_000, 3_200_000),
    },
    "Asesor comercial": {
        "skills": ["ventas", "atención al cliente", "negociación", "CRM",
                   "comunicación efectiva", "prospección de clientes"],
        "salary": (1_400_000, 3_500_000),
    },
    "Agente de servicio al cliente": {
        "skills": ["atención al cliente", "comunicación efectiva", "manejo de PQR",
                   "CRM", "trabajo en equipo", "resolución de problemas"],
        "salary": (1_300_000, 2_200_000),
    },
    "Técnico de mantenimiento": {
        "skills": ["mantenimiento preventivo", "electricidad industrial", "seguridad industrial",
                   "lectura de planos", "mecánica", "soldadura"],
        "salary": (1_700_000, 3_800_000),
    },
    "Enfermero profesional": {
        "skills": ["cuidado del paciente", "administración de medicamentos", "primeros auxilios",
                   "historia clínica", "trabajo en equipo", "bioseguridad"],
        "salary": (2_800_000, 5_200_000),
    },
    "Coordinador logístico": {
        "skills": ["gestión de inventarios", "logística", "Excel avanzado", "SAP",
                   "cadena de suministro", "negociación", "liderazgo"],
        "salary": (2_600_000, 6_000_000),
    },
}
GENERIC = ["trabajo en equipo", "resolución de problemas", "liderazgo",
           "comunicación efectiva", "Excel avanzado"]
CITIES = [("Bogotá", "Bogotá D.C."), ("Medellín", "Antioquia"), ("Cali", "Valle del Cauca"),
          ("Barranquilla", "Atlántico"), ("Cartagena", "Bolívar"), ("Bucaramanga", "Santander")]
SOURCES = ["spe", "spe", "spe", "linkedin", "indeed", "bayt"]
MODALITIES = ["Presencial", "Remoto", "Híbrido"]
CONTRACTS = ["Término indefinido", "Término fijo", "Prestación de servicios"]
EDUCATION = ["Técnico", "Tecnólogo", "Universitario", "Especialización"]
SENIORITY = ["junior", "", "senior"]


def synthetic_corpus(rows: int = 600, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    names = list(ROLES)
    records = []
    for index in range(rows):
        role = names[index % len(names)]
        spec = ROLES[role]
        seniority = SENIORITY[int(rng.integers(0, 3))]
        picked = list(rng.choice(spec["skills"], size=min(4, len(spec["skills"])), replace=False))
        picked.append(str(rng.choice(GENERIC)))
        if rng.random() < 0.25:  # cross-occupation skill, so routes exist
            other = ROLES[names[int(rng.integers(0, len(names)))]]["skills"]
            picked.append(str(rng.choice(other)))
        city, department = CITIES[int(rng.integers(0, len(CITIES)))]
        low, high = spec["salary"]
        factor = {"junior": 0.8, "": 1.0, "senior": 1.35}[seniority]
        base = rng.uniform(low, high) * factor
        has_salary = rng.random() < 0.7
        education = EDUCATION[min(3, int(rng.integers(0, 4)) + (1 if high > 5e6 else 0))]
        title = f"{role} {seniority}".strip()
        description = (
            f"Importante empresa en {city} requiere {title.lower()}. "
            f"Responsabilidades y requisitos: {', '.join(picked)}. "
            f"Experiencia en {picked[0]} y {picked[1]}. Formación {education.lower()}."
        )
        records.append({
            "vacancy_id": f"synthetic-{index:05d}",
            "source": SOURCES[index % len(SOURCES)],
            "url": f"https://example.org/vacantes/synthetic-{index:05d}",
            "title": title,
            "company": f"Empresa demo {int(rng.integers(1, 40))}",
            "city": city,
            "department": department,
            "published_at": f"2026-10-{1 + index % 28:02d}",
            "description": description,
            "salary_text": f"$ {base:,.0f}" if has_salary else None,
            "salary_min": round(base * 0.9, -3) if has_salary else None,
            "salary_max": round(base * 1.1, -3) if has_salary else None,
            "contract_type": CONTRACTS[int(rng.integers(0, 3))],
            "work_modality": MODALITIES[int(rng.integers(0, 3))],
            "education_level": education,
            "experience_text": f"{int(rng.integers(0, 6))} años de experiencia",
            "captured_at": f"2026-10-{1 + index % 28:02d} 12:00:00",
        })
    return pd.DataFrame(records, columns=COLUMNS)


def synthetic_esco(path: Path) -> Path:
    skills = sorted({skill for spec in ROLES.values() for skill in spec["skills"]} | set(GENERIC))
    lines = ["conceptUri,conceptType,preferredLabel,altLabels"]
    for skill in skills:
        slug = "-".join(skill.lower().split())
        lines.append(f"https://example.org/esco-demo/{slug},Skill/competence,{skill},")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_demo(output_root: str | Path = "data/analysis/runs", rows: int = 600) -> Path:
    from .run import build_run

    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    esco = synthetic_esco(output_root / "synthetic_esco.csv")
    frame = synthetic_corpus(rows)
    source = {"repo": "synthetic-demo", "revision": "synthetic", "files": [],
              "rows": len(frame), "sample_limit_per_dataset": None}
    config = AnalysisConfig(esco_csv=esco, output_root=output_root,
                            topic_count=8, cluster_count=8)
    return build_run(frame, source, config)
