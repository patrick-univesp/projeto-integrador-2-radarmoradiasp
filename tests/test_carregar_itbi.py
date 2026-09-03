"""Carga ponta a ponta com a amostra sintética tests/dados/amostra_itbi.xlsx."""

from pathlib import Path

import pytest

from radar.management.commands.carregar_itbi import carregar
from radar.models import Transacao

XLSX = Path(__file__).parent / "dados" / "amostra_itbi.xlsx"
GEO = Path(__file__).parent / "dados" / "dados_geo_amostra"


def _carregar(**kw):
    return carregar(str(XLSX), base_dir_geo=str(GEO), blocos=3, **kw)


@pytest.mark.django_db
def test_carrega_todas_as_linhas():
    r = _carregar()
    assert r["total"]["lidas"] == 10
    assert r["total"]["gravadas"] == 10
    assert Transacao.objects.count() == 10


@pytest.mark.django_db
def test_cep_preserva_zero_a_esquerda():
    _carregar()
    assert Transacao.objects.filter(cep="05662000").exists()


@pytest.mark.django_db
def test_nenhum_rs_m2_zero():
    _carregar()
    assert not Transacao.objects.filter(rs_m2_construido=0).exists()
    zerada = Transacao.objects.get(valor_transacao=500000, base_calculo=0)
    assert zerada.rs_m2_construido is None
    assert zerada.qualidade != 0


@pytest.mark.django_db
def test_bairro_vazio_e_lixo_viram_bairro_norm_vazio():
    _carregar()
    assert Transacao.objects.filter(bairro="", bairro_norm="").count() == 1
    assert Transacao.objects.get(bairro="TORRE 2").bairro_norm == ""


@pytest.mark.django_db
def test_grafia_aglutinada_normaliza():
    _carregar()
    assert Transacao.objects.get(bairro="ITAIMBIBI").bairro_norm == "ITAIM BIBI"


@pytest.mark.django_db
def test_geo_por_lookup_cobre_a_escada():
    _carregar()
    t1 = Transacao.objects.get(sql="00103604280", numero="391")
    assert (t1.geo_nivel, t1.distrito) == ("T1", "REPUBLICA")
    t3 = Transacao.objects.get(sql="00102302388")
    assert (t3.geo_nivel, t3.distrito) == ("T3", "SE")
    sem = Transacao.objects.get(sql="99912300010")
    assert (sem.geo_nivel, sem.distrito) == ("--", "")  # sem match: entra, não é pulada


@pytest.mark.django_db
def test_flag_cadastro_defasado():
    _carregar()
    assert Transacao.objects.get(sql="16526701080", complemento="BL A AP 71").flag_cadastro_defasado
    assert not Transacao.objects.get(sql="00103604280", numero="391").flag_cadastro_defasado


@pytest.mark.django_db
def test_ano_e_mes_da_guia():
    _carregar()
    assert Transacao.objects.filter(ano_guia=2026, mes_guia=1).count() == 8
    assert Transacao.objects.filter(ano_guia=2026, mes_guia=2).count() == 2
    antiga = Transacao.objects.get(valor_transacao=90000)
    assert antiga.ano_transacao == 1997  # ano do negócio
    assert antiga.mes_guia == 2  # mês da guia


@pytest.mark.django_db
def test_substituir_mes_e_idempotente():
    _carregar()
    _carregar(substituir_mes=True)
    assert Transacao.objects.count() == 10


@pytest.mark.django_db
def test_dry_run_nao_grava():
    r = _carregar(dry_run=True)
    assert r["total"]["lidas"] == 10
    assert Transacao.objects.count() == 0


@pytest.mark.django_db
def test_abas_filtra():
    _carregar(abas=["FEV-2026"])
    assert Transacao.objects.count() == 2
