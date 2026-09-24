"""Métricas, similitud y comunidades para el grafo cargo–habilidad."""

from __future__ import annotations

import numpy as np
import pandas as pd


def crear_grafo_bipartito(nodos: pd.DataFrame, aristas: pd.DataFrame):
    import networkx as nx

    grafo = nx.Graph()
    for row in nodos.itertuples(index=False):
        grafo.add_node(row.node_id, nombre=row.nombre, tipo=row.tipo, frecuencia=row.frecuencia, bipartite=0 if row.tipo == "ocupacion" else 1)
    for row in aristas.itertuples(index=False):
        if row.source in grafo and row.target in grafo:
            grafo.add_edge(row.source, row.target, peso=float(row.peso), proporcion=float(row.proporcion_ocupacion))
    return grafo


def resumen_red(grafo) -> dict:
    ocupaciones = {n for n, d in grafo.nodes(data=True) if d.get("tipo") == "ocupacion"}
    habilidades = set(grafo) - ocupaciones
    denominador = len(ocupaciones) * len(habilidades)
    return {
        "nodos": grafo.number_of_nodes(),
        "ocupaciones": len(ocupaciones),
        "habilidades": len(habilidades),
        "aristas": grafo.number_of_edges(),
        "densidad_bipartita": grafo.number_of_edges() / denominador if denominador else np.nan,
        "componentes": __import__("networkx").number_connected_components(grafo) if len(grafo) else 0,
    }


def ranking_grado(grafo, tipo: str, n: int = 20) -> pd.DataFrame:
    filas = []
    for nodo, datos in grafo.nodes(data=True):
        if datos.get("tipo") != tipo:
            continue
        filas.append({
            "node_id": nodo, "nombre": datos.get("nombre"),
            "grado": grafo.degree(nodo),
            "fuerza": sum(e.get("peso", 1) for *_, e in grafo.edges(nodo, data=True)),
        })
    return pd.DataFrame(filas).sort_values(["grado", "fuerza"], ascending=False).head(n) if filas else pd.DataFrame(columns=["node_id", "nombre", "grado", "fuerza"])


def centralidad_aproximada(grafo, muestras: int = 200, semilla: int = 42) -> pd.DataFrame:
    """Betweenness topológica aproximada con muestreo reproducible."""
    import networkx as nx

    if not len(grafo):
        return pd.DataFrame(columns=["node_id", "nombre", "tipo", "betweenness"])
    k = min(muestras, len(grafo))
    valores = nx.betweenness_centrality(grafo, k=k if k < len(grafo) else None, seed=semilla)
    filas = [{"node_id": n, "nombre": grafo.nodes[n].get("nombre"), "tipo": grafo.nodes[n].get("tipo"), "betweenness": v} for n, v in valores.items()]
    return pd.DataFrame(filas).sort_values("betweenness", ascending=False)


def matriz_ocupacion_habilidad(nodos: pd.DataFrame, aristas: pd.DataFrame):
    from scipy.sparse import csr_matrix, diags

    occ = nodos[nodos["tipo"].eq("ocupacion")].reset_index(drop=True)
    skills = nodos[nodos["tipo"].eq("habilidad")].reset_index(drop=True)
    oi = {v: i for i, v in enumerate(occ["node_id"])}
    si = {v: i for i, v in enumerate(skills["node_id"])}
    base = aristas[aristas["source"].isin(oi) & aristas["target"].isin(si)]
    rows = base["source"].map(oi).to_numpy()
    cols = base["target"].map(si).to_numpy()
    vals = base["proporcion_ocupacion"].astype(float).to_numpy()
    matriz = csr_matrix((vals, (rows, cols)), shape=(len(occ), len(skills)))
    df_skill = np.asarray((matriz > 0).sum(axis=0)).ravel()
    idf = np.log((1 + len(occ)) / (1 + df_skill)) + 1
    tfidf = matriz @ diags(idf)
    return tfidf, occ, skills


