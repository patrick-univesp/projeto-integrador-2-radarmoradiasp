import re
from decimal import Decimal

from django.core.paginator import Paginator
from django.http import Http404, HttpResponsePermanentRedirect, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from radar.buscas import sugerir_regioes
from radar.estatisticas import estatisticas_regiao, serie_mensal, transacoes_da_regiao
from radar.models import Transacao
from radar.regioes import APELIDOS, POR_SLUG

# Slugs do registro canônico — nunca string solta, pra nenhum link da home
# apontar pra um slug que a página da região não aceite.
REGIOES_DESTAQUE_SLUGS = ("mooca", "itaim-bibi", "tatuape", "santana", "vila-mariana", "butanta")

# Uma navegação por requisição — mais apertado que faria sentido pro autocomplete
# (#06, que dispara várias por busca). Issue #07.
TAXA_CONSULTA = "30/m"

# O autocomplete dispara mais de uma requisição por busca digitada (mesmo com
# debounce no cliente) — mais generoso que TAXA_CONSULTA de propósito.
TAXA_SUGESTOES = "60/m"

TRANSACOES_POR_PAGINA = 20
ORDENACOES_TRANSACOES = {
    "data": "-data_transacao",
    "valor": "-valor_transacao",
    "rsm2": "-rs_m2_construido",
}

CEP_REGEX = re.compile(r"^\d{8}$")

# Sem teto, um distrito grande manda todos os pontos de uma vez pro navegador
# desenhar. 500 é generoso (a base tem ~1.400 transações/distrito no total,
# sem filtro nenhum); corte por data decrescente, mesmo critério da lista.
LIMITE_PONTOS_MAPA = 500

# T4 = centroide da quadra fiscal inteira, ~100 m — a única faixa que o RF6
# pede pra marcar como aproximada; T1–T3 já são específicas de lote/endereço.
GEO_NIVEL_APROXIMADO = "T4"

# Tradução de geo_nivel (referencia-geo.md) pra linguagem comum — #13: nenhum
# código técnico ("T2") visível ao usuário.
PRECISAO_GEO = {
    "T1": ("lote exato", "A coordenada aponta para o lote exato deste imóvel."),
    "T2": (
        "endereço aproximado",
        "A coordenada resolve o endereço dentro da quadra — comum em apartamentos, "
        "cujo lote individual não existe no cadastro de lotes.",
    ),
    "T3": (
        "vizinhança",
        "A coordenada usa o número de porta mais próximo no mesmo logradouro.",
    ),
    "T4": (
        "aproximado, cerca de 100 m",
        "A coordenada é o centroide da quadra fiscal inteira, sem precisão de lote.",
    ),
}
PRECISAO_GEO_PADRAO = (
    "sem localização",
    "Esta transação não tem coordenada — não é possível mostrá-la no mapa.",
)

# Tradução de qualidade (bitmask, radar/carga/mineracao.py::qualidade) pra
# linguagem comum — mesmo raciocínio do PRECISAO_GEO: nenhum código técnico
# chega ao template. Uma transação pode acumular mais de uma ressalva.
QUALIDADE_RESSALVAS = {
    1: "As colunas desta linha vieram deslocadas na planilha original — algum "
       "campo pode estar com o valor errado.",
    2: "A base de cálculo do imposto não bate com o valor declarado nem com o "
       "valor de referência da Prefeitura.",
    4: "O valor declarado é simbólico (abaixo de R$ 1.000) — não representa o "
       "preço real do imóvel.",
    8: "O valor financiado pelo banco é maior que o valor declarado da "
       "transação — o valor declarado provavelmente não é o preço real do negócio.",
    16: "A data da transação está fora da faixa plausível — pode ser erro de "
        "digitação na planilha original.",
}


def _ressalvas_qualidade(qualidade):
    return [msg for bit, msg in QUALIDADE_RESSALVAS.items() if qualidade & bit]

# Geometria do SVG da série mensal (#14) — viewBox, não pixel real; o CSS
# escala. Largura da faixa de plotagem = LARGURA_SERIE - 2*MARGEM_ESQ_SERIE.
LARGURA_SERIE = 320
ALTURA_PLOT_SERIE = 84
ALTURA_ROTULOS_SERIE = 28
MARGEM_ESQ_SERIE = 4
MARGEM_TOPO_SERIE = 8
# Menos de 2 meses com mediana não é "evolução" — é o estado vazio da #14.
SERIE_MIN_PONTOS = 2

