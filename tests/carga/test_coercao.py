"""Coerção de valores de célula. Funções puras — sem banco."""

import datetime as dt

from radar.carga.coercao import (
    mes_guia,
    para_cep,
    para_data,
    para_numero,
    para_numero_porta,
    para_sql,
    para_texto,
)


def test_para_texto():
    assert para_texto(None) == ""
    assert para_texto("  x ") == "x"
    assert para_texto(71) == "71"


def test_para_numero_aceita_formato_brasileiro():
    assert para_numero("1.234,56") == 1234.56
    assert para_numero(605994.39) == 605994.39
    assert para_numero(260000) == 260000.0
    assert para_numero("") is None
    assert para_numero(None) is None
    assert para_numero("abc") is None
    assert para_numero(True) is None


def test_para_sql_reconstroi_zero_a_esquerda():
    assert para_sql(12318300101) == "12318300101"
    assert para_sql("12318300101") == "12318300101"
    assert para_sql(5202800061.0) == "05202800061"
    assert para_sql(None) is None
    assert para_sql("nao-e-numero") is None


def test_para_cep():
    assert para_cep(5662000) == "05662000"
    assert para_cep("5662000,0000") == "05662000"
    assert para_cep(0) == ""
    assert para_cep(None) == ""


def test_para_numero_porta():
    assert para_numero_porta(71) == "71"
    assert para_numero_porta("071") == "71"
    assert para_numero_porta(0) == ""
    assert para_numero_porta(99999) == ""
    assert para_numero_porta(None) == ""
    assert para_numero_porta("71A") == "71A"


def test_para_numero_porta_aceita_decimal():
    # A planilha de 2024 grava a porta como decimal; o ponto não é milhar aqui.
    assert para_numero_porta(295.0) == "295"
    assert para_numero_porta(99999.0) == ""
    assert para_numero_porta(0.0) == ""


def test_para_data():
    assert para_data(dt.datetime(2026, 1, 21, 0, 0)) == dt.date(2026, 1, 21)
    assert para_data(dt.date(2025, 8, 29)) == dt.date(2025, 8, 29)
    assert para_data("8/7/2026") == dt.date(2026, 7, 8)
    assert para_data(None) is None
    assert para_data("") is None


def test_mes_guia():
    assert mes_guia("MAR-2026") == 3
    assert mes_guia("jul-2026") == 7
    assert mes_guia("qualquer") is None
