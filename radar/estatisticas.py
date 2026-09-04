"""Valor típico por região: a mediana de R$/m² que é o produto do PI2.

``estatisticas_regiao`` é pura sobre um queryset já filtrado por região (o chamador
decide *onde*; esta função decide *quais transações contam* e *como resumi-las*).
Detalhe e critério de aceitação: ``docs/local/issues/08-servico-estatisticas.md``.
"""

import statistics

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


def estatisticas_regiao(queryset, *, uso_grupo=USO_GRUPO_RESIDENCIAL, ano_min=None):
    """Resumo estatístico de uma região. ``queryset`` já vem filtrado por região
    (ex.: ``Transacao.objects.filter(distrito_slug="mooca")``) — aqui entram os
    filtros de qualidade do dado, não de localização.

    ``ano_min=None`` (padrão) usa os últimos ``JANELA_ANOS_PADRAO`` anos com
    transação **nesta região**, para uma área que ficou muda recentemente não
    aparecer vazia por causa de um ano de referência global. Passar ``ano_min``
    explícito fixa a mesma janela entre regiões — necessário para comparação (#15).
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