def similitudes_ocupaciones(
    nodos: pd.DataFrame,
    aristas: pd.DataFrame,
    vecinos: int = 10,
    similitud_minima: float = 0.05,
) -> pd.DataFrame:
    from sklearn.neighbors import NearestNeighbors

    matriz, occ, _ = matriz_ocupacion_habilidad(nodos, aristas)
    if len(occ) < 2:
        return pd.DataFrame(columns=["source", "target", "similitud_coseno"])
    n_vecinos = min(vecinos + 1, len(occ))
    modelo = NearestNeighbors(n_neighbors=n_vecinos, metric="cosine", algorithm="brute")
    modelo.fit(matriz)
    distancias, indices = modelo.kneighbors(matriz)
    filas = []
    for i, (dist_fila, idx_fila) in enumerate(zip(distancias, indices)):
        for distancia, j in zip(dist_fila, idx_fila):
            valor = 1 - float(distancia)
            if i == j or valor < similitud_minima:
                continue
            a, b = sorted((occ.iloc[i]["node_id"], occ.iloc[j]["node_id"]))
            filas.append({"source": a, "target": b, "similitud_coseno": valor})
    if not filas:
        return pd.DataFrame(columns=["source", "target", "similitud_coseno"])
    return pd.DataFrame(filas).groupby(["source", "target"], as_index=False)["similitud_coseno"].max().sort_values("similitud_coseno", ascending=False)


def comunidades_ocupaciones(similitudes: pd.DataFrame, semilla: int = 42) -> pd.DataFrame:
    import networkx as nx

    g = nx.from_pandas_edgelist(similitudes, "source", "target", "similitud_coseno", create_using=nx.Graph)
    if not len(g):
        return pd.DataFrame(columns=["node_id", "comunidad"])
    comunidades = nx.community.louvain_communities(g, weight="similitud_coseno", seed=semilla)
    return pd.DataFrame([{"node_id": nodo, "comunidad": i} for i, grupo in enumerate(comunidades) for nodo in grupo])


def habilidades_puente(aristas: pd.DataFrame, comunidades: pd.DataFrame, nodos: pd.DataFrame) -> pd.DataFrame:
    base = aristas.merge(comunidades.rename(columns={"node_id": "source"}), on="source", how="inner")
    if base.empty:
        return pd.DataFrame(columns=["node_id", "nombre", "comunidades", "entropia"])
    pesos = base.groupby(["target", "comunidad"])["peso"].sum().rename("peso").reset_index()
    total = pesos.groupby("target")["peso"].transform("sum")
    pesos["p"] = pesos["peso"] / total
    salida = pesos.groupby("target").agg(comunidades=("comunidad", "nunique"), entropia=("p", lambda p: float(-(p * np.log(p)).sum()))).reset_index().rename(columns={"target": "node_id"})
    nombres = nodos[["node_id", "nombre"]]
    return salida.merge(nombres, on="node_id", how="left").sort_values(["comunidades", "entropia"], ascending=False)


def detalle_transicion(ocupacion_origen: str, ocupacion_destino: str, aristas: pd.DataFrame, nodos: pd.DataFrame, n: int = 10) -> dict:
    nombres = nodos.set_index("node_id")["nombre"].to_dict()
    origen = aristas[aristas["source"].eq(ocupacion_origen)].set_index("target")["proporcion_ocupacion"]
    destino = aristas[aristas["source"].eq(ocupacion_destino)].set_index("target")["proporcion_ocupacion"]
    compartidas = origen.index.intersection(destino.index)
    adicionales = destino.index.difference(origen.index)
    return {
        "origen": nombres.get(ocupacion_origen, ocupacion_origen),
        "destino": nombres.get(ocupacion_destino, ocupacion_destino),
        "habilidades_compartidas": [nombres[x] for x in destino.loc[compartidas].sort_values(ascending=False).head(n).index],
        "habilidades_adicionales_observadas": [nombres[x] for x in destino.loc[adicionales].sort_values(ascending=False).head(n).index],
        "aviso": "Señal exploratoria de proximidad entre perfiles publicados; no implica que una persona pueda realizar la transición.",
    }


def habilidades_caracteristicas(ocupacion_id: str, nodos: pd.DataFrame, aristas: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    matriz, ocupaciones, skills = matriz_ocupacion_habilidad(nodos, aristas)
    indices = ocupaciones.index[ocupaciones["node_id"].eq(ocupacion_id)].tolist()
    if not indices:
        return pd.DataFrame(columns=["habilidad", "puntaje_tfidf"])
    fila = matriz.getrow(indices[0])
    orden = np.argsort(fila.data)[::-1][:n]
    return pd.DataFrame({
        "habilidad": [skills.iloc[fila.indices[i]]["nombre"] for i in orden],
        "puntaje_tfidf": [float(fila.data[i]) for i in orden],
    })