# uso_grupo -> slug do glifo/ilustração (#18). Slugs batem 1:1 com os 11
# uso_grupo de radar/carga/mineracao.py::_GRUPOS_USO. Grupo desconhecido ou
# vazio (GRUPO_OUTROS — uso_cod 73/91, fora da Tabela de USOS) fica sem
# entrada: o fallback explícito é não mostrar ilustração nenhuma, não uma
# peça genérica que não existe.
SLUG_ILUSTRACAO_USO = {
    "Apartamento / res. vertical": "apartamento",
    "Terreno": "terreno",
    "Casa / residência horizontal": "casa",
    "Loja / comércio": "loja",
    "Indústria / armazém": "industria",
    "Garagem": "garagem",
    "Escritório / consultório": "escritorio",
    "Institucional": "institucional",
    "Oficina / serviços": "oficina",
    "Hotel / saúde / especial": "hotel-saude",
    "Depósito": "deposito",
}


def _glifo_uso(uso_grupo):
    slug = SLUG_ILUSTRACAO_USO.get(uso_grupo)
    return f"img/uso/{slug}.svg" if slug else None

_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _rotular_periodo(ano_ini, mes_ini, ano_fim, mes_fim):
    """"janeiro de 2026" / "janeiro a julho de 2026" / "novembro de 2025 a março de 2026"."""
    if ano_ini == ano_fim and mes_ini == mes_fim:
        return f"{_MESES[mes_ini - 1]} de {ano_ini}"
    if ano_ini == ano_fim:
        return f"{_MESES[mes_ini - 1]} a {_MESES[mes_fim - 1]} de {ano_fim}"
    return f"{_MESES[mes_ini - 1]} de {ano_ini} a {_MESES[mes_fim - 1]} de {ano_fim}"


def _resumo_da_base():
    """Total de transações e período coberto (pelo mês da guia), lidos do banco.

    Ficam vazios se a carga não rodou neste ambiente — a home renderiza igual.
    """
    total = Transacao.objects.count()
    guias = (
        Transacao.objects.filter(ano_guia__isnull=False, mes_guia__isnull=False)
        .order_by("ano_guia", "mes_guia")
        .values_list("ano_guia", "mes_guia")
    )
    primeiro, ultimo = guias.first(), guias.last()
    periodo = _rotular_periodo(primeiro[0], primeiro[1], ultimo[0], ultimo[1]) if primeiro else ""

    return {
        "n_vendas": total,
        "total_vendas": f"{total:,}".replace(",", "."),
        "periodo": periodo,
    }


def _formatar_rs(valor):
    """"8.465" ou "8.465,50" — separador de milhar por ponto, duas casas só quando
    o valor tem centavos de verdade (issue #09: "duas casas quando couber")."""
    if valor is None:
        return None
    valor = Decimal(valor)
    negativo = valor < 0
    valor = abs(valor)
    inteiro = int(valor)
    texto = f"{inteiro:,}".replace(",", ".")
    centavos = valor - inteiro
    if centavos:
        texto = f"{texto},{int((centavos * 100).to_integral_value()):02d}"
    return f"-{texto}" if negativo else texto


def _endereco(t):
    # numero="" é "sem numeração" de verdade (coercao.para_numero_porta zera os
    # códigos 0/99999 do cadastro, comum em Terreno) — "s/n", não vírgula solta.
    return f"{t.logradouro}, {t.numero}" if t.numero else f"{t.logradouro}, s/n"


def _sem_prefixo_numerico(texto):
    """``"33.Demais atos onerosos translativos"`` → ``"Demais atos onerosos
    translativos"`` — o código da planilha nunca chega ao template."""
    m = re.match(r"^\s*\d+\s*\.\s*(.+)$", texto or "")
    return m.group(1) if m else texto


