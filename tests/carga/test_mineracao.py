"""Regras de mineração portadas de tmp/ITBI. Funções puras — sem banco."""

import datetime as dt

import pytest

from radar.carga.mineracao import (
    agio,
    ano_transacao,
    cadastro_defasado,
    cod_natureza,
    grupo_de_uso,
    idade,
    linha_deslocada,
    qualidade,
    rs_m2_construido,
    rs_m2_terreno,
    valor_inconsistente,
)


def test_grupo_de_uso():
    assert grupo_de_uso(20) == "Apartamento / res. vertical"
    assert grupo_de_uso(0) == "Terreno"
    assert grupo_de_uso(10) == "Casa / residência horizontal"
    assert grupo_de_uso(73) == "Outros"  # 73 e 91 não constam na Tabela de USOS
    assert grupo_de_uso(None) == "Outros"
    assert grupo_de_uso("lixo") == "Outros"


def test_rs_m2_construido_trava_de_proporcao():
    assert rs_m2_construido(500_000, 100, 100) == 5000
    assert rs_m2_construido(500_000, 100, 50) is None
    assert rs_m2_construido(500_000, 0, 100) is None
    assert rs_m2_construido(None, 100, 100) is None
    assert rs_m2_construido(0, 100, 100) is None  # base zerada não é R$ 0/m²


def test_rs_m2_terreno_exige_fracao_ideal():
    assert rs_m2_terreno(500_000, 250, 100, 1.0) == 2000
    assert rs_m2_terreno(500_000, 250, 100, 0.02) is None
    assert rs_m2_terreno(500_000, 250, 50, 1.0) is None


def test_agio_so_acima_de_5_pct():
    assert agio(600_000, 500_000, 100) == pytest.approx(1.2)
    assert agio(600_000, 500_000, 0.32) is None


def test_cod_natureza():
    assert cod_natureza("1.Compra e venda") == 1
    assert cod_natureza("20.Realização ou integralização de capital ") == 20
    assert cod_natureza("") is None
    assert cod_natureza(None) is None


def test_linha_deslocada():
    assert linha_deslocada("Ativo Predial", "1.SFH") is False
    assert linha_deslocada(dt.datetime(2020, 1, 1), "x") is True
    assert linha_deslocada("Ativo Predial", 12345) is True


def test_valor_inconsistente():
    assert valor_inconsistente(260_000, 260_000, 47_600.38) is False
    assert valor_inconsistente(0, 260_000, 47_600) is True
    assert valor_inconsistente(None, 100, 100) is True


def test_qualidade():
    assert qualidade(False, False) == 0
    assert qualidade(True, False) == 1
    assert qualidade(False, True) == 2
    assert qualidade(True, True) == 3


def test_cadastro_defasado_casos_reais():
    assert cadastro_defasado("1.Compra e venda", "2.Minha Casa Minha Vida", 0.07, 0) is True
    assert cadastro_defasado("1.Compra e venda", "2.Minha Casa Minha Vida", 0.32, 74) is True


def test_cadastro_defasado_negativos():
    assert cadastro_defasado("1.Compra e venda", "2.Minha Casa Minha Vida", 100, 0) is False
    assert cadastro_defasado("1.Compra e venda", "2.Minha Casa Minha Vida", 0.07, 20) is False
    assert cadastro_defasado("1.Compra e venda", None, 0.07, 0) is False
    assert cadastro_defasado("20.Integralização de capital", "2.Minha Casa Minha Vida", 0.07, 0) is False


def test_idade():
    assert idade(1992) == 2026 - 1992
    assert idade(None) is None
    assert idade(0) is None


def test_ano_transacao():
    assert ano_transacao(dt.date(2025, 8, 29)) == 2025
    assert ano_transacao(None) is None
