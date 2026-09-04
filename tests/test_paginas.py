"""Casca da interface: rotas, template e requisitos que não podem regredir."""

import re

import pytest
from django.template import Context
from django.template.loader import get_template
from django.urls import reverse


def test_inicio_responde(client):
    r = client.get(reverse("radar:inicio"))
    assert r.status_code == 200
    assert "Quanto se pagou de verdade" in r.content.decode()


def test_inicio_traz_atalhos_de_regiao(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert 'href="/regiao/mooca/"' in corpo
    assert "Itaim Bibi" in corpo


def test_busca_aceita_termo(client):
    r = client.get(reverse("radar:busca"), {"q": "Mooca"})
    assert r.status_code == 200
    assert "Mooca" in r.content.decode()


def test_regiao_responde(client):
    r = client.get(reverse("radar:regiao", args=["mooca"]))
    assert r.status_code == 200


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
    ],
)
def test_estatico_existe(nome):
    from django.contrib.staticfiles import finders

    assert finders.find(nome), f"não encontrado em STATICFILES_DIRS: {nome}"


def test_inicio_carrega_busca_animada(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert "busca_animada.js" in corpo


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