def _grafico_serie(serie):
    """Geometria pronta pro SVG de regiao.html (#14): coordenadas em viewBox,
    segmentos de polyline que já pulam buraco (mês sem mediana não vira reta
    até o próximo ponto real) e os dois rótulos do eixo Y. ``None`` quando a
    região não tem meses suficientes pra uma linha de verdade (estado vazio)."""
    reais = [p for p in serie if p["mediana_rs_m2"] is not None]
    if len(reais) < SERIE_MIN_PONTOS:
        return None

    valores = [p["mediana_rs_m2"] for p in reais]
    v_min, v_max = min(valores), max(valores)
    if v_min == v_max:
        folga = (v_min * Decimal("0.1")) or Decimal("1")
        v_min, v_max = v_min - folga, v_max + folga

    n = len(serie)
    passo_x = (LARGURA_SERIE - 2 * MARGEM_ESQ_SERIE) / max(n - 1, 1)

    def _y(valor):
        proporcao = float((valor - v_min) / (v_max - v_min))
        return MARGEM_TOPO_SERIE + ALTURA_PLOT_SERIE * (1 - proporcao)

    # String, não número: LANGUAGE_CODE="pt-br" localiza float no template
    # (ponto -> vírgula) e "cx=4,0" quebra o atributo SVG (mesma armadilha do
    # pos_mediana_pct da #09).
    def _num(valor):
        return f"{valor:g}"

    pontos = []
    ano_anterior = None
    for i, p in enumerate(serie):
        rotulo = _MESES[p["mes"] - 1][:3]
        if p["ano"] != ano_anterior:
            rotulo = f"{rotulo}/{p['ano'] % 100:02d}"
        ano_anterior = p["ano"]
        # O rótulo do primeiro/último mês fica centralizado no x=0/x=largura
        # do gráfico — texto ancorado ao centro vazaria pra fora do viewBox e
        # seria cortado. Só esses dois crescem pra dentro.
        if i == 0:
            ancora = "start"
        elif i == n - 1:
            ancora = "end"
        else:
            ancora = "middle"
        pontos.append({
            "x": _num(MARGEM_ESQ_SERIE + i * passo_x),
            "y": _num(_y(p["mediana_rs_m2"])) if p["mediana_rs_m2"] is not None else None,
            "mes_rotulo": rotulo,
            "ancora": ancora,
            "n": p["n_transacoes"],
            "fraco": p["fraco"],
            "tem_dado": p["mediana_rs_m2"] is not None,
            "valor_fmt": _formatar_rs(p["mediana_rs_m2"]) if p["mediana_rs_m2"] is not None else None,
        })

    pontos_com_dado = [pt for pt in pontos if pt["tem_dado"]]
    ultimo_ponto = pontos_com_dado[-1] if pontos_com_dado else None
    for pt in pontos:
        pt["ativo"] = (pt is ultimo_ponto)

    segmentos = []
    atual = []
    for pt in pontos:
        if pt["tem_dado"]:
            atual.append(f"{pt['x']},{pt['y']}")
        else:
            if len(atual) > 1:
                segmentos.append(" ".join(atual))
            atual = []
    if len(atual) > 1:
        segmentos.append(" ".join(atual))

    y_base = MARGEM_TOPO_SERIE + ALTURA_PLOT_SERIE
    return {
        "largura": _num(LARGURA_SERIE),
        "altura": _num(y_base + ALTURA_ROTULOS_SERIE),
        "pontos": pontos,
        "segmentos": segmentos,
        "y_topo": _num(MARGEM_TOPO_SERIE),
        "y_base": _num(y_base),
        "y_rotulos": _num(y_base + 14),
        "rotulo_topo": _formatar_rs(v_max),
        "rotulo_base": _formatar_rs(v_min),
        "ultimo_ponto": ultimo_ponto,
    }


def _transacoes_formatadas(pagina):
    """Uma página do Paginator -> dicts prontos para o partial
    _lista_transacoes.html (mesmo formato para regiao() e cep())."""
    return [
        {
            "id": t.id,
            "sql": t.sql,
            "endereco": _endereco(t),
            "area_construida": t.area_construida,
            "uso_grupo": t.uso_grupo,
            "data": t.data_transacao,
            "valor_fmt": _formatar_rs(t.valor_transacao),
            "rs_m2_fmt": _formatar_rs(t.rs_m2_construido),
            "glifo_uso": _glifo_uso(t.uso_grupo),
        }
        for t in pagina.object_list
    ]


