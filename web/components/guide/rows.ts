// Example postings written for the guide (fictional, labelled as such in the UI).
// They are built so every pipeline phenomenon shows up: a mojibake SPE row,
// the same vacancy on SPE and LinkedIn, a re-captured URL the append-only store
// drops, template phrases, salaries in different SPE bands and one without salary.

export type Row = {
  vacancy_id: string;
  source: "spe" | "linkedin" | "indeed";
  url: string;
  title: string;
  company: string;
  city: string;
  salary_text: string;
  salary_min: number | null;
  salary_max: number | null;
  work_modality: string;
  captured_at: string;
  description: string;
};

// Field names as each source exports them, before the canonical schema.
export const RAW_FIELDS: Record<Row["source"], Record<string, keyof Row>> = {
  spe: { CODIGO_VACANTE: "vacancy_id", TITULO_VACANTE: "title", NOMBRE_PRESTADOR: "company", MUNICIPIO: "city", RANGO_SALARIAL: "salary_text", DESCRIPCION_VACANTE: "description" },
  linkedin: { id: "vacancy_id", job_url: "url", title: "title", company: "company", location: "city", description: "description" },
  indeed: { id: "vacancy_id", job_url: "url", title: "title", company: "company", location: "city", min_amount: "salary_min", description: "description" },
};

export const ROWS: Row[] = [
  {
    vacancy_id: "1849302", source: "spe", url: "https://www.serviciodeempleo.gov.co/vacante/1849302",
    title: "TÃ©cnico en LogÃ­stica", company: "Distribuciones del Caribe S.A.S.", city: "Barranquilla",
    salary_text: "$1.600.000 - $1.900.000", salary_min: 1_600_000, salary_max: 1_900_000, work_modality: "Presencial",
    captured_at: "2026-11-03 04:23:10",
    description: "Empresa lÃ­der del sector busca tÃ©cnico en logÃ­stica para gestiÃ³n de inventarios, control de despachos y manejo de montacargas. Requiere Excel bÃ¡sico y trabajo en equipo. Horario de lunes a sÃ¡bado. Â¡PostÃºlate ya!",
  },
  {
    vacancy_id: "li-40912", source: "linkedin", url: "https://co.linkedin.com/jobs/view/40912",
    title: "Analista de datos junior", company: "Fintech Andina", city: "Bogotá",
    salary_text: "$3.200.000 - $3.800.000", salary_min: 3_200_000, salary_max: 3_800_000, work_modality: "Híbrido",
    captured_at: "2026-11-03 04:47:02",
    description: "Buscamos analista de datos junior para construir tableros en Power BI, escribir consultas SQL y automatizar reportes con Python. Valoramos la comunicación efectiva y el pensamiento analítico. ¡Postúlate ya!",
  },
  {
    vacancy_id: "1851177", source: "spe", url: "https://www.serviciodeempleo.gov.co/vacante/1851177",
    title: "Analista de datos", company: "Fintech Andina S.A.S.", city: "Bogotá",
    salary_text: "A convenir", salary_min: null, salary_max: null, work_modality: "Híbrido",
    captured_at: "2026-11-03 16:23:44",
    description: "Se busca analista de datos junior para construir tableros en Power BI, escribir consultas SQL y automatizar reportes con Python. Valoramos la comunicación efectiva y el pensamiento analítico.",
  },
  {
    vacancy_id: "in-77310", source: "indeed", url: "https://co.indeed.com/viewjob?jk=77310",
    title: "Auxiliar contable", company: "Contadores Asociados del Valle", city: "Cali",
    salary_text: "$1.400.000 - $1.600.000", salary_min: 1_400_000, salary_max: 1_600_000, work_modality: "Presencial",
    captured_at: "2026-11-03 05:17:30",
    description: "Empresa líder del sector requiere auxiliar contable con manejo de facturación electrónica, conciliaciones bancarias y nómina. Conocimiento en Excel avanzado. Contrato a término fijo con todas las prestaciones de ley.",
  },
  {
    vacancy_id: "li-41388", source: "linkedin", url: "https://co.linkedin.com/jobs/view/41388",
    title: "Desarrollador backend", company: "Software Caribe", city: "Cartagena",
    salary_text: "$6.000.000 - $8.000.000", salary_min: 6_000_000, salary_max: 8_000_000, work_modality: "Remoto",
    captured_at: "2026-11-03 05:47:12",
    description: "Desarrollador backend con experiencia en Python y Django, diseño de APIs REST y bases de datos PostgreSQL. Inglés intermedio y trabajo en equipo.",
  },
  {
    vacancy_id: "in-77544", source: "indeed", url: "https://co.indeed.com/viewjob?jk=77544",
    title: "Asesor comercial", company: "Seguros Horizonte", city: "Medellín",
    salary_text: "$1.800.000 - $2.400.000", salary_min: 1_800_000, salary_max: 2_400_000, work_modality: "Presencial",
    captured_at: "2026-11-03 06:17:55",
    description: "Asesor comercial para venta de seguros, atención al cliente y seguimiento de metas. Se requiere comunicación efectiva y orientación a resultados. ¡Postúlate ya!",
  },
];

// Re-captured half an hour later: same URL as ROWS[4], so the store keeps the first one.
export const RECAPTURE: Row = { ...ROWS[4], vacancy_id: "li-41388", captured_at: "2026-11-03 06:17:21",
  description: ROWS[4].description + " Beneficios: medicina prepagada." };

export const SAMPLE_CV =
  "Profesional en ingeniería industrial con dos años como analista. Construí tableros en Power BI y consultas SQL para el área comercial, " +
  "automaticé reportes en Excel avanzado y empecé a programar en Python. Me destaco por la comunicación efectiva y el trabajo en equipo.";
