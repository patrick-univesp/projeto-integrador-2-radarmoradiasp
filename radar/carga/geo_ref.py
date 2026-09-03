"""Resolve ``lat``/``lon``/``distrito`` de uma transação por *lookup* na
referência versionada ``radar/dados_geo/`` (gerada offline por
``scripts/prefetch_geo.py``).

**Sem `shapely`, sem rede.** O *point-in-polygon* já aconteceu no *prefetch*: cada
lote da referência já vem com o distrito resolvido. Detalhe: ``docs/referencia-geo.md``.

``carregar_indices()`` monta ~1,4 M de entradas em dicionários; medido em **~450 MB
de pico** (com *interning* das chaves e dedupe dos 96 distritos). A carga (#03)
precisa conferir que o total, com o streaming do ``.xlsx`` por cima, fica abaixo dos
600 MB do container.
"""

import gzip
import json
import sys
from collections import Counter
from pathlib import Path

from radar.carga.coercao import para_numero_porta
from radar.carga.normalizacao import normalizar

DADOS_GEO = Path(__file__).resolve().parent.parent / "dados_geo"

# (lon, lat, geo_nivel, distrito, subprefeitura, regiao)
SEM_GEO = (None, None, "--", "", "", "")


def _partes_sql(sql: str):
    return sql[:3], sql[3:6], sql[6:10]


def _indexar(lotes, setor, indices, triplas):
    por_lote, por_endereco, por_rua, por_quadra = indices
    for quadra, lote, _cond, logr, num, lon, lat, distrito, subpref, regiao in lotes:
        t = (distrito, subpref, regiao)
        geo = (lon, lat, triplas.setdefault(t, t))
        por_lote[(setor, quadra, lote)] = geo
        por_quadra.setdefault((setor, quadra), []).append(geo)
        if logr:
            por_endereco.setdefault((setor, quadra, logr, num), []).append(geo)
            if num.isdigit():
                por_rua.setdefault((setor, quadra, logr), []).append((int(num), geo))


def indices_de_setor(setor, base_dir=None):
    """Os quatro índices de **um** setor (``<setor>.json.gz``). É o que a carga
    usa — ~poucos MB por setor, em vez dos ~450 MB da cidade toda."""
    base = Path(base_dir) if base_dir else DADOS_GEO
    arq = base / f"{setor}.json.gz"
    indices = ({}, {}, {}, {})
    if arq.exists():
        with gzip.open(arq, "rt", encoding="utf-8") as fh:
            _indexar(json.load(fh)["lotes"], setor, indices, {})
    return indices


def carregar_indices(base_dir=None):
    """Lê ``radar/dados_geo/*.json.gz`` e monta os quatro índices da cidade
    inteira. ~450 MB — a carga usa ``indices_de_setor``; isto é para testes e
    uso pontual."""
    base = Path(base_dir) if base_dir else DADOS_GEO
    indices = ({}, {}, {}, {})
    triplas: dict = {}
    for arq in sorted(base.glob("*.json.gz")):
        setor = sys.intern(arq.name.split(".")[0])
        with gzip.open(arq, "rt", encoding="utf-8") as fh:
            _indexar(json.load(fh)["lotes"], setor, indices, triplas)
    return indices


def _do_lote(geo, nivel):
    d, s, r = geo[2]
    return (geo[0], geo[1], nivel, d, s, r)


def _consolidar(geos, nivel):
    """Média de lon/lat; distrito por maioria dos lotes que contribuíram (na
    escala de T2–T4 a diferença entre lotes vizinhos é menor que uma quadra)."""
    n = len(geos)
    lon = round(sum(g[0] for g in geos) / n, 7)
    lat = round(sum(g[1] for g in geos) / n, 7)
    d, s, r = Counter(g[2] for g in geos).most_common(1)[0][0]
    return (lon, lat, nivel, d, s, r)


def resolver(sql, logradouro, numero, indices):
    """``(lon, lat, geo_nivel, distrito, subprefeitura, regiao)``.

    Escada: T1 lote exato · T2 endereço na quadra · T3 rua na quadra (número mais
    próximo) · T4 centroide da quadra · ``--`` sem correspondência. ``distrito``
    vem preenchido sempre que ``geo_nivel != '--'``.
    """
    por_lote, por_endereco, por_rua, por_quadra = indices
    if not sql or len(sql) != 11:
        return SEM_GEO
    setor, quadra, lote = _partes_sql(sql)
    logr = normalizar(logradouro)
    num = para_numero_porta(numero)

    geo = por_lote.get((setor, quadra, lote))
    if geo:
        return _do_lote(geo, "T1")

    if logr and num:
        gs = por_endereco.get((setor, quadra, logr, num))
        if gs:
            return _consolidar(gs, "T2")

    if logr:
        cands = por_rua.get((setor, quadra, logr))
        if cands:
            if num.isdigit():
                alvo = int(num)
                _, geo = min(cands, key=lambda c: abs(c[0] - alvo))
                return _do_lote(geo, "T3")
            return _consolidar([g for _, g in cands], "T3")

    gs = por_quadra.get((setor, quadra))
    if gs:
        return _consolidar(gs, "T4")

    return SEM_GEO
