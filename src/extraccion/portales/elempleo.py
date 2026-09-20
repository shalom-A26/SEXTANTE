"""Colector de vacantes de El Empleo (elempleo.com/co/) a DataFrame canónico.

Fuente pública con robots.txt permisivo. El detalle de cada oferta se extrae
del bloque JSON-LD (schema.org JobPosting) que la propia página publica.

Estructura:
- listado: HTML con tarjetas (enlace `/co/ofertas-trabajo/<slug>-<id>`,
  atributo data-ga4-offerdata con id, título, empresa, ciudad y salario texto).
- detalle: JSON-LD con descripción, salario min/max (COP), tipo de contrato,
  modalidad y fecha de publicación.
"""

from __future__ import annotations

import html as html_mod
import json
import re
from datetime import date, datetime

import pandas as pd

from src.extraccion.base import get
from src.extraccion.esquema import normalizar

BASE = "https://www.elempleo.com"

# Páginas de listado SEO: genérica + ciudades + cargos. CADA una devuelve 20
# ofertas únicas. Se pueden ampliar libremente.
PAGINAS_LISTADO = [
    "/co/ofertas-empleo/",
    "/co/ofertas-empleo/bogota",
    "/co/ofertas-empleo/medellin",
    "/co/ofertas-empleo/cali",
    "/co/ofertas-empleo/barranquilla",
    "/co/ofertas-empleo/cartagena",
    "/co/ofertas-empleo/bucaramanga",
    "/co/ofertas-empleo/pereira",
    "/co/ofertas-empleo/trabajo-analista",
    "/co/ofertas-empleo/trabajo-ingeniero",
    "/co/ofertas-empleo/trabajo-desarrollador",
]

# employmentType schema.org -> texto canónico.
TIPO_CONTRATO = {
    "FULL_TIME": "Tiempo completo",
    "PART_TIME": "Medio tiempo",
    "CONTRACTOR": "Contrato",
    "TEMPORARY": "Temporal",
    "INTERN": "Prácticas",
    "VOLUNTEER": "Voluntariado",
    "PER_DIEM": "Por día",
    "OTHER": "Otro",
}

# jobLocationType -> modalidad canónica.
MODALIDAD = {
    "TELECOMMUTE": "Remoto",
    "HYBRID": "Híbrido",
    "ON_SITE": "Presencial",
}


def _fecha_captura() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def extraer_enlaces_listado(html_texto: str) -> list[str]:
    """Devuelve URLs únicas de ofertas del listado (slug-id al final)."""
    enlaces = re.findall(r'"(/co/ofertas-trabajo/[^"]+)"', html_texto)
    unicos = []
    vistos = set()
    for e in enlaces:
        m = re.search(r"/([\w-]+)-(\d+)$", e)
        if m and m.group(2) not in vistos:
            vistos.add(m.group(2))
            unicos.append(e)
    return unicos


def parsear_tarjeta(html_texto: str) -> dict[str, dict]:
    """id -> {url, titulo, empresa, ciudad, salario_texto} desde data-ga4-offerdata."""
    tarjetas: dict[str, dict] = {}
    for m in re.finditer(
        r'data-url="(/co/ofertas-trabajo/[^"]+)"[^>]*data-ga4-offerdata="([^"]+)"',
        html_texto,
    ):
        url, raw = m.group(1), m.group(2)
        try:
            info = json.loads(html_mod.unescape(raw))
        except json.JSONDecodeError:
            continue
        mid = str(info.get("id") or re.search(r"-(\d+)$", url).group(1))
        tarjetas[mid] = {
            "url": url,
            "titulo": info.get("title"),
            "empresa": info.get("company"),
            "ciudad": info.get("location"),
            "salario_texto": info.get("salary"),
        }
    return tarjetas


def extraer_jsonld(html_texto: str) -> dict | None:
    """Devuelve el bloque JSON-LD JobPosting de una página de detalle."""
    for bloque in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_texto, re.S):
        try:
            data = json.loads(bloque)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def _map_detalle_esquema(mid: str, tarjeta: dict, ld: dict) -> dict:
    titulo = ld.get("title") or tarjeta.get("titulo")
    descripcion = ld.get("description") or None
    if descripcion:
        descripcion = html_mod.unescape(re.sub(r"\s+", " ", descripcion)).strip()

    sal = ld.get("baseSalary", {}) or {}
    valor = sal.get("value", {}) or {}
    sal_min = valor.get("minValue")
    sal_max = valor.get("maxValue")
    moneda = sal.get("currency")
    intervalo = valor.get("unitText")
    sal_texto = tarjeta.get("salario_texto")
    if not sal_texto and (sal_min or sal_max):
        partes = [p for p in (sal_min, sal_max) if p]
        sal_texto = f"{moneda} {' - '.join(f'{p:,.0f}' for p in partes)} ({intervalo})"

    return {
        "id_vacante": mid,
        "portal": "elempleo",
        "url": BASE + tarjeta["url"],
        "titulo": titulo,
        "empresa": (ld.get("hiringOrganization") or {}).get("name") or tarjeta.get("empresa"),
        "ciudad": tarjeta.get("ciudad"),
        "departamento": None,
        "fecha_publicacion": ld.get("datePosted"),
        "descripcion": descripcion,
        "salario_texto": sal_texto,
        "salario_min": sal_min,
        "salario_max": sal_max,
        "tipo_contrato": TIPO_CONTRATO.get(ld.get("employmentType")),
        "modalidad": MODALIDAD.get(ld.get("jobLocationType")),
        "nivel_educativo": None,
        "experiencia_texto": None,
        "fecha_captura": _fecha_captura(),
    }


def scrape_el_empleo(urls: list[str] | None = None, max_detalles: int = 120) -> pd.DataFrame:
    """Listado + detalle JSON-LD para las páginas de El Empleo dadas.

    - urls: páginas de listado. Por defecto PAGINAS_LISTADO.
    - max_detalles: techo de detalles a visitar por corrida (throttling ético).
    """
    paginas = urls or PAGINAS_LISTADO
    resultados: list[dict] = []
    vistos: set[str] = set()

    for lista in paginas:
        resp = get(BASE + lista)
        enlaces = extraer_enlaces_listado(resp.text)
        tarjetas = parsear_tarjeta(resp.text)
        for enlace in enlaces:
            if len(resultados) >= max_detalles:
                break
            mid = re.search(r"-(\d+)$", enlace).group(1)
            if mid in vistos:
                continue
            vistos.add(mid)
            try:
                detalle = get(BASE + enlace)
                ld = extraer_jsonld(detalle.text)
                if not ld:
                    continue
                tarjeta = tarjetas.get(mid, {})
                resultados.append(_map_detalle_esquema(mid, tarjeta, ld))
            except Exception as ese:  # noqa: BLE001 - una oferta no debe tumbar la corrida
                print(f"  [elempleo] detalle {enlace} falló: {ese}")
        if len(resultados) >= max_detalles:
            break

    df = pd.DataFrame(resultados) if resultados else pd.DataFrame()
    return normalizar(df) if len(df) else normalizar(pd.DataFrame())