def inicio(request):
    return render(
        request,
        "radar/inicio.html",
        {
            "regioes_destaque": [POR_SLUG[s] for s in REGIOES_DESTAQUE_SLUGS],
            **_resumo_da_base(),
        },
    )


def busca(request):
    termo = (request.GET.get("q") or "").strip()
    # Nenhuma rua de São Paulo começa com dígito — o campo já aplica essa
    # máscara no cliente (static/js/autocomplete.js), mas resolve aqui de
    # novo pra funcionar sem JS e em quem colar a URL direto.
    if termo and termo[0].isdigit():
        digitos = re.sub(r"\D", "", termo)
        if CEP_REGEX.fullmatch(digitos):
            return HttpResponseRedirect(reverse("radar:cep", args=[digitos]))
    return render(
        request,
        "radar/em_breve.html",
        {
            "titulo": f"Busca por “{termo}”" if termo else "Busca",
            "mensagem": (
                "A busca ainda não está ligada: falta o autocomplete que resolve um "
                "termo digitado para uma região. Esta tela existe para o caminho da "
                "interface ficar completo enquanto o restante é construído."
            ),
        },
    )


def _contexto_destaque(stats):
    """Os dados que ``_bloco_destaque.html`` precisa pra desenhar o número
    típico, a faixa p25↔p75 e o aviso de confiança — reusado tanto pela página
    da região quanto pela comparação entre regiões."""
    mediana = stats["mediana_rs_m2"]
    p25, p75 = stats["p25_rs_m2"], stats["p75_rs_m2"]
    pos_mediana_pct = None
    if mediana is not None and p75 != p25:
        # String, não número: LANGUAGE_CODE="pt-br" localiza um float no template
        # (ponto → vírgula), e "left: 50,0%" é CSS inválido.
        pos_mediana_pct = f"{float((mediana - p25) / (p75 - p25)) * 100:.1f}"
    elif mediana is not None:
        pos_mediana_pct = "50.0"

    return {
        "stats": stats,
        "mediana_fmt": _formatar_rs(mediana),
        "p25_fmt": _formatar_rs(p25),
        "p75_fmt": _formatar_rs(p75),
        "pos_mediana_pct": pos_mediana_pct,
        "periodo": (
            _rotular_periodo(
                stats["periodo_inicio"].year, stats["periodo_inicio"].month,
                stats["periodo_fim"].year, stats["periodo_fim"].month,
            )
            if stats["periodo_inicio"]
            else ""
        ),
    }


@ratelimit(key="ip", rate=TAXA_CONSULTA, block=False)
def regiao(request, slug):
    if request.limited:
        return render(request, "429.html", status=429)
    if slug in APELIDOS:
        return HttpResponsePermanentRedirect(reverse("radar:regiao", args=[APELIDOS[slug]]))
    r = POR_SLUG.get(slug)
    if r is None:
        raise Http404(f"região {slug!r} não existe")

    stats = estatisticas_regiao(Transacao.objects.filter(distrito_slug=slug))
    destaque = _contexto_destaque(stats)

    serie, _ = serie_mensal(Transacao.objects.filter(distrito_slug=slug), ano_min=stats["ano_min"])
    grafico_serie = _grafico_serie(serie)

    # Mesmo ano_min da mediana acima: a soma dos itens paginados bate com
    # stats["n_transacoes"] porque é o mesmo filtro, só reordenado.
    ordenar = request.GET.get("ordenar", "data")
    if ordenar not in ORDENACOES_TRANSACOES:
        ordenar = "data"
    lista, _ = transacoes_da_regiao(Transacao.objects.filter(distrito_slug=slug), ano_min=stats["ano_min"])
    lista = lista.order_by(ORDENACOES_TRANSACOES[ordenar])
    pagina = Paginator(lista, TRANSACOES_POR_PAGINA).get_page(request.GET.get("pagina"))

    return render(
        request,
        "radar/regiao.html",
        {
            "regiao": r,
            **destaque,
            "grafico_serie": grafico_serie,
            "transacoes": _transacoes_formatadas(pagina),
            "pagina": pagina,
            "ordenar": ordenar,
            "transacoes_vazio_texto": f"Nenhuma transação encontrada com estes critérios em {r.nome}.",
        },
    )


