"""Valor típico por região: a mediana de R$/m² que é o produto do PI2.

``estatisticas_regiao`` é pura sobre um queryset já filtrado por região (o chamador
decide *onde*; esta função decide *quais transações contam* e *como resumi-las*).
Detalhe e critério de aceitação: ``docs/local/issues/08-servico-estatisticas.md``.
"""

import statistics
from collections import defaultdict

from django.db.models import Max

# "Radar da Moradia": a mediana é de imóvel residencial. Sem este filtro, garagem,
# loja e indústria entrariam misturadas com casa e apartamento — achado em
# 04/09/2026, ver referencia-itbi.md §2.4.
USO_GRUPO_RESIDENCIAL = ("Casa / residência horizontal", "Apartamento / res. vertical")

JANELA_ANOS_PADRAO = 2

LIMITE_CONFIANCA_INSUFICIENTE = 10
LIMITE_CONFIANCA_BAIXA = 30

CONFIANCA_INSUFICIENTE = "insuficiente"
CONFIANCA_BAIXA = "baixa"
CONFIANCA_OK = "ok"

# Os limiares de confiança acima são calibrados pra n_com_metrica de uma
# região inteira (~2 anos somados). Um mês isolado nunca chega a 10 —
# aplicar o mesmo limiar aqui marcaria a série inteira como fraca sempre.
# Abaixo disso a "mediana" do mês é 1-2 valores brutos, não uma mediana de
# verdade.
LIMIAR_MES_FRACO = 3

# A série não olha pra trás mais que isso a partir do mês mais recente com
# dado na região. ano_min (JANELA_ANOS_PADRAO) já pode abrir uma janela de
# quase 2 anos — se a região só tem transação no começo e no fim dela, a
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


def transacoes_da_regiao(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, ano_min=None):
    """O mesmo filtro de base que sustenta a mediana — qualidade boa, uso
    residencial por padrão, janela de anos — mas deliberadamente **sem**
    exigir ``rs_m2_construido``: excluir esconderia um SQL com cadastro
    defasado (``referencia-itbi.md`` §2.4) que tem ``valor_transacao`` real e
    só não tem R$/m² calculável. Fonte única para ``estatisticas_regiao`` e
    para a lista de transações da #10 não divergirem.
    """
    base = queryset.filter(qualidade=0)
    if uso_grupo:
        base = base.filter(uso_grupo__in=uso_grupo)

    if ano_min is None:
        maior_ano = base.aggregate(m=Max("ano_transacao"))["m"]
        if maior_ano is not None:
            ano_min = maior_ano - (JANELA_ANOS_PADRAO - 1)
    if ano_min is not None:
        base = base.filter(ano_transacao__gte=ano_min)

    return base, ano_min


def estatisticas_regiao(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, ano_min=None):
    """Resumo estatístico de uma região. ``queryset`` já vem filtrado por região
    (ex.: ``Transacao.objects.filter(distrito_slug="mooca")``) — aqui entram os
    filtros de qualidade do dado, não de localização.

    ``ano_min=None`` (padrão) usa os últimos ``JANELA_ANOS_PADRAO`` anos com
    transação **nesta região**, para uma área que ficou muda recentemente não
    aparecer vazia por causa de um ano de referência global. Passar ``ano_min``
    explícito fixa a mesma janela entre regiões — necessário para comparação (#15).
    """
    base, ano_min = transacoes_da_regiao(queryset, uso_grupo=uso_grupo, ano_min=ano_min)

    n_transacoes = base.count()
    valores_transacao = list(base.values_list("valor_transacao", flat=True))
    valor_mediano_transacao = statistics.median(valores_transacao) if valores_transacao else None

    com_metrica = base.filter(rs_m2_construido__isnull=False)
    n_com_metrica = com_metrica.count()
    valores_m2 = list(com_metrica.values_list("rs_m2_construido", flat=True))
    p25_rs_m2, mediana_rs_m2, p75_rs_m2 = _mediana_e_quartis(valores_m2)

    areas = list(com_metrica.exclude(area_construida__isnull=True).values_list("area_construida", flat=True))
    area_mediana = statistics.median(areas) if areas else None

    datas = list(base.exclude(data_transacao__isnull=True).values_list("data_transacao", flat=True))
    periodo = (min(datas), max(datas)) if datas else (None, None)

    return {
        "ano_min": ano_min,
        "n_transacoes": n_transacoes,
        "n_com_metrica": n_com_metrica,
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


def _meses_atras(ano, mes, n):
    """(ano, mes) menos n meses, como tupla (ano, mes)."""
    absoluto = ano * 12 + (mes - 1) - n
    return absoluto // 12, absoluto % 12 + 1


def serie_mensal(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, ano_min=None):
    """Mediana mensal de R$/m² (RF8) — evolução do valor típico no tempo.

    Usa ``data_transacao`` (quando o negócio aconteceu), nunca ``mes_guia``
    (quando a guia foi paga — a issue #14 é enfática nisso, são coisas
    diferentes). Mês sem transação que sustente uma mediana entra na série
    como buraco (``mediana_rs_m2=None``), nunca é pulado: emendar dois meses
    distantes como se fossem vizinhos mentiria sobre a evolução.

    A série mostra no máximo os últimos ``SERIE_JANELA_MESES`` (12) meses,
    contados a partir do mês mais recente com dado **nesta região** — não do
    calendário real. ``ano_min`` pode abrir uma janela de quase 2 anos; sem
    esse teto, uma região com dado só no início e no fim dela vira uma série
    de 2 pontos separados por ~20 buracos.
    """
    base, ano_min = transacoes_da_regiao(queryset, uso_grupo=uso_grupo, ano_min=ano_min)
    pares = (
        base.exclude(data_transacao__isnull=True)
        .filter(rs_m2_construido__isnull=False)
        .values_list("data_transacao", "rs_m2_construido")
    )

    por_mes = defaultdict(list)
    for data, rs_m2 in pares:
        por_mes[(data.year, data.month)].append(rs_m2)

    if not por_mes:
        return [], ano_min

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
    return serie, ano_min
