#!/usr/bin/env python3
"""Gera tests/dados/amostra_itbi.xlsx — uma planilha sintética minúscula (2 abas,
poucas linhas) que exercita os casos difíceis da carga. Não é extraída da planilha
real; é montada à mão para o teste ser autossuficiente.

    python tests/dados/gerar_amostra_itbi.py
"""

import datetime as dt
from pathlib import Path

import openpyxl

CABECALHO = [
    "N° do Cadastro (SQL)", "Nome do Logradouro", "Número", "Complemento", "Bairro",
    "Referência", "CEP", "Natureza de Transação", "Valor de Transação", "Data de Transação",
    "Valor Venal de Referência", "Proporção Transmitida (%)", "Valor Venal de Referência (proporcional)",
    "Base de Cálculo adotada", "Tipo de Financiamento", "Valor Financiado", "Cartório de Registro",
    "Matrícula do Imóvel", "Situação do SQL", "Área do Terreno (m2)", "Testada (m)", "Fração Ideal",
    "Área Construída (m2)", "Uso (IPTU)", "Descrição do uso (IPTU)", "Padrão (IPTU)",
    "Descrição do padrão (IPTU)", "ACC (IPTU)",
]

D = dt.datetime

# 28 colunas por linha. SQLs de setor 001 e 165 batem com dados_geo_amostra/.
LINHAS_JAN = [
    # sql inteiro, apto, casa T1 setor 001 quadra 036 lote 0428 -> REPUBLICA
    [103604280, "R BRIG TOBIAS", 391, None, "REPUBLICA", None, 1103010, "1.Compra e venda",
     600000, D(2026, 1, 10), 500000, 100, 500000, 600000, "1.SFH", 480000, "1º CRI", 1000,
     "Ativo Predial", 300, 10.0, 1.0, 120, 20, "APARTAMENTO EM CONDOMINIO", 23, "RESIDENCIAL VERTICAL", 2010],
    # CEP com zero à esquerda, bairro vazio
    [16526701080, "R ARMANDO DUPRAT", 32, "AP 51", None, None, 5662000, "1.Compra e venda",
     260000, D(2025, 8, 29), 430000, 100, 430000, 430000, None, 0, "18º CRI", 1000,
     "Ativo Predial", 250, 8.0, 1.0, 90, 10, "RESIDENCIA", 13, "RESIDENCIAL HORIZONTAL", 1998],
    # bairro = lixo de complemento -> bairro_norm vazio
    [103604280, "R BRIG TOBIAS", 100, None, "TORRE 2", None, 1103010, "1.Compra e venda",
     350000, D(2026, 1, 15), 350000, 100, 350000, 350000, None, 0, "1º CRI", 2000,
     "Ativo Predial", 0, 0, 1.0, 0, 0, "TERRENO", 0, "TERRENO", None],
    # apto fracionado + MCMV num SQL "terreno" -> flag_cadastro_defasado
    [16526701080, "R ARMANDO DUPRAT", 99999, "BL A AP 71", "JARDIM SAO LUIS", None, 5820000,
     "1.Compra e venda", 180000, D(2026, 1, 20), 9000000, 0.05, 4500, 180000,
     "2.Minha Casa Minha Vida", 150000, "18º CRI", 3000, "Ativo Territorial", 5000, 40.0, 1.0,
     0, 0, "TERRENO", 0, "TERRENO", None],
    # colunas deslocadas: datetime onde é "Situação do SQL" -> qualidade != 0
    [103604280, "R BRIG TOBIAS", 5, None, "REPUBLICA", None, 1103010, "1.Compra e venda",
     420000, D(2026, 1, 22), 420000, 100, 420000, 420000, None, 0, "1º CRI", 4000,
     D(2020, 1, 1), 100, 5.0, 1.0, 80, 10, "RESIDENCIA", 12, "RESIDENCIAL HORIZONTAL", 1970],
    # base de cálculo zerada com valor declarado -> qualidade != 0, rs_m2 = None (não 0)
    [103604280, "R BRIG TOBIAS", 7, None, "REPUBLICA", None, 1103010, "1.Compra e venda",
     500000, D(2026, 1, 25), 300000, 100, 300000, 0, None, 0, "1º CRI", 5000,
     "Ativo Predial", 200, 6.0, 1.0, 100, 20, "APARTAMENTO EM CONDOMINIO", 21, "RESIDENCIAL VERTICAL", 1985],
    # SQL de setor fora da amostra de geo -> geo_nivel '--'
    [99912300010, "R INEXISTENTE", 10, None, "BAIRRO X", None, 8000000, "1.Compra e venda",
     700000, D(2026, 1, 28), 700000, 100, 700000, 700000, None, 0, "9º CRI", 6000,
     "Ativo Predial", 300, 10.0, 1.0, 150, 20, "APARTAMENTO EM CONDOMINIO", 24, "RESIDENCIAL VERTICAL", 2015],
]

LINHAS_FEV = [
    # transação antiga (anos 1990)
    [103604280, "R BRIG TOBIAS", 401, None, "REPUBLICA", None, 1103010, "1.Compra e venda",
     90000, D(1997, 6, 15), 90000, 100, 90000, 90000, None, 0, "1º CRI", 7000,
     "Ativo Predial", 300, 10.0, 1.0, 110, 10, "RESIDENCIA", 11, "RESIDENCIAL HORIZONTAL", 1965],
    # grafia aglutinada de bairro
    [16526701080, "R ARMANDO DUPRAT", 45, None, "ITAIMBIBI", None, 4530000, "1.Compra e venda",
     2000000, D(2026, 2, 3), 2000000, 100, 2000000, 2000000, "1.SFH", 1600000, "1º CRI", 8000,
     "Ativo Predial", 400, 12.0, 1.0, 200, 20, "APARTAMENTO EM CONDOMINIO", 25, "RESIDENCIAL VERTICAL", 2005],
]


def main():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for nome, linhas in (("JAN-2026", LINHAS_JAN), ("FEV-2026", LINHAS_FEV)):
        ws = wb.create_sheet(nome)
        ws.append(CABECALHO)
        for linha in linhas:
            ws.append(linha)
    destino = Path(__file__).parent / "amostra_itbi.xlsx"
    wb.save(destino)
    print(f"gravado {destino} ({destino.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