def _stats_alinhadas(slug_a, slug_b):
    """Estatísticas das duas regiões na **mesma janela de anos** — comparar a
    mediana de um período com a de outro período diferente seria enganoso.
    Usa a janela mais antiga das duas (ver ``estatisticas_regiao``, que já
    antecipa esse uso)."""
    qs_a = Transacao.objects.filter(distrito_slug=slug_a)
    qs_b = Transacao.objects.filter(distrito_slug=slug_b)

    anos = [
        a
        for a in (estatisticas_regiao(qs_a)["ano_min"], estatisticas_regiao(qs_b)["ano_min"])
        if a is not None
    ]
    ano_min_comum = min(anos) if anos else None

    return estatisticas_regiao(qs_a, ano_min=ano_min_comum), estatisticas_regiao(qs_b, ano_min=ano_min_comum)


def _diferenca(stats_a, stats_b):
    m_a, m_b = stats_a["mediana_rs_m2"], stats_b["mediana_rs_m2"]
    if m_a is None or m_b is None:
        return None
    diff = m_b - m_a
    pct = float(abs(diff) / m_a * 100) if m_a else None
    return {
        "abs_fmt": _formatar_rs(abs(diff)),
        "pct_fmt": f"{pct:.1f}" if pct is not None else None,
        "b_mais_caro": diff > 0,
        "igual": diff == 0,
    }


@ratelimit(key="ip", rate=TAXA_CONSULTA, block=False)
def comparar(request):
    """Comparação entre duas regiões — RF7: o Q1 (onde mora) e o Q3 (onde
    moraria) da pesquisa com a comunidade, lado a lado."""
    if request.limited:
        return render(request, "429.html", status=429)

    slug_a = request.GET.get("a") or ""
    slug_b = request.GET.get("b") or ""
    canonico_a, canonico_b = APELIDOS.get(slug_a, slug_a), APELIDOS.get(slug_b, slug_b)
    if canonico_a != slug_a or canonico_b != slug_b:
        return HttpResponsePermanentRedirect(f"{reverse('radar:comparar')}?a={canonico_a}&b={canonico_b}")

    regiao_a = POR_SLUG.get(slug_a) if slug_a else None
    regiao_b = POR_SLUG.get(slug_b) if slug_b else None
    if (slug_a and regiao_a is None) or (slug_b and regiao_b is None):
        raise Http404("região inexistente")

    if regiao_a is None or regiao_b is None:
        # Falta escolher um dos dois lados — não é erro, é o ponto de entrada
        # da página (ex.: link "Comparar com outra região" da página de região, só com `a`).
        return render(request, "radar/comparar.html", {"regiao_a": regiao_a, "regiao_b": regiao_b})

    stats_a, stats_b = _stats_alinhadas(slug_a, slug_b)
    diferenca = _diferenca(stats_a, stats_b)

    return render(
        request,
        "radar/comparar.html",
        {
            "regiao_a": regiao_a,
            "regiao_b": regiao_b,
            "contexto_a": _contexto_destaque(stats_a),
            "contexto_b": _contexto_destaque(stats_b),
            "diferenca": diferenca,
            "confianca_baixa": stats_a["confianca"] != "ok" or stats_b["confianca"] != "ok",
        },
    )


