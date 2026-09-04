"""Modelo Transacao: o que não pode regredir sem estragar o número da tela."""

from decimal import Decimal

import pytest
from django.db import connection

from radar.models import Transacao


def _nova(**extra):
    campos = {
        "sql": "01234567890",
        "logradouro": "RUA DOS ANDRADAS",
        "numero": "71",
        "bairro": "REPUBLICA",
        "bairro_norm": "REPUBLICA",
        "valor_transacao": Decimal("450000.00"),
        "base_calculo": Decimal("450000.00"),
    }
    campos.update(extra)
    return Transacao.objects.create(**campos)


@pytest.mark.django_db
def test_rs_m2_nulo_persiste_como_null_nao_zero():
    """Um zero em rs_m2_construido contamina a mediana exibida na tela."""
    obj = _nova(rs_m2_construido=None, area_construida=None)
    obj.refresh_from_db()
    assert obj.rs_m2_construido is None
    with connection.cursor() as cur:
        cur.execute("SELECT rs_m2_construido FROM radar_transacao WHERE id = %s", [obj.id])
        assert cur.fetchone()[0] is None


@pytest.mark.django_db
def test_cep_preserva_zero_a_esquerda():
    """O CEP chegou como float no CSV e perdeu o zero: 5662000 é 05662-000."""
    obj = _nova(cep="05662000")
    obj.refresh_from_db()
    assert obj.cep == "05662000"


@pytest.mark.django_db
def test_bairro_vazio_e_aceito():
    """40% das linhas da planilha de origem não têm bairro. Vazio é caminho normal."""
    obj = _nova(bairro="", bairro_norm="")
    obj.refresh_from_db()
    assert obj.bairro == ""
    assert obj.bairro_norm == ""


@pytest.mark.django_db
def test_indices_esperados_existem():
    with connection.cursor() as cur:
        constraints = connection.introspection.get_constraints(cur, "radar_transacao")
    indices = {tuple(c["columns"]) for c in constraints.values() if c["index"]}
    esperados = [
        ("bairro_norm",),
        ("cep",),
        ("distrito",),
        ("distrito_slug",),
        ("ano_transacao",),
        ("uso_grupo",),
        ("qualidade",),
        ("lat", "lon"),
        ("distrito_slug", "ano_transacao"),
        ("bairro_norm", "ano_transacao"),
    ]
    faltando = [e for e in esperados if e not in indices]
    assert not faltando, f"índices ausentes: {faltando}"


@pytest.mark.django_db
def test_qualidade_default_zero():
    """qualidade == 0 é a linha boa; o default não pode ser outro."""
    assert _nova().qualidade == 0


@pytest.mark.django_db
def test_flags_e_complemento_tem_default_neutro():
    """complemento vazio e flag_cadastro_defasado falso são o caso comum."""
    obj = _nova()
    obj.refresh_from_db()
    assert obj.complemento == ""
    assert obj.flag_cadastro_defasado is False
