#!/usr/bin/env python3
"""Extrai uma amostra REAL da planilha completa, escolhida para cobrir os casos
difíceis da carga — não as primeiras N linhas.

    python scripts/gerar_amostra.py "GUIAS DE ITBI PAGAS ... .xlsx" [--linhas 150] [--saida amostra.xlsx]

Precisa de ``openpyxl``. **Não mexe em geo** — se for adotar a saída como fixture do
CI, também recorte ``radar/dados_geo/`` para os setores dos SQLs escolhidos (copiar
os ``<setor>.json.gz`` correspondentes para ``tests/dados/dados_geo_amostra/``).

A fixture que o CI usa hoje é a **sintética** (``tests/dados/amostra_itbi.xlsx``,
montada à mão por ``tests/dados/gerar_amostra_itbi.py``): é hermética e o recorte de
geo fica minúsculo. Este script é para conferir a carga contra dado real.
"""

import argparse
import datetime as dt
import random
import sys
from pathlib import Path

import openpyxl

C_SQL, C_BAIRRO, C_PROP, C_SITSQL, C_TIPOFIN, C_USOCOD, C_DATA = 0, 4, 11, 18, 14, 23, 9


def _rotulos(linha):
    """Quais casos difíceis esta linha exercita."""
    r = set()
    sql = linha[C_SQL]
    if isinstance(sql, (int, float)) and int(sql) < 100_000_000_000 and str(int(sql)).zfill(11).startswith("00"):
        r.add("setor<100")
    b = linha[C_BAIRRO]
    r.add("bairro-vazio" if b is None or not str(b).strip() else "bairro-cheio")
    prop = linha[C_PROP]
    if isinstance(prop, (int, float)):
        r.add("prop>=99" if prop >= 99 else "prop<99")
    if isinstance(linha[C_SITSQL], (dt.datetime, dt.date, int, float)):
        r.add("colunas-deslocadas")
    if isinstance(linha[C_TIPOFIN], (int, float)):
        r.add("colunas-deslocadas")
    uso = linha[C_USOCOD]
    if uso is not None:
        try:
            r.add({0: "uso-terreno", 20: "uso-apto"}.get(int(uso), f"uso-{int(uso)}"))
        except (TypeError, ValueError):
            pass
    d = linha[C_DATA]
    ano = getattr(d, "year", None)
    if ano:
        r.add("ano-antigo" if ano < 2005 else "ano-recente")
    return r


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("planilha")
    ap.add_argument("--linhas", type=int, default=150)
    ap.add_argument("--saida", default="amostra_real_itbi.xlsx")
    ap.add_argument("--por-caso", type=int, default=6, help="linhas por caso difícil")
    args = ap.parse_args(argv)

    wb = openpyxl.load_workbook(args.planilha, read_only=True, data_only=True)
    abas = [a for a in wb.sheetnames if len(a) == 8 and a[3] == "-"][:3]

    cabecalho = None
    por_caso: dict[str, list] = {}
    todas: list[tuple[str, tuple]] = []
    for aba in abas:
        for i, linha in enumerate(wb[aba].iter_rows(values_only=True)):
            if i == 0:
                cabecalho = list(linha[:28])
                continue
            if linha[C_SQL] is None:
                continue
            todas.append((aba, linha[:28]))
            for rot in _rotulos(linha[:28]):
                por_caso.setdefault(rot, [])
                if len(por_caso[rot]) < args.por_caso:
                    por_caso[rot].append((aba, linha[:28]))

    escolhidas = {id(v): v for grupo in por_caso.values() for v in grupo}
    faltam = args.linhas - len(escolhidas)
    if faltam > 0:
        for v in random.sample(todas, min(faltam, len(todas))):
            escolhidas.setdefault(id(v), v)

    saida = openpyxl.Workbook()
    saida.remove(saida.active)
    por_aba: dict[str, list] = {}
    for aba, linha in escolhidas.values():
        por_aba.setdefault(aba, []).append(linha)
    for aba, linhas in por_aba.items():
        ws = saida.create_sheet(aba)
        ws.append(cabecalho)
        for linha in linhas:
            ws.append(list(linha))
    Path(args.saida).parent.mkdir(parents=True, exist_ok=True)
    saida.save(args.saida)

    print(f"{len(escolhidas)} linhas -> {args.saida}")
    print("casos cobertos:", ", ".join(sorted(por_caso)))
    faltando = {"setor<100", "bairro-vazio", "bairro-cheio", "prop<99", "prop>=99",
                "colunas-deslocadas", "uso-terreno", "uso-apto", "ano-antigo"} - set(por_caso)
    if faltando:
        print("!! não achei linhas para:", ", ".join(sorted(faltando)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
