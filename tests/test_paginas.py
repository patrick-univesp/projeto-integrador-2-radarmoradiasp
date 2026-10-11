"""Casca da interface: rotas, template e requisitos que não podem regredir."""

import datetime as dt
import re
from decimal import Decimal

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


def test_busca_com_cep_de_8_digitos_redireciona_pro_cep(client):
    r = client.get(reverse("radar:busca"), {"q": "01310100"})
    assert r.status_code == 302
    assert r.url == reverse("radar:cep", args=["01310100"])


def test_busca_com_cep_formatado_com_hifen_tambem_redireciona(client):
    r = client.get(reverse("radar:busca"), {"q": "01310-100"})
    assert r.status_code == 302
    assert r.url == reverse("radar:cep", args=["01310100"])


def test_busca_com_digitos_incompletos_nao_redireciona(client):
    r = client.get(reverse("radar:busca"), {"q": "013101"})
    assert r.status_code == 200


@pytest.mark.django_db
def test_regiao_responde(client):
    r = client.get(reverse("radar:regiao", args=["mooca"]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_regiao_exibe_o_nome_acentuado(client):
    """Achado de 03/09/2026: antes da #24, /regiao/butanta/ exibia "Butanta"
    (slug.title(), sem acento) em vez do nome de verdade."""
    corpo = client.get(reverse("radar:regiao", args=["butanta"])).content.decode()
    assert "Butantã" in corpo


def test_regiao_com_slug_inexistente_da_404(client):
    r = client.get(reverse("radar:regiao", args=["xpto-nao-existe"]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_regiao_marsilac_tem_pagina_mesmo_sem_transacao(client):
    """Marsilac tem zero lotes na referência geo — a página tem que existir."""
    r = client.get(reverse("radar:regiao", args=["marsilac"]))
    assert r.status_code == 200


def test_regiao_apelido_redireciona_para_o_canonico(client):
    r = client.get(reverse("radar:regiao", args=["vila-madalena"]))
    assert r.status_code == 301
    assert r.url == reverse("radar:regiao", args=["pinheiros"])


_seq_regiao = 0


def _transacao_regiao(**over):
    """Transação residencial válida na Mooca — a #24 já garante o slug."""
    global _seq_regiao
    _seq_regiao += 1
    campos = {
        "sql": f"{_seq_regiao:011d}",
        "distrito": "MOOCA",
        "distrito_slug": "mooca",
        "valor_transacao": Decimal("500000"),
        "base_calculo": Decimal("500000"),
        "data_transacao": dt.date(2026, 6, 1),
        "ano_transacao": 2026,
        "area_construida": Decimal("50"),
        "uso_grupo": "Apartamento / res. vertical",
        "rs_m2_construido": Decimal("10000"),
        "qualidade": 0,
        "natureza": "1.Compra e venda",
    }
    campos.update(over)
    from radar.models import Transacao

    return Transacao.objects.create(**campos)


@pytest.mark.django_db
def test_regiao_mostra_valor_tipico_faixa_e_confianca(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "valor típico" in corpo
    assert "(mediana)" in corpo
    assert "R$" in corpo
    assert "baseado em 30 transações" in corpo
    assert 'class="aviso"' not in corpo
    assert 'class="faixa"' in corpo


@pytest.mark.django_db
def test_regiao_explica_o_que_o_valor_tipico_e(client):
    for _ in range(27):
        _transacao_regiao(vvr_proporcional=Decimal("400000"))
    for _ in range(3):
        _transacao_regiao(valor_transacao=Decimal("300000"), vvr_proporcional=Decimal("400000"))
    _transacao_regiao(natureza="4.Arrematação (em leilão ou hasta pública)")
    corpo = " ".join(client.get(reverse("radar:regiao", args=["mooca"])).content.decode().split())
    assert "Valor de imóveis usados" in corpo
    assert "Em 10% destas vendas" in corpo
    assert "#referencia" in corpo
    assert "1 venda de leilão" in corpo
    assert "não entra no valor típico" in corpo


@pytest.mark.django_db
def test_regiao_marcador_da_faixa_usa_ponto_decimal(client):
    """LANGUAGE_CODE="pt-br" localiza número cru no template (vírgula em vez de
    ponto) — "data-pos="50,0"" viraria "left: 50,0%" via JS, CSS inválido, e o
    navegador descarta a declaração inteira. O marcador tem que sair do view já
    como string com ponto. Desde a #12, a posição vai num data-attribute (JS via
    CSSOM), não mais em <style> inline — a CSP de produção bloqueia inline."""
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert re.search(r'data-pos="\d+\.\d"', corpo)
    assert 'data-pos="50,0"' not in corpo and ',5"' not in corpo


@pytest.mark.django_db
def test_regiao_confianca_baixa_mostra_aviso(client):
    for i in range(15):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'class="aviso"' in corpo
    assert "amostra pequena" in corpo


@pytest.mark.django_db
def test_regiao_confianca_insuficiente_mostra_aviso_mais_forte(client):
    for i in range(3):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "confiança insuficiente" in corpo


@pytest.mark.django_db
def test_regiao_sem_transacao_valida_tem_estado_vazio(client):
    """Não é a página de erro — é um estado próprio, com R$ nenhum solto."""
    corpo = client.get(reverse("radar:regiao", args=["marsilac"])).content.decode()
    assert "Ainda não há vendas suficientes" in corpo
    assert "R$" not in corpo


@pytest.mark.django_db
def test_regiao_og_tags_trazem_nome_e_valor_tipico(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'property="og:title" content="Mooca ·' in corpo
    assert "vendas registradas no ITBI" in corpo


@pytest.mark.django_db
def test_regiao_og_tags_genericas_quando_nao_ha_dados(client):
    corpo = client.get(reverse("radar:regiao", args=["marsilac"])).content.decode()
    assert 'property="og:title" content="Marsilac ·' in corpo


@pytest.mark.django_db
def test_regiao_baixa_confianca_aparece_na_og_descricao(client):
    for i in range(3):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    inicio = corpo.index('property="og:description"')
    trecho_og = corpo[inicio:inicio + 400]
    assert "baixa confiança" in trecho_og


@pytest.mark.django_db
def test_regiao_url_e_a_mesma_ao_reabrir(client):
    """Critério de aceitação: a URL da região pode ser copiada e aberta de novo."""
    url = reverse("radar:regiao", args=["mooca"])
    assert client.get(url).status_code == client.get(url).status_code == 200
    assert url == "/regiao/mooca/"


@pytest.mark.django_db
def test_regiao_nao_usa_vocabulario_de_fisco(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode().lower()
    for termo in (
        "valor venal de referência", "proporção transmitida",
        "base de cálculo", "ágio", "padrão construtivo",
    ):
        assert termo not in corpo


@pytest.mark.django_db
def test_regiao_lista_transacoes_mostra_endereco_e_valores(client):
    _transacao_regiao(logradouro="Rua Taquari", numero="500", valor_transacao=Decimal("500000"))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "Rua Taquari, 500" in corpo
    assert "R$&nbsp;500.000" in corpo


@pytest.mark.django_db
def test_regiao_lista_metrica_ausente_mostra_travessao_nao_zero(client):
    _transacao_regiao(logradouro="Rua Sem Metrica", numero="1", rs_m2_construido=None)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "Rua Sem Metrica, 1" in corpo
    assert "não aplicável" in corpo
    assert "R$ 0" not in corpo


@pytest.mark.django_db
def test_regiao_lista_ordena_por_data_decrescente_por_padrao(client):
    _transacao_regiao(logradouro="Mais Antiga", numero="1", data_transacao=dt.date(2025, 1, 1), ano_transacao=2025)
    _transacao_regiao(logradouro="Mais Recente", numero="2", data_transacao=dt.date(2026, 6, 1), ano_transacao=2026)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert corpo.index("Mais Recente") < corpo.index("Mais Antiga")


@pytest.mark.django_db
def test_regiao_lista_ordena_por_valor(client):
    _transacao_regiao(logradouro="Barata", numero="1", valor_transacao=Decimal("100000"))
    _transacao_regiao(logradouro="Cara", numero="2", valor_transacao=Decimal("900000"))
    corpo = client.get(reverse("radar:regiao", args=["mooca"]) + "?ordenar=valor").content.decode()
    assert corpo.index("Cara") < corpo.index("Barata")


@pytest.mark.django_db
def test_regiao_lista_ordena_por_rs_m2(client):
    _transacao_regiao(logradouro="Barato o m2", numero="1", rs_m2_construido=Decimal("3000"))
    _transacao_regiao(logradouro="Caro o m2", numero="2", rs_m2_construido=Decimal("20000"))
    corpo = client.get(reverse("radar:regiao", args=["mooca"]) + "?ordenar=rsm2").content.decode()
    assert corpo.index("Caro o m2") < corpo.index("Barato o m2")


@pytest.mark.django_db
def test_regiao_ordenar_invalido_cai_no_padrao_sem_quebrar(client):
    _transacao_regiao()
    r = client.get(reverse("radar:regiao", args=["mooca"]) + "?ordenar=lixo")
    assert r.status_code == 200


@pytest.mark.django_db
def test_regiao_lista_pagina_e_soma_bate_com_n_transacoes(client):
    from radar.estatisticas import estatisticas_regiao
    from radar.models import Transacao
    from radar.views import TRANSACOES_POR_PAGINA

    total = TRANSACOES_POR_PAGINA + 5
    for _ in range(total):
        _transacao_regiao()

    stats = estatisticas_regiao(Transacao.objects.filter(distrito_slug="mooca"))
    assert stats["n_transacoes"] == total

    pagina_1 = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    pagina_2 = client.get(reverse("radar:regiao", args=["mooca"]) + "?pagina=2").content.decode()
    assert pagina_1.count('class="transacoes__item"') == TRANSACOES_POR_PAGINA
    assert pagina_2.count('class="transacoes__item"') == total - TRANSACOES_POR_PAGINA
    assert "página 1 de 2" in pagina_1
    assert "página 2 de 2" in pagina_2


@pytest.mark.django_db
def test_regiao_sem_transacao_na_janela_mostra_lista_vazia_propria(client):
    corpo = client.get(reverse("radar:regiao", args=["marsilac"])).content.decode()
    assert "Nenhuma transação encontrada" in corpo


@pytest.mark.django_db
def test_regiao_lista_nao_usa_tabela_com_rolagem_lateral(client):
    """Critério de aceitação da #10: em 390px cada transação vira cartão, não
    tabela. A marcação nunca deveria ter <table> para a lista."""
    _transacao_regiao()
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "<table" not in corpo


# ---- regiao/<slug>/pontos.geojson e mapa (#12) ----


@pytest.mark.django_db
def test_pontos_regiao_devolve_geojson_valido(client):
    _transacao_regiao(lat=-23.55, lon=-46.61)
    r = client.get(reverse("radar:pontos_regiao", args=["mooca"]))
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["type"] == "FeatureCollection"
    assert len(corpo["features"]) == 1
    feicao = corpo["features"][0]
    assert feicao["geometry"] == {"type": "Point", "coordinates": [-46.61, -23.55]}
    assert feicao["properties"]["endereco"]
    assert feicao["properties"]["valor_fmt"]


@pytest.mark.django_db
def test_pontos_regiao_ignora_transacao_sem_coordenada(client):
    """Critério da #12: sem coordenada não vai pro mapa, mas continua na lista
    e na estatística — aqui só garante que o endpoint do mapa filtra."""
    _transacao_regiao(lat=None, lon=None)
    from radar.estatisticas import estatisticas_regiao
    from radar.models import Transacao

    stats = estatisticas_regiao(Transacao.objects.filter(distrito_slug="mooca"))
    assert stats["n_transacoes"] == 1  # continua na estatística

    corpo = client.get(reverse("radar:pontos_regiao", args=["mooca"])).json()
    assert corpo["features"] == []


@pytest.mark.django_db
def test_pontos_regiao_marca_geo_nivel_t4_como_aproximado(client):
    _transacao_regiao(lat=-23.55, lon=-46.61, geo_nivel="T4")
    _transacao_regiao(lat=-23.56, lon=-46.62, geo_nivel="T1")
    corpo = client.get(reverse("radar:pontos_regiao", args=["mooca"])).json()
    aproximados = {f["properties"]["aproximado"] for f in corpo["features"]}
    assert aproximados == {True, False}


@pytest.mark.django_db
def test_pontos_regiao_slug_inexistente_da_404(client):
    r = client.get(reverse("radar:pontos_regiao", args=["nao-existe"]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_pontos_regiao_respeita_o_limite(client):
    from radar.views import LIMITE_PONTOS_MAPA

    for _ in range(LIMITE_PONTOS_MAPA + 5):
        _transacao_regiao(lat=-23.55, lon=-46.61)

    corpo = client.get(reverse("radar:pontos_regiao", args=["mooca"])).json()
    assert len(corpo["features"]) == LIMITE_PONTOS_MAPA


@pytest.mark.django_db
def test_regiao_com_mediana_mostra_secao_do_mapa(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'id="mapa-regiao"' in corpo
    assert 'data-slug="mooca"' in corpo
    assert 'data-distrito="MOOCA"' in corpo
    assert "js/mapa_regiao.js" in corpo


@pytest.mark.django_db
def test_regiao_sem_mediana_nao_mostra_mapa(client):
    """O mapa é subordinado ao número (#12: "entra abaixo da resposta, não no
    lugar dela") — sem mediana calculável, não tem resposta pro mapa ilustrar."""
    corpo = client.get(reverse("radar:regiao", args=["marsilac"])).content.decode()
    assert 'id="mapa-regiao"' not in corpo
    assert "js/mapa_regiao.js" not in corpo


@pytest.mark.django_db
def test_regiao_mapa_e_marcador_da_faixa_sem_script_ou_style_inline(client):
    """A CSP de produção (#11) bloqueia script e style inline sem aviso. Nem o
    marcador da faixa (#09) nem o mapa (#12) podem depender disso."""
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "<style" not in corpo
    scripts_inline = re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", corpo, re.S)
    assert not [t for t in scripts_inline if t.strip()], "há script inline no HTML"


# ---- evolução do valor típico / série mensal (#14) ----


@pytest.mark.django_db
def test_regiao_com_meses_suficientes_mostra_grafico_da_serie(client):
    _transacao_regiao(data_transacao=dt.date(2026, 5, 1), ano_transacao=2026)
    _transacao_regiao(data_transacao=dt.date(2026, 6, 1), ano_transacao=2026)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'class="serie__grafico"' in corpo
    assert ">mai/26<" in corpo
    assert ">jun<" in corpo


@pytest.mark.django_db
def test_regiao_com_um_mes_so_mostra_estado_vazio_da_serie(client):
    """Critério da #14: estado vazio quando a região não tem série
    suficiente — um mês só não é evolução."""
    for _ in range(5):
        _transacao_regiao(data_transacao=dt.date(2026, 6, 1), ano_transacao=2026)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "serie__grafico" not in corpo
    assert "Ainda não há meses suficientes" in corpo


@pytest.mark.django_db
def test_regiao_sem_mediana_nao_mostra_serie_nem_estado_vazio(client):
    corpo = client.get(reverse("radar:regiao", args=["marsilac"])).content.decode()
    assert "serie__grafico" not in corpo
    assert "Ainda não há meses suficientes" not in corpo


@pytest.mark.django_db
def test_regiao_serie_marca_mes_fraco_visualmente(client):
    _transacao_regiao(data_transacao=dt.date(2026, 5, 1), ano_transacao=2026)
    for _ in range(3):
        _transacao_regiao(data_transacao=dt.date(2026, 6, 1), ano_transacao=2026)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert "serie__ponto--fraco" in corpo


@pytest.mark.django_db
def test_regiao_grafico_da_serie_usa_ponto_decimal(client):
    """LANGUAGE_CODE="pt-br" localiza float no template (ponto -> vírgula) —
    cx="4,0" quebra o atributo SVG, mesma armadilha do pos_mediana_pct (#09)."""
    _transacao_regiao(data_transacao=dt.date(2026, 5, 1), ano_transacao=2026)
    _transacao_regiao(data_transacao=dt.date(2026, 7, 1), ano_transacao=2026)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert not re.search(r'\b(?:cx|cy|x|y)="\d+,\d+"', corpo)


@pytest.mark.django_db
def test_regiao_grafico_da_serie_exibe_valores_dos_pontos(client):
    """Garante que tanto no mobile quanto no desktop os valores dos pontos estão visíveis:
    painel de destaque, atributos data-valor, title no ponto e tabela mês a mês."""
    _transacao_regiao(data_transacao=dt.date(2026, 5, 1), ano_transacao=2026, rs_m2_construido=Decimal("10000"))
    _transacao_regiao(data_transacao=dt.date(2026, 6, 1), ano_transacao=2026, rs_m2_construido=Decimal("12000"))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'id="serie-painel"' in corpo
    assert 'id="serie-painel-valor"' in corpo
    assert "12.000/m²" in corpo
    assert 'class="serie__ponto-grupo' in corpo
    assert 'data-valor="R$&#160;10.000/m²"' in corpo or 'data-valor="R$ 10.000/m²"' in corpo
    assert "10.000/m²" in corpo
    assert 'class="serie__tabela-detalhes"' in corpo
    assert "serie_grafico.js" in corpo


@pytest.mark.django_db
def test_regiao_layout_estruturado_duas_colunas(client):
    """Garante que os blocos estruturais do layout responsivo (duas colunas no desktop) estão presentes."""
    _transacao_regiao(data_transacao=dt.date(2026, 5, 1), ano_transacao=2026)
    _transacao_regiao(data_transacao=dt.date(2026, 6, 1), ano_transacao=2026)
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'class="regiao__layout"' in corpo
    assert 'class="regiao__bloco-destaque"' in corpo
    assert 'class="regiao__bloco-serie"' in corpo
    assert 'class="regiao__bloco-mapa"' in corpo
    assert 'class="regiao__bloco-transacoes"' in corpo




# ---- /cep/<cep>/ (#28) ----


@pytest.mark.django_db
def test_cep_lista_as_transacoes_daquele_cep(client):
    _transacao_regiao(cep="01310100", logradouro="Avenida Paulista", numero="1000")
    corpo = client.get(reverse("radar:cep", args=["01310100"])).content.decode()
    assert "Avenida Paulista, 1000" in corpo
    assert "01310-100" in corpo


@pytest.mark.django_db
def test_lista_numero_ausente_mostra_sem_numero_nao_virgula_solta(client):
    """numero="" é "sem numeração" de verdade (coercao.para_numero_porta zera os
    códigos 0/99999 do cadastro) — comum em Terreno, que a lista de CEP mostra
    (não filtra por uso_grupo, diferente da lista de região). O card não pode
    sobrar com vírgula solta ("R Domingos Leme, ")."""
    _transacao_regiao(cep="01310100", logradouro="R Domingos Leme", numero="", uso_grupo="Terreno")
    corpo = client.get(reverse("radar:cep", args=["01310100"])).content.decode()
    assert "R Domingos Leme, s/n" in corpo
    assert "R Domingos Leme, </p>" not in corpo


@pytest.mark.django_db
def test_cep_nao_filtra_por_qualidade_uso_ou_ano(client):
    """Diferente da lista da região (#10, que sustenta uma mediana), a busca por
    CEP é consulta de endereço direta — mostra tudo que existe naquele CEP,
    mesmo qualidade!=0, uso não residencial ou fora da janela de anos."""
    _transacao_regiao(cep="01310100", qualidade=1)
    _transacao_regiao(cep="01310100", uso_grupo="Garagem")
    _transacao_regiao(cep="01310100", ano_transacao=1998, data_transacao=dt.date(1998, 1, 1))
    r = client.get(reverse("radar:cep", args=["01310100"]))
    assert r.content.decode().count('class="transacoes__item"') == 3


@pytest.mark.django_db
def test_cep_sem_transacao_tem_estado_vazio_proprio(client):
    corpo = client.get(reverse("radar:cep", args=["04538133"])).content.decode()
    assert "Nenhuma transação encontrada para o CEP 04538-133" in corpo
    assert "R$" not in corpo


def test_cep_com_formato_invalido_da_404(client):
    r = client.get(reverse("radar:cep", args=["abc"]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_cep_lista_pagina(client):
    from radar.views import TRANSACOES_POR_PAGINA

    total = TRANSACOES_POR_PAGINA + 3
    for _ in range(total):
        _transacao_regiao(cep="01310100")

    pagina_1 = client.get(reverse("radar:cep", args=["01310100"])).content.decode()
    pagina_2 = client.get(reverse("radar:cep", args=["01310100"]) + "?pagina=2").content.decode()
    assert pagina_1.count('class="transacoes__item"') == TRANSACOES_POR_PAGINA
    assert pagina_2.count('class="transacoes__item"') == total - TRANSACOES_POR_PAGINA


# ---- /transacao/<id>/ (#13) ----


@pytest.mark.django_db
def test_transacao_mostra_dados_basicos(client):
    t = _transacao_regiao(
        logradouro="Rua Bresser", numero="100",
        area_construida=Decimal("80"), uso_grupo="Apartamento / res. vertical",
        rs_m2_construido=Decimal("9500"),
    )
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "Rua Bresser, 100" in corpo
    assert "80" in corpo
    assert "Apartamento / res. vertical" in corpo
    assert "9.500" in corpo


@pytest.mark.django_db
def test_transacao_geo_nivel_traduzido_sem_codigo_tecnico(client):
    """Critério da #13: nenhum código técnico (T2, uso_cod) visível ao usuário."""
    t = _transacao_regiao(geo_nivel="T2")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "endereço aproximado" in corpo
    assert ">T2<" not in corpo
    assert "uso_cod" not in corpo


@pytest.mark.django_db
def test_transacao_geo_nivel_t4_marca_precisao_como_aviso(client):
    t = _transacao_regiao(geo_nivel="T4")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "cerca de 100 m" in corpo
    assert 'class="transacao__precisao aviso"' in corpo


@pytest.mark.django_db
def test_transacao_geo_nivel_t1_nao_marca_aviso(client):
    t = _transacao_regiao(geo_nivel="T1")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "lote exato" in corpo
    assert 'class="transacao__precisao aviso"' not in corpo


@pytest.mark.django_db
def test_transacao_sem_geo_nivel_mostra_precisao_padrao(client):
    t = _transacao_regiao(geo_nivel="")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "sem localização" in corpo


@pytest.mark.django_db
def test_transacao_com_coordenada_mostra_mapa(client):
    t = _transacao_regiao(geo_nivel="T2", lat=-23.55, lon=-46.63)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert 'id="mapa-transacao"' in corpo
    assert 'data-lon="-46.63' in corpo and 'data-lat="-23.55' in corpo
    assert 'data-fuzzy="0"' in corpo  # T2 é ponto, não halo
    assert "maplibre-gl.js" in corpo


@pytest.mark.django_db
def test_transacao_geo_difuso_marca_halo_no_mapa(client):
    t = _transacao_regiao(geo_nivel="T4", lat=-23.55, lon=-46.63)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert 'data-fuzzy="1"' in corpo


@pytest.mark.django_db
def test_transacao_sem_coordenada_nao_carrega_o_mapa(client):
    t = _transacao_regiao(geo_nivel="", lat=None, lon=None)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "mapa-transacao" not in corpo
    assert "maplibre-gl.js" not in corpo


@pytest.mark.django_db
def test_transacao_rs_m2_nulo_sem_area_explica_terreno(client):
    """Métrica não aplicável tem explicação, não um traço mudo (critério da #13)."""
    t = _transacao_regiao(area_construida=None, rs_m2_construido=None, uso_grupo="Terreno")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "não tem área construída registrada" in corpo


@pytest.mark.django_db
def test_transacao_rs_m2_nulo_com_area_explica_fracao(client):
    t = _transacao_regiao(area_construida=Decimal("120"), rs_m2_construido=None)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "só uma fração do imóvel" in corpo


@pytest.mark.django_db
def test_transacao_linka_de_volta_para_a_regiao(client):
    t = _transacao_regiao()
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert 'href="/regiao/mooca/"' in corpo


@pytest.mark.django_db
def test_transacao_mostra_valor_financiado_quando_presente(client):
    t = _transacao_regiao(valor_financiado=Decimal("400000"))
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "valor financiado" in corpo
    assert "400.000" in corpo


@pytest.mark.django_db
def test_transacao_mostra_vvr_quando_virou_piso_da_base(client):
    """#37: quando o VVR proporcional passa do declarado, ele virou o piso da
    base de cálculo — aí aparece ("declarou menos que a referência da Prefeitura")."""
    t = _transacao_regiao(
        valor_transacao=Decimal("375000"),
        base_calculo=Decimal("485000"),
        vvr_proporcional=Decimal("485000"),
    )
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "referência da Prefeitura" in corpo
    assert "485.000" in corpo


@pytest.mark.django_db
def test_transacao_vvr_menor_que_declarado_nao_aparece(client):
    """VVR proporcional abaixo do declarado é só a fração proporcional — número
    que confunde ao lado do valor cheio, não entra na tela."""
    t = _transacao_regiao(valor_transacao=Decimal("350000"), vvr_proporcional=Decimal("31000"))
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "referência da Prefeitura" not in corpo


@pytest.mark.django_db
def test_transacao_base_de_calculo_so_aparece_quando_veio_menor(client):
    """base < declarado = base zerada/quebrada na origem (a ressalva do bit 2).
    base == declarado (o comum) não repete o número grande."""
    igual = _transacao_regiao(valor_transacao=Decimal("500000"), base_calculo=Decimal("500000"))
    corpo = client.get(reverse("radar:transacao", args=[igual.id])).content.decode()
    assert "base de cálculo do ITBI" not in corpo

    zerada = _transacao_regiao(valor_transacao=Decimal("500000"), base_calculo=Decimal("0"))
    corpo = client.get(reverse("radar:transacao", args=[zerada.id])).content.decode()
    assert "base de cálculo do ITBI" in corpo


@pytest.mark.django_db
def test_transacao_natureza_incomum_mostra_selo_sem_prefixo_numerico(client):
    t = _transacao_regiao(natureza="4.Arrematação (em leilão ou hasta pública)")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert 'class="transacao__selo"' in corpo
    assert "Arrematação (em leilão ou hasta pública)" in corpo
    assert "4.Arrematação" not in corpo


@pytest.mark.django_db
def test_transacao_compra_e_venda_nao_polui_a_pagina(client):
    """Compra e venda é o caso comum (~95%) — não é sinal, não aparece."""
    t = _transacao_regiao(natureza="1.Compra e venda")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "Compra e venda" not in corpo
    assert "transacao__selo" not in corpo


@pytest.mark.django_db
def test_transacao_com_ressalva_mostra_selo_que_aponta_pra_caixa(client):
    """A caixa de ressalvas fica abaixo da dobra — um selo no topo avisa e
    leva até ela, sem expor a palavra "qualidade"."""
    t = _transacao_regiao(qualidade=4)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert '<a class="transacao__selo" href="#transacao-ressalvas">Dados com ressalvas</a>' in corpo
    assert 'id="transacao-ressalvas"' in corpo


@pytest.mark.django_db
def test_transacao_mostra_tipo_financiamento_quando_ha_financiamento(client):
    t = _transacao_regiao(
        valor_financiado=Decimal("400000"), tipo_financiamento="2.Minha Casa Minha Vida",
    )
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "Minha Casa Minha Vida" in corpo
    assert "2.Minha Casa Minha Vida" not in corpo


@pytest.mark.django_db
def test_transacao_sem_financiamento_nao_mostra_tipo_financiamento(client):
    t = _transacao_regiao(valor_financiado=None, tipo_financiamento="")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "<dt>financiamento</dt>" not in corpo


@pytest.mark.django_db
def test_transacao_mostra_cartorio_e_matricula(client):
    t = _transacao_regiao(cartorio="1º Cartório de Registro de Imóvel", matricula="122380")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "1º Cartório de Registro de Imóvel" in corpo
    assert "122380" in corpo


@pytest.mark.django_db
def test_transacao_cartorio_e_matricula_vazios_mostram_traco(client):
    t = _transacao_regiao(cartorio="", matricula="")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "<dt>cartório</dt><dd>—</dd>" in corpo
    assert "<dt>matrícula</dt><dd>—</dd>" in corpo


@pytest.mark.django_db
def test_transacao_sem_valor_financiado_nao_mostra_o_campo(client):
    t = _transacao_regiao(valor_financiado=None)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "valor financiado" not in corpo


@pytest.mark.django_db
def test_transacao_valor_financiado_zero_nao_mostra_o_campo(client):
    """Achado real: a planilha grava 0 (não vazio) quando não há financiamento
    — `0` formatado ainda é uma string não-vazia ("0"), então o template não
    pode confiar em `{% if valor_financiado_fmt %}` sem essa checagem na view."""
    t = _transacao_regiao(valor_financiado=Decimal("0"))
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "valor financiado" not in corpo


@pytest.mark.django_db
def test_transacao_qualidade_boa_nao_mostra_ressalvas(client):
    t = _transacao_regiao(qualidade=0)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "Ressalvas sobre esta transação" not in corpo


@pytest.mark.django_db
def test_transacao_valor_irrisorio_mostra_ressalva(client):
    t = _transacao_regiao(qualidade=4)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "Ressalvas sobre esta transação" in corpo
    assert "valor declarado é simbólico" in corpo


@pytest.mark.django_db
def test_transacao_sql_cancelado_mostra_ressalva(client):
    t = _transacao_regiao(qualidade=32, situacao_sql="Cancelado Predial")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "Ressalvas sobre esta transação" in corpo
    assert "foi cancelado ou não existe" in corpo


@pytest.mark.django_db
def test_transacao_qualidade_com_dois_bits_mostra_as_duas_ressalvas(client):
    """4 (irrisório) + 8 (financiamento incompatível) = 12."""
    t = _transacao_regiao(qualidade=12)
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "valor declarado é simbólico" in corpo
    assert "financiado pelo banco é maior" in corpo
    assert corpo.count("<li>") == 2
    assert "Mooca" in corpo


@pytest.mark.django_db
def test_transacao_sem_regiao_correspondente_nao_mostra_link_voltar(client):
    t = _transacao_regiao(distrito_slug="")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "transacao__voltar" not in corpo


@pytest.mark.django_db
def test_transacao_id_inexistente_da_404(client):
    r = client.get(reverse("radar:transacao", args=[999999]))
    assert r.status_code == 404


@pytest.mark.django_db
def test_transacao_sem_script_ou_style_inline(client):
    """Mesma regra da #11/#12: a CSP de produção bloqueia inline sem aviso."""
    t = _transacao_regiao()
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert "<style" not in corpo
    scripts_inline = re.findall(r"<script(?![^>]*\ssrc=)[^>]*>(.*?)</script>", corpo, re.S)
    assert not [s for s in scripts_inline if s.strip()], "há script inline no HTML"


@pytest.mark.django_db
def test_lista_de_transacoes_da_regiao_linka_para_o_detalhe(client):
    t = _transacao_regiao(rs_m2_construido=Decimal("9500"))
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert f'href="/transacao/{t.id}/"' in corpo


@pytest.mark.django_db
def test_pontos_regiao_inclui_id_da_transacao(client):
    t = _transacao_regiao(lat=-23.55, lon=-46.61)
    corpo = client.get(reverse("radar:pontos_regiao", args=["mooca"])).json()
    assert corpo["features"][0]["properties"]["id"] == t.id


# ---- ilustrações por uso_grupo (#18) ----


@pytest.mark.django_db
def test_lista_mostra_glifo_do_uso_grupo(client):
    _transacao_regiao(uso_grupo="Apartamento / res. vertical")
    corpo = client.get(reverse("radar:regiao", args=["mooca"])).content.decode()
    assert 'src="/static/img/uso/apartamento.svg"' in corpo
    assert 'class="transacoes__glifo"' in corpo
    assert 'alt=""' in corpo


@pytest.mark.django_db
def test_lista_uso_grupo_desconhecido_nao_mostra_glifo(client):
    """Critério da #18: uso_grupo desconhecido cai no fallback sem quebrar a
    página — aqui o fallback é não mostrar ilustração nenhuma."""
    _transacao_regiao(uso_grupo="Outros")
    r = client.get(reverse("radar:regiao", args=["mooca"]))
    assert r.status_code == 200
    assert "transacoes__glifo" not in r.content.decode()


@pytest.mark.django_db
def test_transacao_mostra_ilustracao_isometrica_do_uso(client):
    t = _transacao_regiao(uso_grupo="Casa / residência horizontal")
    corpo = client.get(reverse("radar:transacao", args=[t.id])).content.decode()
    assert 'src="/static/img/uso/casa-96.webp"' in corpo
    assert 'class="transacao__ilustracao"' in corpo


@pytest.mark.django_db
def test_transacao_sem_ilustracao_para_uso_desconhecido(client):
    t = _transacao_regiao(uso_grupo="")
    r = client.get(reverse("radar:transacao", args=[t.id]))
    assert r.status_code == 200
    assert "transacao__ilustracao" not in r.content.decode()


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


def test_500_nao_usa_estilo_inline():
    """A CSP de produção (style-src 'self') bloqueia <style> e style="": a página
    de erro aparecia sem formatação. O CSS vem de arquivo, por caminho fixo."""
    from django.contrib.staticfiles import finders

    saida = get_template("500.html").template.render(Context({}))
    assert "<style" not in saida
    assert "style=" not in saida
    for href in re.findall(r'href="/static/([^"]+\.css)"', saida):
        assert finders.find(href), f"500.html aponta para um CSS que não existe: {href}"
    assert "/static/css/erro-500.css" in saida


@pytest.mark.parametrize(
    "nome",
    [
        "css/tokens.css",
        "css/base.css",
        "css/transicao.css",
        "css/erro.css",
        "css/erro-500.css",
        "css/regiao.css",
        "js/busca_animada.js",
        "js/contador_transacoes.js",
        "js/autocomplete.js",
        "css/transacao.css",
        "css/mapa.css",
    ],
)
def test_estatico_existe(nome):
    from django.contrib.staticfiles import finders

    assert finders.find(nome), f"não encontrado em STATICFILES_DIRS: {nome}"


def test_todas_as_ilustracoes_de_uso_existem():
    """#18: os 11 slugs de SLUG_ILUSTRACAO_USO têm glifo SVG (lista) e WebP
    96/192/384 (detalhe/mapa/cartão) de verdade em static/, sem CDN."""
    from django.contrib.staticfiles import finders

    from radar.views import SLUG_ILUSTRACAO_USO

    faltando = []
    for slug in SLUG_ILUSTRACAO_USO.values():
        arquivos = [f"img/uso/{slug}.svg"] + [f"img/uso/{slug}-{t}.webp" for t in (96, 192, 384)]
        faltando += [a for a in arquivos if not finders.find(a)]
    assert not faltando, f"faltando em STATICFILES_DIRS: {faltando}"


@pytest.mark.django_db
def test_inicio_carrega_busca_animada(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert "busca_animada.js" in corpo


@pytest.mark.django_db
def test_inicio_carrega_contador_de_transacoes(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert '<script src="/static/js/contador_transacoes.js" defer></script>' in corpo


@pytest.mark.django_db
def test_inicio_carrega_autocomplete(client):
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert '<script src="/static/js/autocomplete.js" defer></script>' in corpo


@pytest.mark.django_db
def test_campo_de_busca_e_um_combobox_acessivel(client):
    """Sem isso o autocomplete é invisível pra leitor de tela — a lista de
    sugestões existe no DOM, mas nada anuncia que ela existe."""
    corpo = client.get(reverse("radar:inicio")).content.decode()
    assert 'role="combobox"' in corpo
    assert 'aria-controls="sugestoes-lista"' in corpo
    assert 'id="sugestoes-lista"' in corpo
    assert 'role="listbox"' in corpo


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


def test_t_numero_encolhe_em_telas_estreitas():
    """Achado real ao medir com a base inteira: "R$ 6.705,43/m²" (uma mediana
    comum) e valores de transação de verdade estouravam a tela a 320-374px com
    --t-numero fixo em 3.25rem — a amostra de dev usada até então tinha poucos
    dígitos e escondia o problema."""
    from pathlib import Path

    tokens = Path("static/css/tokens.css").read_text()
    inicio = tokens.index("@media (max-width:")
    bloco = tokens[inicio:tokens.index("}", tokens.index("}", inicio) + 1)]
    assert "--t-numero:" in bloco


def test_numeros_grandes_tem_rede_de_seguranca_contra_estouro():
    """Mesmo com --t-numero responsivo, um valor fora da curva (ex.: transação
    de R$ 894 milhões, real na base) ainda pode não caber — sem isto, a página
    ganha rolagem horizontal e esconde conteúdo em vez de quebrar a linha."""
    from pathlib import Path

    for arquivo, classe in (
        ("static/css/regiao.css", ".regiao__numero"),
        ("static/css/transacao.css", ".transacao__valor"),
    ):
        css = Path(arquivo).read_text()
        inicio = css.index(classe)
        bloco = css[inicio:css.index("}", inicio)]
        assert "overflow-wrap" in bloco, f"{arquivo}: {classe} sem overflow-wrap"


# ---- /comparar/ (comparação entre regiões) ----


@pytest.mark.django_db
def test_comparar_mostra_as_duas_regioes_e_a_diferenca(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    for i in range(30):
        _transacao_regiao(
            distrito="PINHEIROS", distrito_slug="pinheiros",
            rs_m2_construido=Decimal(10000 + i * 100),
        )
    corpo = client.get(reverse("radar:comparar"), {"a": "mooca", "b": "pinheiros"}).content.decode()
    assert "Mooca" in corpo
    assert "Pinheiros" in corpo
    assert "mais caro" in corpo
    assert 'class="aviso"' not in corpo


@pytest.mark.django_db
def test_comparar_confianca_baixa_em_um_lado_mostra_aviso(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    for i in range(3):
        _transacao_regiao(
            distrito="PINHEIROS", distrito_slug="pinheiros",
            rs_m2_construido=Decimal(10000 + i * 100),
        )
    corpo = client.get(reverse("radar:comparar"), {"a": "mooca", "b": "pinheiros"}).content.decode()
    assert 'class="aviso"' in corpo
    assert "Compare com cautela" in corpo


@pytest.mark.django_db
def test_comparar_regiao_consigo_mesma_nao_quebra(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    r = client.get(reverse("radar:comparar"), {"a": "mooca", "b": "mooca"})
    assert r.status_code == 200
    assert "o mesmo valor típico" in r.content.decode()


@pytest.mark.django_db
def test_comparar_url_com_a_e_b_reabre_a_mesma_comparacao(client):
    """Critério de aceitação: a URL da comparação pode ser copiada e aberta de novo."""
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    for i in range(30):
        _transacao_regiao(
            distrito="PINHEIROS", distrito_slug="pinheiros",
            rs_m2_construido=Decimal(10000 + i * 100),
        )
    url = "/comparar/?a=mooca&b=pinheiros"
    corpo = client.get(url).content.decode()
    assert "Mooca" in corpo and "Pinheiros" in corpo
    assert client.get(url).content.decode() == corpo


@pytest.mark.django_db
def test_comparar_sem_parametros_mostra_selecao(client):
    r = client.get(reverse("radar:comparar"))
    assert r.status_code == 200
    corpo = r.content.decode()
    assert 'id="q-a"' in corpo
    assert 'id="q-b"' in corpo
    assert "<h2" not in corpo


@pytest.mark.django_db
def test_comparar_so_um_lado_preenchido_mostra_o_outro_vazio(client):
    """Ponto de entrada da página de região: o link "Comparar com outra
    região" só manda `a`."""
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    r = client.get(reverse("radar:comparar"), {"a": "mooca"})
    assert r.status_code == 200
    corpo = r.content.decode()
    assert "Mooca" in corpo
    assert corpo.count("<h2") == 1


def test_comparar_slug_inexistente_da_404(client):
    r = client.get(reverse("radar:comparar"), {"a": "mooca", "b": "xpto-nao-existe"})
    assert r.status_code == 404


def test_comparar_apelido_redireciona_para_o_canonico(client):
    r = client.get(reverse("radar:comparar"), {"a": "vila-madalena", "b": "mooca"})
    assert r.status_code == 301
    assert r.url == "/comparar/?a=pinheiros&b=mooca"


@pytest.mark.django_db
def test_comparar_uma_regiao_sem_dados_mostra_estado_vazio_so_naquele_lado(client):
    for i in range(30):
        _transacao_regiao(rs_m2_construido=Decimal(8000 + i * 100))
    corpo = client.get(reverse("radar:comparar"), {"a": "mooca", "b": "marsilac"}).content.decode()
    assert "Ainda não há vendas suficientes" in corpo
    assert "Não há dados suficientes para calcular a diferença" in corpo

