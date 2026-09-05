"""Regras de mineração portadas de tmp/ITBI. Funções puras — sem banco."""

import datetime as dt

import pytest

from radar.carga.mineracao import (
    agio,
    ano_transacao,
    cadastro_defasado,
    cod_natureza,
    data_implausivel,
    financiamento_incompativel,
    grupo_de_uso,
    idade,
    linha_deslocada,
    qualidade,
    rs_m2_construido,
    rs_m2_terreno,
    situacao_sql_invalida,
    valor_inconsistente,
    valor_irrisorio,
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


def test_qualidade_bits_novos():
    assert qualidade(False, False, irrisorio=True) == 4
    assert qualidade(False, False, financiamento_ruim=True) == 8
    assert qualidade(False, False, data_ruim=True) == 16
    assert qualidade(False, False, sql_ruim=True) == 32
    assert qualidade(True, True, irrisorio=True, financiamento_ruim=True, data_ruim=True,
                     sql_ruim=True) == 63


def test_situacao_sql_invalida():
    assert situacao_sql_invalida("Cancelado Predial") is True
    assert situacao_sql_invalida("Não_Existe_Exercício") is True
    assert situacao_sql_invalida("NAO_EXISTE_EXERCICIO") is True  # caixa/acento não importam
    assert situacao_sql_invalida("Ativo Predial") is False
    assert situacao_sql_invalida("Ativo Territorial") is False
    # Cancelado Territorial parece que deveria casar, mas fica de fora de propósito
    assert situacao_sql_invalida("Cancelado Territorial") is False
    assert situacao_sql_invalida("") is False
    assert situacao_sql_invalida(None) is False


def test_valor_irrisorio():
    """Achado real: R$ 0,01 e R$ 1,00 passavam como qualidade=0 porque o VVR
    "corrigia" a base de cálculo — o valor de origem já denuncia a linha."""
    assert valor_irrisorio(0.01) is True
    assert valor_irrisorio(999.99) is True
    assert valor_irrisorio(1000) is False
    assert valor_irrisorio(500_000) is False
    assert valor_irrisorio(None) is False


def test_financiamento_incompativel():
    """Caso real da auditoria: R$ 711,78 declarado, R$ 320.000 financiado."""
    assert financiamento_incompativel(711.78, 320_000) is True
    assert financiamento_incompativel(500_000, 400_000) is False
    assert financiamento_incompativel(500_000, None) is False
    assert financiamento_incompativel(None, 320_000) is False
    assert financiamento_incompativel(0, 320_000) is False


def test_data_implausivel():
    assert data_implausivel(dt.date(1994, 6, 24)) is False  # contrato antigo real, legítimo
    assert data_implausivel(dt.date(2026, 7, 1)) is False
    assert data_implausivel(dt.date(1989, 12, 31)) is True
    assert data_implausivel(dt.date(2099, 1, 1)) is True
    assert data_implausivel(None) is False


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
