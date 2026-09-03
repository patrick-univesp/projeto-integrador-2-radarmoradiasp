#!/usr/bin/env python3
"""Gera a referência geo versionada ``radar/dados_geo/`` — roda OFFLINE, na
máquina de quem mantém os dados. Precisa de ``shapely`` (``requirements-geo.txt``).

Cada lote sai com o distrito já resolvido por *point-in-polygon*, para o runtime
(``radar/carga/geo_ref.py``) só fazer *lookup*, sem `shapely` e sem rede.

    # bootstrap a partir do cache do projeto de referência (sem rede):
    python scripts/prefetch_geo.py --cache tmp/ITBI/cache

    # crawl do GeoSampa para os setores/quadras de uma planilha:
    python scripts/prefetch_geo.py --planilha "GUIAS ... .xlsx"

    # cidade inteira (todos os setores e quadras):
    python scripts/prefetch_geo.py --cidade-inteira

    # preencher lacunas depois que a carga acusou geo_nivel='--':
    python scripts/prefetch_geo.py --refresh 052:012,052:013

Formato de saída: ``radar/dados_geo/<setor>.json.gz`` =
``{"lotes": [[quadra, lote, cond, logr_norm, num_norm, lon, lat, distrito, subpref, regiao], ...]}``
mais ``radar/dados_geo/_meta.json``.
"""

import argparse
import datetime as dt
import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shapely.geometry import Point, shape  # noqa: E402
from shapely.strtree import STRtree  # noqa: E402

from radar.carga.coercao import para_numero_porta  # noqa: E402
from radar.carga.normalizacao import normalizar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "radar" / "dados_geo"
WFS = "http://wfs.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wfs"
CAMPOS_LOTE = (
    "cd_setor_fiscal,cd_quadra_fiscal,cd_lote,cd_condominio,"
    "nm_logradouro_completo,cd_numero_porta,ge_poligono"
)
QUADRAS_POR_REQ = 60
TENTATIVAS = 4


class Bloqueado(Exception):
    """Resposta HTML do WAF da PRODAM — repetir a mesma URL não adianta."""


def _wfs(params: dict, timeout=300) -> dict:
    url = WFS + "?" + urllib.parse.urlencode(params)
    ultimo = None
    for tent in range(TENTATIVAS):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310
                bruto = r.read()
            if bruto[:1] == b"<":
                raise Bloqueado(f"resposta não-JSON ({len(url)} chars na URL)")
            return json.loads(bruto)
        except Bloqueado:
            raise
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            ultimo = e
            time.sleep(2**tent)
    raise RuntimeError(f"WFS falhou após {TENTATIVAS} tentativas: {ultimo}")


def _feicoes_lote(setor: str, quadras: list[str]) -> list:
    lista = "','".join(quadras)
    dados = _wfs({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": "geoportal:lote_cidadao", "outputFormat": "application/json",
        "srsName": "EPSG:4326", "propertyName": CAMPOS_LOTE,
        "CQL_FILTER": f"cd_setor_fiscal='{setor}' AND cd_quadra_fiscal IN ('{lista}')",
    })
    out = []
    for f in dados.get("features", []):
        g = f.get("geometry")
        if not g:
            continue
        try:
            c = shape(g).centroid
        except Exception:  # noqa: BLE001
            continue
        if c.is_empty:
            continue
        p = f["properties"]
        out.append([
            p.get("cd_quadra_fiscal"), p.get("cd_lote"), p.get("cd_condominio"),
            p.get("nm_logradouro_completo"), p.get("cd_numero_porta"),
            round(c.x, 7), round(c.y, 7),
        ])
    return out


def baixar_setor(setor: str, quadras: set[str]) -> list:
    ordenadas = sorted(quadras)
    out = []
    for i in range(0, len(ordenadas), QUADRAS_POR_REQ):
        out.extend(_feicoes_lote(setor, ordenadas[i : i + QUADRAS_POR_REQ]))
    return out


def de_cache(pasta: Path) -> dict[str, list]:
    """Lê um cache no formato do projeto de referência
    (``<pasta>/lotes/<setor>.json.gz`` com ``{"lotes": [[q,l,cond,logr,num,lon,lat],...]}``)."""
    lotes = pasta / "lotes"
    if not lotes.is_dir():
        sys.exit(f"não encontrei {lotes}")
    return {
        arq.name.split(".")[0]: json.load(gzip.open(arq, "rt", encoding="utf-8"))["lotes"]
        for arq in sorted(lotes.glob("*.json.gz"))
    }


def carregar_distritos(caminho: Path):
    gj = json.loads(caminho.read_text(encoding="utf-8"))
    geoms, props = [], []
    for f in gj["features"]:
        if not f.get("geometry"):
            continue
        geoms.append(shape(f["geometry"]))
        p = f["properties"]
        props.append((
            p.get("nm_distrito_municipal") or "",
            str(p.get("cd_identificador_subprefeitura") or ""),
            p.get("nm_regiao_05") or "",
        ))
    return STRtree(geoms), geoms, props


