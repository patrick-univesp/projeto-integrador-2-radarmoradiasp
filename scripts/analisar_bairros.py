#!/usr/bin/env python3
"""Uso único: mede o efeito da normalização de bairro sobre a planilha de ITBI
e lista candidatos a grafia aglutinada, para alimentar ``radar/grafias_bairro.py``.

A decisão final de cada par é humana — este script só agrupa.

    python scripts/analisar_bairros.py "tmp/GUIAS DE ITBI PAGAS (27082026) XLS.xlsx"

Precisa de ``openpyxl`` (já em requirements.txt).
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import openpyxl  # noqa: E402

from radar.carga.normalizacao import eh_lixo_de_bairro, normalizar  # noqa: E402

COL_BAIRRO = 4  # posição da coluna "Bairro" nas abas mensais


def main(caminho: str) -> int:
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    abas = [a for a in wb.sheetnames if len(a) == 8 and a[3] == "-"]

    brutos = Counter()
    for aba in abas:
        for linha in wb[aba].iter_rows(min_row=2, values_only=True):
            if linha[0] is None:
                continue
            b = linha[COL_BAIRRO]
            brutos["" if b is None or not str(b).strip() else str(b).strip()] += 1

    vazio = brutos.pop("", 0)
    total = sum(brutos.values())
    print(f"abas: {', '.join(abas)}")
    print(f"linhas com bairro preenchido: {total}  |  vazias: {vazio}")
    print(f"grafias distintas (cruas): {len(brutos)}")

    norm = Counter()
    lixo = 0
    for b, c in brutos.items():
        n = normalizar(b)
        if eh_lixo_de_bairro(n):
            lixo += c
            continue
        norm[n] += c
    print(f"grafias distintas após normalizar: {len(norm)}")
    print(f"linhas descartadas como lixo de complemento: {lixo} ({100 * lixo / total:.1f}%)")

    sem_espaco: dict[str, list[str]] = {}
    for k in norm:
        sem_espaco.setdefault(k.replace(" ", ""), []).append(k)
    grupos = {k: v for k, v in sem_espaco.items() if len(v) > 1}
    print(f"\ncandidatos a grafia aglutinada (mesma string sem espaços): {len(grupos)}")
    for _, grafias in sorted(grupos.items(), key=lambda kv: -sum(norm[g] for g in kv[1]))[:30]:
        gs = sorted(grafias, key=lambda g: -norm[g])
        print("  " + "  |  ".join(f"{g!r}={norm[g]}" for g in gs))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
