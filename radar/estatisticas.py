"""Valor típico por região: a mediana de R$/m² que é o produto do PI2.

``estatisticas_regiao`` é pura sobre um queryset já filtrado por região (o chamador
decide *onde*; esta função decide *quais transações contam* e *como resumi-las*).
Detalhe e critério de aceitação: ``docs/local/issues/08-servico-estatisticas.md``.
"""

import datetime as dt
import statistics
from collections import defaultdict

from django.db.models import F, Max, Q

# "Radar da Moradia": a mediana é de imóvel residencial. Sem este filtro, garagem,
# loja e indústria entrariam misturadas com casa e apartamento — achado em
# 04/09/2026, ver referencia-itbi.md §2.4.
USO_GRUPO_RESIDENCIAL = ("Casa / residência horizontal", "Apartamento / res. vertical")

# Janela padrão da mediana: 12 meses a partir da transação mais recente **da
# região** (não do calendário — área que ficou muda não some). Se 12 meses não
# reúnem nem LIMIAR_JANELA_AMPLA vendas, alarga pra 24 — região pequena não fica
# sem número por falta de volume recente. A granularidade é o mês (o corte é o
# dia 1); antes era ano-calendário, o que dava de 12 a 24 meses conforme a data.
JANELA_MESES_PADRAO = 12
JANELA_MESES_AMPLA = 24
LIMIAR_JANELA_AMPLA = 30

# Só negócio de mercado entra na mediana: compra e venda e cessão de direitos de
# compra. Leilão, retomada pelo banco, dação, permuta, integralização de capital e
# afins têm preço que não é o de uma venda comum (o leilão fecha ~45% abaixo).
# Essas linhas continuam na lista e no detalhe; só saem do cálculo. Lista de
# inclusão de propósito: um código novo na planilha fica fora até alguém olhar.
NATUREZAS_DE_MERCADO = (1, 2, 26, 35)

LIMITE_CONFIANCA_INSUFICIENTE = 10
LIMITE_CONFIANCA_BAIXA = 30

CONFIANCA_INSUFICIENTE = "insuficiente"
CONFIANCA_BAIXA = "baixa"
CONFIANCA_OK = "ok"

# Os limiares de confiança acima são calibrados pra n_com_metrica de uma
# região inteira (~2 anos somados). Um mês isolado nunca chega a 10 —
# aplicar o mesmo limiar aqui marcaria a série inteira como fraca sempre.
# Com menos de 10 vendas, a mediana do mês oscila mais que a tendência que a
# série quer mostrar.
LIMIAR_MES_FRACO = 10

# A série não olha pra trás mais que isso a partir do mês mais recente com
# dado na região. A janela da mediana pode chegar a 24 meses (JANELA_MESES_AMPLA,
# região pequena) — se a região só tem transação no começo e no fim dela, a
# série vira 2 pontos reais separados por ~20 buracos, que lê mal (achado em
# 05/09/2026: Moema "ficou estranha"). 12 meses é enough pra mostrar
# tendência recente sem essa esparsidade.
SERIE_JANELA_MESES = 12


def _confianca(n_com_metrica: int) -> str:
    if n_com_metrica < LIMITE_CONFIANCA_INSUFICIENTE:
        return CONFIANCA_INSUFICIENTE
    if n_com_metrica < LIMITE_CONFIANCA_BAIXA:
        return CONFIANCA_BAIXA
    return CONFIANCA_OK


def _mediana_e_quartis(valores):
    if not valores:
        return None, None, None
    if len(valores) == 1:
        return valores[0], valores[0], valores[0]
    p25, _, p75 = statistics.quantiles(valores, n=4, method="inclusive")
    return p25, statistics.median(valores), p75


def _meses_atras(ano, mes, n):
    """(ano, mes) menos n meses, como tupla (ano, mes)."""
    absoluto = ano * 12 + (mes - 1) - n
    return absoluto // 12, absoluto % 12 + 1


def _primeiro_do_mes_atras(data, n):
    """Dia 1 do mês ``n`` meses antes de ``data``."""
    return dt.date(*_meses_atras(data.year, data.month, n), 1)


def _na_janela(qs, data_min):
    """``data_transacao >= data_min``. O ``ano_transacao__gte`` é só um
    pré-filtro grosso que usa o índice ``(distrito_slug, ano_transacao)`` —
    o corte fino é a data."""
    return qs.filter(ano_transacao__gte=data_min.year, data_transacao__gte=data_min)