def distrito_de(lon, lat, arvore, geoms, props):
    pt = Point(lon, lat)
    for i in arvore.query(pt):
        if geoms[int(i)].covers(pt):
            return props[int(i)]
    return ("", "", "")


def _registro(bruto, arvore, geoms, props):
    """``[q, l, cond, logr, num, lon, lat]`` cru → registro de 10 campos com
    distrito resolvido."""
    quadra, lote, cond, logr, num, lon, lat = bruto
    dist, sub, reg = distrito_de(lon, lat, arvore, geoms, props)
    return [quadra, lote, cond, normalizar(logr), para_numero_porta(num), lon, lat, dist, sub, reg]


def escrever(lotes_por_setor: dict, distritos_geojson: Path, saida: Path, origem: str, *, merge=False):
    arvore, geoms, props = carregar_distritos(distritos_geojson)
    saida.mkdir(parents=True, exist_ok=True)
    n_lotes = n_sem_dist = 0
    for setor, brutos in sorted(lotes_por_setor.items()):
        arq = saida / f"{setor}.json.gz"
        registros = (
            json.load(gzip.open(arq, "rt", encoding="utf-8"))["lotes"]
            if merge and arq.exists()
            else []
        )
        vistos = {(r[0], r[1]) for r in registros}
        for bruto in brutos:
            if (bruto[0], bruto[1]) in vistos:
                continue
            registros.append(_registro(bruto, arvore, geoms, props))
        with gzip.open(arq, "wt", encoding="utf-8") as fh:
            json.dump({"lotes": registros}, fh, separators=(",", ":"))
        n_lotes += len(registros)
        n_sem_dist += sum(1 for r in registros if not r[7])
    meta = {
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "origem": origem,
        "setores": len(list(saida.glob("*.json.gz"))),
        "lotes": n_lotes if not merge else "(parcial: merge)",
        "lotes_sem_distrito": n_sem_dist,
    }
    if not merge:
        (saida / "_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    print(json.dumps(meta, ensure_ascii=False, indent=2))


def quadras_da_planilha(caminho: str) -> dict[str, set]:
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    por_setor: dict[str, set] = {}
    for aba in (a for a in wb.sheetnames if len(a) == 8 and a[3] == "-"):
        for linha in wb[aba].iter_rows(min_row=2, values_only=True):
            v = linha[0]
            if v is None:
                continue
            s = str(int(v) if isinstance(v, float) else v).zfill(11)
            if s.isdigit():
                por_setor.setdefault(s[:3], set()).add(s[3:6])
    return por_setor


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cache", metavar="PASTA", help="bootstrap de um cache existente, sem rede")
    g.add_argument("--planilha", metavar="XLSX", help="crawl dos setores/quadras da planilha")
    g.add_argument("--cidade-inteira", action="store_true", help="crawl de todos os setores")
    g.add_argument("--refresh", metavar="SETOR:QUADRA,...", help="crawl só do que falta e faz merge")
    ap.add_argument("--distritos", default=str(RAIZ / "tmp" / "ITBI" / "cache" / "distritos.geojson"))
    ap.add_argument("--saida", default=str(SAIDA))
    args = ap.parse_args(argv)

    saida = Path(args.saida)
    distritos = Path(args.distritos)
    if not distritos.exists():
        sys.exit(f"distritos.geojson não encontrado em {distritos} (use --distritos)")

    if args.cache:
        escrever(de_cache(Path(args.cache)), distritos, saida, f"cache {args.cache}")
        return 0

    if args.planilha:
        por_setor = quadras_da_planilha(args.planilha)
    elif args.refresh:
        por_setor = {}
        for par in args.refresh.split(","):
            setor, quadra = par.split(":")
            por_setor.setdefault(setor, set()).add(quadra)
    else:  # --cidade-inteira: descobre os setores pela camada de distritos não dá;
        sys.exit("--cidade-inteira exige a lista de setores fiscais; use --planilha por ora")

    lotes = {}
    for i, (setor, quadras) in enumerate(sorted(por_setor.items()), 1):
        try:
            lotes[setor] = baixar_setor(setor, quadras)
        except (RuntimeError, Bloqueado) as e:
            print(f"  ERRO setor {setor}: {e}", flush=True)
            lotes[setor] = []
        if i % 20 == 0:
            print(f"  {i}/{len(por_setor)} setores", flush=True)

    escrever(lotes, distritos, saida, f"refresh {args.refresh}" if args.refresh else
             (args.planilha or "cidade-inteira"), merge=bool(args.refresh))
    return 0


if __name__ == "__main__":
    sys.exit(main())
