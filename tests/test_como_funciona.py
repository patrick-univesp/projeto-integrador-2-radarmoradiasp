"""Página "Como funciona": a linha de exemplo e os números de cada etapa."""

import re
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse

from radar import como_funciona
from radar.models import Transacao


@pytest.fixture(autouse=True)
def _cache_limpo():
    cache.clear()
    yield
    cache.clear()


def _transacao(**campos):
    base = {"sql": "02702102743", "valor_transacao": 1, "base_calculo": 1,
            "ano_guia": 2026, "mes_guia": 1, "geo_nivel": "T1"}
    return Transacao.objects.create(**{**base, **campos})


def test_linha_de_exemplo_passa_pela_carga_de_verdade():
    """O texto da página afirma cada um destes resultados ("parou no segundo
    degrau", "passou nos seis", bairro vazio). Se uma regra da carga mudar, este
    teste avisa que a página ficou mentindo."""
    t = como_funciona.transacao_exemplo()
    assert t.sql == "02702102743"
    assert t.cep == "03164120"
    assert t.bairro_norm == ""
    assert t.geo_nivel == "T2"
    assert t.distrito_slug == "mooca"
    assert t.uso_grupo == "Apartamento / res. vertical"
    assert t.rs_m2_construido == Decimal("5816.33")
    assert t.qualidade == 0


@pytest.mark.django_db
def test_pagina_responde_com_a_base_vazia(client):
    r = client.get(reverse("radar:como_funciona"))
    assert r.status_code == 200
    corpo = r.content.decode()
    assert "Da planilha da Prefeitura ao mapa" in corpo
    assert "2702102743" in corpo
    assert 'href="/regiao/mooca/"' in corpo


@pytest.mark.django_db
def test_numeros_saem_do_banco():
    _transacao(qualidade=0)
    _transacao(qualidade=4 | 32, geo_nivel="T2")
    _transacao(qualidade=32, geo_nivel="--", mes_guia=2)
    _transacao(rs_m2_construido=Decimal("5000"), bairro="TORRE 1", bairro_norm="")

    n = como_funciona.numeros_da_base()
    assert n["total"] == 4
    assert n["por_bit"] == {1: 0, 2: 0, 4: 1, 8: 0, 16: 0, 32: 2}
    assert n["com_ressalva"] == 2
    assert n["com_ponto"] == 3
    assert n["com_ponto_sem_ressalva"] == 2
    assert n["com_rs_m2"] == 1
    assert n["bairro_lixo"] == 1
    assert n["por_mes"] == [(2026, 1, 3), (2026, 2, 1)]
    assert n["por_geo"] == {"T1": 2, "T2": 1, "--": 1}
    assert n["setores"] == [("027", 4)]


@pytest.mark.django_db
def test_pagina_marca_o_degrau_e_o_mes_da_linha(client):
    _transacao(geo_nivel="T2")
    _transacao(mes_guia=2)
    ctx = client.get(reverse("radar:como_funciona")).context

    assert [d["estado"] for d in ctx["degraus"]] == ["tentou", "achou", "depois", "depois", "depois"]
    assert [m["exemplo"] for m in ctx["meses"]] == [True, False]
    assert ctx["n_blocos"] == 1


@pytest.mark.django_db
def test_pagina_nao_usa_style_nem_script_inline(client):
    """A CSP de produção bloqueia os dois sem aviso: uma barra com largura em
    style="" simplesmente não aparece."""
    _transacao()
    corpo = client.get(reverse("radar:como_funciona")).content.decode()
    assert "style=" not in corpo
    inline = re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", corpo, re.S)
    assert not [t for t in inline if t.strip()]


@pytest.mark.django_db
def test_cabecalho_e_rodape_linkam_a_pagina(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert corpo.count('href="/como-funciona/"') == 2