def _so_mercado(qs):
    # Com o ponto: "1." não pode casar "10." nem "17.".
    filtro = Q()
    for codigo in NATUREZAS_DE_MERCADO:
        filtro |= Q(natureza__startswith=f"{codigo}.")
    return qs.filter(filtro)


def transacoes_da_regiao(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, data_min=None, ano=None):
    """O mesmo filtro de base que sustenta a mediana — qualidade boa, uso
    residencial por padrão, janela de 12 meses (ver ``JANELA_MESES_PADRAO``) —
    mas deliberadamente **sem** exigir ``rs_m2_construido``: excluir esconderia
    um SQL com cadastro defasado (``referencia-itbi.md`` §2.4) que tem
    ``valor_transacao`` real e só não tem R$/m² calculável. Fonte única para
    ``estatisticas_regiao`` e para a lista de transações, que só divergem num
    ponto: a lista mostra todas as naturezas, a mediana só as de mercado.

    ``data_min=None`` (padrão) calcula a janela a partir da transação mais
    recente da região, alargando pra 24 meses se 12 tiverem poucas vendas.
    ``data_min`` explícito fixa a mesma janela entre regiões (comparação #15).
    ``ano`` troca a janela pelo ano do negócio inteiro, e ``data_min`` vira 1º de
    janeiro dele.
    """
    base = queryset.filter(qualidade=0)
    if uso_grupo:
        base = base.filter(uso_grupo__in=uso_grupo)

    if ano is not None:
        return base.filter(ano_transacao=ano), dt.date(ano, 1, 1)

    if data_min is None:
        mais_recente = base.aggregate(m=Max("data_transacao"))["m"]
        if mais_recente is not None:
            data_min = _primeiro_do_mes_atras(mais_recente, JANELA_MESES_PADRAO - 1)
            if _na_janela(base, data_min).count() < LIMIAR_JANELA_AMPLA:
                data_min = _primeiro_do_mes_atras(mais_recente, JANELA_MESES_AMPLA - 1)

    if data_min is not None:
        base = _na_janela(base, data_min)

    return base, data_min


def estatisticas_regiao(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, data_min=None, ano=None,
                        so_mercado=True):
    """Resumo estatístico de uma região. ``queryset`` já vem filtrado por região
    (ex.: ``Transacao.objects.filter(distrito_slug="mooca")``) — aqui entram os
    filtros de qualidade do dado, não de localização.

    ``data_min=None`` (padrão) usa a janela de 12 meses da transação mais
    recente **nesta região** (ver ``transacoes_da_regiao``). Passar ``data_min``
    explícito fixa a mesma janela entre regiões — necessário para comparação (#15).

    ``so_mercado=False`` inclui todas as naturezas (ver ``NATUREZAS_DE_MERCADO``).
    """
    base, data_min = transacoes_da_regiao(queryset, uso_grupo=uso_grupo, data_min=data_min, ano=ano)
    n_fora_do_mercado = 0
    if so_mercado:
        mercado = _so_mercado(base)
        n_fora_do_mercado = base.count() - mercado.count()
        base = mercado

    n_transacoes = base.count()
    valores_transacao = list(base.values_list("valor_transacao", flat=True))
    valor_mediano_transacao = statistics.median(valores_transacao) if valores_transacao else None

    com_metrica = base.filter(rs_m2_construido__isnull=False)
    n_com_metrica = com_metrica.count()
    valores_m2 = list(com_metrica.values_list("rs_m2_construido", flat=True))
    p25_rs_m2, mediana_rs_m2, p75_rs_m2 = _mediana_e_quartis(valores_m2)

    # A base de cálculo do imposto é o maior entre o declarado e a referência da
    # Prefeitura; quando o declarado fica abaixo, o R$/m² é a referência, não o
    # preço pago. A tela diz em quantas vendas isso aconteceu.
    com_referencia = com_metrica.filter(vvr_proporcional__gt=0)
    n_com_referencia = com_referencia.count()
    pct_pela_referencia = (
        com_referencia.filter(base_calculo__gt=F("valor_transacao") + 1).count() / n_com_referencia * 100
        if n_com_referencia
        else None
    )

    areas = list(com_metrica.exclude(area_construida__isnull=True).values_list("area_construida", flat=True))
    area_mediana = statistics.median(areas) if areas else None

    datas = list(base.exclude(data_transacao__isnull=True).values_list("data_transacao", flat=True))
    periodo = (min(datas), max(datas)) if datas else (None, None)

    return {
        "data_min": data_min,
        "n_transacoes": n_transacoes,
        "n_com_metrica": n_com_metrica,
        "n_fora_do_mercado": n_fora_do_mercado,
        "pct_pela_referencia": pct_pela_referencia,
        "mediana_rs_m2": mediana_rs_m2,
        "p25_rs_m2": p25_rs_m2,
        "p75_rs_m2": p75_rs_m2,
        "valor_mediano_transacao": valor_mediano_transacao,
        "area_mediana": area_mediana,
        "periodo_inicio": periodo[0],
        "periodo_fim": periodo[1],
        "confianca": _confianca(n_com_metrica),
    }


