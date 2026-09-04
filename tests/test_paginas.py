"""Casca da interface: rotas, template e requisitos que não podem regredir."""

import re

import pytest
from django.template import Context
from django.template.loader import get_template
from django.urls import reverse


@pytest.mark.django_db
def test_inicio_responde(client):
    r = client.get(reverse("radar:inicio"))
    assert r.status_code == 200
    assert "Quanto se pagou de verdade" in r.content.decode()


@pytest.mark.django_db
def test_inicio_traz_atalhos_de_regiao(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert 'href="/regiao/mooca/"' in corpo
    assert "Itaim Bibi" in corpo


def _transacao(ano_guia, mes_guia):
    from radar.models import Transacao

    return Transacao.objects.create(
        sql="03500000100", valor_transacao=1, base_calculo=1,
        ano_guia=ano_guia, mes_guia=mes_guia,
    )


@pytest.mark.django_db
def test_resumo_da_base_conta_e_datar_o_periodo():
    """O total e o período da home vêm do banco, não de string em código (issue #06)."""
    from radar.views import _resumo_da_base

    _transacao(2026, 1)
    _transacao(2026, 7)
    _transacao(2026, 7)
    assert _resumo_da_base() == {
        "n_vendas": 3, "total_vendas": "3", "periodo": "janeiro a julho de 2026",
    }


@pytest.mark.django_db
def test_resumo_da_base_atravessa_anos():
    from radar.views import _resumo_da_base

    _transacao(2025, 11)
    _transacao(2026, 3)
    assert _resumo_da_base()["periodo"] == "novembro de 2025 a março de 2026"


@pytest.mark.django_db
def test_resumo_da_base_um_mes_so():
    from radar.views import _resumo_da_base

    _transacao(2026, 7)
    assert _resumo_da_base()["periodo"] == "julho de 2026"


@pytest.mark.django_db
def test_resumo_da_base_vazio_nao_quebra():
    """Ambiente sem carga (dev recém-migrado): a home renderiza mesmo assim."""
    from radar.views import _resumo_da_base

    assert _resumo_da_base() == {"n_vendas": 0, "total_vendas": "0", "periodo": ""}


@pytest.mark.django_db
def test_inicio_mostra_total_e_periodo_quando_ha_dados(client):
    _transacao(2026, 1)
    _transacao(2026, 7)
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert 'data-contador="2">2</strong>' in corpo
    assert "transações reais, de janeiro a julho de 2026." in corpo


@pytest.mark.django_db
def test_inicio_omite_a_linha_da_base_quando_vazia(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert "transações reais" not in corpo


def test_busca_aceita_termo(client):
    r = client.get(reverse("radar:busca"), {"q": "Mooca"})
    assert r.status_code == 200
    assert "Mooca" in r.content.decode()


def test_regiao_responde(client):
    r = client.get(reverse("radar:regiao", args=["mooca"]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_inicio_tem_botao_entrar(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert 'href="/entrar/"' in corpo
    assert "Entrar" in corpo


def test_entrar_renderiza_pagina_erro(client):
    r = client.get(reverse("radar:entrar"))
    assert r.status_code == 404
    assert "Esta página não existe" in r.content.decode()



def test_500_renderiza_sem_contexto_de_requisicao():
    """O handler500 do Django renderiza sem request. Se o template usar url ou
    static, ele estoura justamente durante um erro — e o usuário vê uma pilha
    em vez da página. Esta é a regressão que o teste impede."""
    saida = get_template("500.html").template.render(Context({}))
    assert "quebrou do nosso lado" in saida
    assert "{%" not in saida


@pytest.mark.parametrize(
    "nome",
    [
        "css/tokens.css",
        "css/base.css",
        "css/transicao.css",
        "css/erro.css",
        "js/busca_animada.js",
        "js/contador_transacoes.js",
    ],
)
def test_estatico_existe(nome):
    from django.contrib.staticfiles import finders

    assert finders.find(nome), f"não encontrado em STATICFILES_DIRS: {nome}"


@pytest.mark.django_db
def test_inicio_carrega_busca_animada(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert "busca_animada.js" in corpo


@pytest.mark.django_db
def test_inicio_carrega_contador_de_transacoes(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert '<script src="/static/js/contador_transacoes.js" defer></script>' in corpo


def test_contador_respeita_reduced_motion():
    """A contagem é cosmética; quem pede menos movimento não deve recebê-la."""
    from pathlib import Path

    js = Path("static/js/contador_transacoes.js").read_text()
    assert "prefers-reduced-motion" in js


@pytest.mark.django_db
def test_sem_script_inline(client):
    """A CSP de produção (issue #11) não vai permitir script inline. Hoje a
    página não tem JavaScript nenhum; quando tiver, tem de ser arquivo
    externo."""
    corpo = client.get(reverse("radar:inicio")).content.decode()
    inline = re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", corpo, re.S)
    assert not [t for t in inline if t.strip()], "há script inline no HTML"


def test_css_nao_tem_cor_literal():
    """Toda cor vive em tokens.css. Se arquivos de CSS ganharem um hex, o tema escuro
    para de funcionar naquele ponto e ninguém percebe até a apresentação.

    Exceção: declarações de máscara. Ali a cor não é tinta — só o canal alfa
    do degradê é lido, e qualquer cor opaca dá o mesmo resultado. Não é um
    valor que o tema possa querer trocar."""
    from pathlib import Path

    for css_file in Path("static/css").glob("*.css"):
        if css_file.name in ("tokens.css", "admin-marca.css"):
            continue
        css = css_file.read_text()
        sem_comentario = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        pintura = ";".join(
            d for d in sem_comentario.split(";") if "mask" not in d.split(":")[0].lower()
        )
        assert not re.search(r"#[0-9A-Fa-f]{3,8}\b", pintura), f"{css_file.name} contém hex literal"
        assert not re.search(r"\b(rgb|hsl|oklch)\(", pintura), f"{css_file.name} contém função de cor literal"

