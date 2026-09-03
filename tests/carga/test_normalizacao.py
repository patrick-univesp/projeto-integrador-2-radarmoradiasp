"""Normalização de bairro e logradouro. Funções puras — sem banco."""

import pytest

from radar.carga.grafias_bairro import GRAFIAS
from radar.carga.normalizacao import eh_lixo_de_bairro, normalizar, normalizar_bairro


def test_acento_caixa_e_pontuacao():
    assert normalizar("Vila Mariana") == "VILA MARIANA"
    assert normalizar("SÃO PAULO") == "SAO PAULO"
    assert normalizar("Jd. Paulista, 2") == "JARDIM PAULISTA 2"


def test_vazio():
    assert normalizar("") == ""
    assert normalizar(None) == ""
    assert normalizar("   ") == ""


def test_expande_abreviacao_de_logradouro():
    assert normalizar("R SEN OTAVIO MANGABEIRA").startswith("RUA ")
    assert normalizar("Av Paulista") == "AVENIDA PAULISTA"
    assert normalizar("Pç da Sé") == "PRACA DA SE"


def test_expande_abreviacao_de_bairro():
    assert normalizar("VL FORMOSA") == "VILA FORMOSA"
    assert normalizar("JD MIRIAM") == "JARDIM MIRIAM"
    assert normalizar("STO AMARO") == "SANTO AMARO"
    assert normalizar("STO AMARO") == normalizar("Santo Amaro")


def test_grafia_aglutinada():
    assert normalizar("ITAIMBIBI") == "ITAIM BIBI"
    assert normalizar("ITAIMBIBI") == normalizar("Itaim Bibi")
    assert normalizar("VLFORMOSA") == "VILA FORMOSA"
    assert normalizar("casaverde") == "CASA VERDE"


@pytest.mark.parametrize("colado", list(GRAFIAS))
def test_toda_grafia_da_tabela_resolve(colado):
    assert normalizar(colado) == GRAFIAS[colado]


@pytest.mark.parametrize(
    "lixo", ["TORRE 1", "Torre A", "2 SUBSOLO", "SS3", "BLOCO 2", "E 1 DP", "COBERTURA"]
)
def test_lixo_de_bairro_detectado(lixo):
    assert eh_lixo_de_bairro(normalizar(lixo)) is True


@pytest.mark.parametrize("real", ["MOOCA", "VILA FORMOSA", "JARDIM PAULISTA", "SANTO AMARO"])
def test_bairro_real_nao_e_lixo(real):
    assert eh_lixo_de_bairro(real) is False


def test_normalizar_bairro_esvazia_o_lixo():
    assert normalizar_bairro("TORRE 1") == ""
    assert normalizar_bairro("Vila Formosa") == "VILA FORMOSA"