@ratelimit(key="ip", rate=TAXA_CONSULTA, block=False)
def transacao(request, id):
    """Detalhe de uma transação (#13) — RF3: o usuário clicou num ponto do
    mapa ou num item da lista e quer ver aquele negócio, em linguagem comum."""
    if request.limited:
        return render(request, "429.html", status=429)
    t = get_object_or_404(Transacao, pk=id)

    rs_m2_fmt = _formatar_rs(t.rs_m2_construido)
    rs_m2_explicacao = None
    if rs_m2_fmt is None:
        rs_m2_explicacao = (
            "Este imóvel não tem área construída registrada (é um terreno, ou a guia "
            "não trouxe essa informação) — R$/m² não se aplica."
            if not t.area_construida
            else "A guia registra só uma fração do imóvel (ex.: transferência de "
            "cota-parte) — o valor não representa o imóvel inteiro, então R$/m² não "
            "é calculado."
        )

    precisao_rotulo, precisao_descricao = PRECISAO_GEO.get(t.geo_nivel, PRECISAO_GEO_PADRAO)
    slug_uso = SLUG_ILUSTRACAO_USO.get(t.uso_grupo)

    return render(
        request,
        "radar/transacao.html",
        {
            "t": t,
            "endereco": _endereco(t),
            "ilustracao_uso": f"img/uso/{slug_uso}-96.webp" if slug_uso else None,
            "valor_fmt": _formatar_rs(t.valor_transacao),
            # `0` na planilha é "sem financiamento", não "financiado R$ 0" —
            # mesmo tratamento que financiamento_incompativel já dá na carga.
            "valor_financiado_fmt": _formatar_rs(t.valor_financiado) if t.valor_financiado else None,
            "natureza_fmt": _sem_prefixo_numerico(t.natureza),
            "tipo_financiamento_fmt": _sem_prefixo_numerico(t.tipo_financiamento),
            "rs_m2_fmt": rs_m2_fmt,
            "rs_m2_explicacao": rs_m2_explicacao,
            "ressalvas_qualidade": _ressalvas_qualidade(t.qualidade),
            "precisao_rotulo": precisao_rotulo,
            "precisao_descricao": precisao_descricao,
            "precisao_aproximada": t.geo_nivel == GEO_NIVEL_APROXIMADO,
            "regiao": POR_SLUG.get(t.distrito_slug),
        },
    )


@ratelimit(key="ip", rate=TAXA_CONSULTA, block=False)
def pontos_regiao(request, slug):
    """GeoJSON dos pontos da região pro mapa (#12). Mesmo filtro de base da
    lista/mediana (transacoes_da_regiao) — o mapa ilustra o mesmo número, não
    uma amostra à parte —, mais o corte que só o mapa precisa: só quem tem
    coordenada entra (#12: "sem coordenada não vai pro mapa mas continua na
    lista e na estatística")."""
    if request.limited:
        return JsonResponse({"type": "FeatureCollection", "features": []}, status=429)
    if POR_SLUG.get(slug) is None:
        raise Http404(f"região {slug!r} não existe")

    lista, _ = transacoes_da_regiao(Transacao.objects.filter(distrito_slug=slug))
    lista = lista.exclude(lat__isnull=True).exclude(lon__isnull=True).order_by("-data_transacao")
    lista = lista[:LIMITE_PONTOS_MAPA]

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [t.lon, t.lat]},
            "properties": {
                "id": t.id,
                "endereco": _endereco(t),
                "valor_fmt": _formatar_rs(t.valor_transacao),
                "rs_m2_fmt": _formatar_rs(t.rs_m2_construido),
                "data": t.data_transacao.strftime("%d/%m/%Y") if t.data_transacao else None,
                "aproximado": t.geo_nivel == GEO_NIVEL_APROXIMADO,
            },
        }
        for t in lista
    ]
    return JsonResponse({"type": "FeatureCollection", "features": features})


@ratelimit(key="ip", rate=TAXA_CONSULTA, block=False)
def cep(request, cep):
    if request.limited:
        return render(request, "429.html", status=429)
    if not CEP_REGEX.fullmatch(cep):
        raise Http404(f"CEP {cep!r} inválido")

    cep_fmt = f"{cep[:5]}-{cep[5:]}"
    lista = Transacao.objects.filter(cep=cep).order_by("-data_transacao")
    pagina = Paginator(lista, TRANSACOES_POR_PAGINA).get_page(request.GET.get("pagina"))

    return render(
        request,
        "radar/cep.html",
        {
            "cep": cep,
            "cep_fmt": cep_fmt,
            "transacoes": _transacoes_formatadas(pagina),
            "pagina": pagina,
            "transacoes_vazio_texto": f"Nenhuma transação encontrada para o CEP {cep_fmt}.",
        },
    )


@ratelimit(key="ip", rate=TAXA_SUGESTOES, block=False)
def sugestoes(request):
    if request.limited:
        return JsonResponse({"sugestoes": []}, status=429)
    termo = request.GET.get("q", "")
    return JsonResponse({"sugestoes": sugerir_regioes(termo)})


def entrar(request):
    return render(request, "404.html", status=404)