def _meses_entre(inicio, fim):
    """[(ano, mes), ...] de inicio a fim (tuplas (ano, mes)), inclusive."""
    ano, mes = inicio
    meses = []
    while (ano, mes) <= fim:
        meses.append((ano, mes))
        mes += 1
        if mes == 13:
            mes = 1
            ano += 1
    return meses


def serie_mensal(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, data_min=None, ano=None,
                 so_mercado=True):
    """Mediana mensal de R$/m² (RF8) — evolução do valor típico no tempo.

    Usa ``data_transacao`` (quando o negócio aconteceu), nunca ``mes_guia``
    (quando a guia foi paga — a issue #14 é enfática nisso, são coisas
    diferentes). Mês sem transação que sustente uma mediana entra na série
    como buraco (``mediana_rs_m2=None``), nunca é pulado: emendar dois meses
    distantes como se fossem vizinhos mentiria sobre a evolução.

    A série mostra no máximo os últimos ``SERIE_JANELA_MESES`` (12) meses,
    contados a partir do mês mais recente com dado **nesta região** — não do
    calendário real. Mantém o teto próprio porque ``data_min`` pode vir da
    janela alargada de 24 meses (região pequena): a mediana usa 24, a série
    ainda mostra 12.
    """
    base, data_min = transacoes_da_regiao(queryset, uso_grupo=uso_grupo, data_min=data_min, ano=ano)
    if so_mercado:
        base = _so_mercado(base)
    pares = (
        base.exclude(data_transacao__isnull=True)
        .filter(rs_m2_construido__isnull=False)
        .values_list("data_transacao", "rs_m2_construido")
    )

    por_mes = defaultdict(list)
    for data, rs_m2 in pares:
        por_mes[(data.year, data.month)].append(rs_m2)

    if not por_mes:
        return [], data_min

    chaves = sorted(por_mes)
    inicio = max(chaves[0], _meses_atras(*chaves[-1], SERIE_JANELA_MESES - 1))
    serie = []
    for ano, mes in _meses_entre(inicio, chaves[-1]):
        valores = por_mes.get((ano, mes), [])
        serie.append({
            "ano": ano,
            "mes": mes,
            "mediana_rs_m2": statistics.median(valores) if valores else None,
            "n_transacoes": len(valores),
            "fraco": len(valores) < LIMIAR_MES_FRACO,
        })
    return serie, data_min


def inicio_da_janela_da_cidade(ano_guia, mes_guia):
    """1º dia da janela comum a todos os distritos: os 12 meses que terminam no último
    mês de guia carregado. Comum de propósito — no mapa da cidade os distritos são
    comparados entre si, e cada um com a própria janela (como na página da região)
    seria comparar períodos diferentes."""
    return dt.date(*_meses_atras(ano_guia, mes_guia, JANELA_MESES_PADRAO - 1), 1)


def valor_tipico_por_distrito(queryset, *, data_min=None, ano=None):
    """Mediana de R$/m² de cada distrito, com o mesmo filtro da região (qualidade,
    uso residencial, só natureza de mercado), numa janela única para todos:
    ``ano`` inteiro ou a partir de ``data_min``. Uma consulta só e a mediana em
    Python, em vez de uma consulta por distrito."""
    base = _so_mercado(
        queryset.filter(qualidade=0, uso_grupo__in=USO_GRUPO_RESIDENCIAL, rs_m2_construido__isnull=False)
        .exclude(distrito_slug="")
    )
    if ano is not None:
        base = base.filter(ano_transacao=ano)
    elif data_min is not None:
        base = _na_janela(base, data_min)

    por_distrito = defaultdict(list)
    for slug, rs_m2 in base.values_list("distrito_slug", "rs_m2_construido"):
        por_distrito[slug].append(rs_m2)
    return {
        slug: {"mediana_rs_m2": statistics.median(v), "n_com_metrica": len(v), "confianca": _confianca(len(v))}
        for slug, v in por_distrito.items()
    }
