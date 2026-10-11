"""radar/estatisticas.py — a mediana que é o produto do PI2. Ver
docs/local/issues/08-servico-estatisticas.md.
"""

import datetime as dt
from decimal import Decimal

import pytest

from radar.estatisticas import (
    CONFIANCA_BAIXA,
    CONFIANCA_INSUFICIENTE,
    CONFIANCA_OK,
    LIMIAR_MES_FRACO,
    NATUREZAS_DE_MERCADO,
    estatisticas_regiao,
    serie_mensal,
    transacoes_da_regiao,
)
from radar.models import Transacao

_seq = 0


def _transacao(**over):
    global _seq
    _seq += 1
    campos = {
        "sql": f"{_seq:011d}",
        "distrito": "MOOCA",
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
    return Transacao.objects.create(**campos)


@pytest.mark.django_db
def test_mediana_impar():
    for v in ("10000", "12000", "15000"):
        _transacao(rs_m2_construido=Decimal(v))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["mediana_rs_m2"] == Decimal("12000")


@pytest.mark.django_db
def test_mediana_par():
    for v in ("10000", "12000", "14000", "16000"):
        _transacao(rs_m2_construido=Decimal(v))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["mediana_rs_m2"] == Decimal("13000")


@pytest.mark.django_db
def test_qualidade_diferente_de_zero_fica_fora():
    _transacao(rs_m2_construido=Decimal("10000"))
    _transacao(rs_m2_construido=Decimal("999999"), qualidade=1)
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["mediana_rs_m2"] == Decimal("10000")
    assert r["n_transacoes"] == 1


@pytest.mark.django_db
def test_rs_m2_nulo_nao_vira_zero():
    _transacao(rs_m2_construido=Decimal("10000"))
    _transacao(rs_m2_construido=None)
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["mediana_rs_m2"] == Decimal("10000")
    assert r["n_transacoes"] == 2
    assert r["n_com_metrica"] == 1


@pytest.mark.django_db
def test_transacao_de_1998_fora_do_recorte_padrao():
    _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 6, 1))
    _transacao(ano_transacao=1998, data_transacao=dt.date(1998, 3, 1), rs_m2_construido=Decimal("1"))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["n_transacoes"] == 1
    assert r["periodo_inicio"] == dt.date(2026, 6, 1)


@pytest.mark.django_db
def test_janela_padrao_e_12_meses_do_mes_mais_recente():
    for _ in range(30):  # 30+ evita o alargamento pra 24 meses
        _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 6, 15))
    _transacao(ano_transacao=2025, data_transacao=dt.date(2025, 6, 1))  # 12 meses e 1 dia atrás
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["data_min"] == dt.date(2025, 7, 1)
    assert r["n_transacoes"] == 30  # a de jun/2025 fica de fora


@pytest.mark.django_db
def test_janela_alarga_para_24_meses_quando_ha_poucas_vendas():
    for _ in range(3):
        _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 6, 15))
    for _ in range(2):  # dentro de 24 meses, fora de 12
        _transacao(ano_transacao=2025, data_transacao=dt.date(2025, 1, 15))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["data_min"] == dt.date(2024, 7, 1)
    assert r["n_transacoes"] == 5


@pytest.mark.django_db
def test_data_min_explicita_sobrepoe_a_janela_automatica():
    _transacao(ano_transacao=2020, data_transacao=dt.date(2020, 1, 1))
    _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 1, 1))
    r = estatisticas_regiao(Transacao.objects.all(), data_min=dt.date(2020, 1, 1))
    assert r["n_transacoes"] == 2


@pytest.mark.django_db
def test_n_transacoes_e_n_com_metrica_sao_contagens_separadas():
    _transacao()
    _transacao()
    _transacao(rs_m2_construido=None)
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["n_transacoes"] == 3
    assert r["n_com_metrica"] == 2


@pytest.mark.django_db
def test_regiao_com_3_transacoes_confianca_insuficiente():
    for _ in range(3):
        _transacao()
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["confianca"] == CONFIANCA_INSUFICIENTE


@pytest.mark.django_db
def test_confianca_baixa_entre_10_e_29():
    for _ in range(15):
        _transacao()
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["confianca"] == CONFIANCA_BAIXA


@pytest.mark.django_db
def test_confianca_ok_a_partir_de_30():
    for _ in range(30):
        _transacao()
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["confianca"] == CONFIANCA_OK


@pytest.mark.django_db
def test_garagem_loja_industria_fora_da_mediana_residencial_padrao():
    _transacao(uso_grupo="Apartamento / res. vertical", rs_m2_construido=Decimal("10000"))
    _transacao(uso_grupo="Garagem", rs_m2_construido=Decimal("50000"))
    _transacao(uso_grupo="Loja / comércio", rs_m2_construido=Decimal("1"))
    _transacao(uso_grupo="Indústria / armazém", rs_m2_construido=Decimal("1"))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["n_transacoes"] == 1
    assert r["mediana_rs_m2"] == Decimal("10000")


@pytest.mark.django_db
def test_uso_grupo_none_desliga_o_filtro_de_tipo():
    _transacao(uso_grupo="Apartamento / res. vertical")
    _transacao(uso_grupo="Garagem")
    r = estatisticas_regiao(Transacao.objects.all(), uso_grupo=None)
    assert r["n_transacoes"] == 2


@pytest.mark.django_db
def test_valor_mediano_area_mediana_e_periodo():
    _transacao(
        valor_transacao=Decimal("400000"), area_construida=Decimal("40"),
        data_transacao=dt.date(2026, 1, 10),
    )
    _transacao(
        valor_transacao=Decimal("600000"), area_construida=Decimal("60"),
        data_transacao=dt.date(2026, 7, 20),
    )
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["valor_mediano_transacao"] == Decimal("500000")
    assert r["area_mediana"] == Decimal("50")
    assert r["periodo_inicio"] == dt.date(2026, 1, 10)
    assert r["periodo_fim"] == dt.date(2026, 7, 20)


@pytest.mark.django_db
def test_sem_transacoes_nao_quebra():
    r = estatisticas_regiao(Transacao.objects.none())
    assert r["n_transacoes"] == 0
    assert r["n_com_metrica"] == 0
    assert r["mediana_rs_m2"] is None
    assert r["confianca"] == CONFIANCA_INSUFICIENTE


@pytest.mark.django_db
def test_uma_unica_transacao_nao_quebra_o_calculo_de_quartis():
    _transacao(rs_m2_construido=Decimal("10000"))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["mediana_rs_m2"] == r["p25_rs_m2"] == r["p75_rs_m2"] == Decimal("10000")


@pytest.mark.django_db
def test_estatisticas_expoe_a_data_min_usada():
    for _ in range(30):
        _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 6, 1))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["data_min"] == dt.date(2025, 7, 1)  # jun/2026 menos 11 meses


# ---- transacoes_da_regiao (#10) ----
# Mesmo filtro de base que estatisticas_regiao usa por baixo — o teste que
# importa aqui é que os dois nunca divirjam (critério de aceitação da #10:
# "a soma de itens paginados bate com o n_transacoes da #08").


@pytest.mark.django_db
def test_transacoes_da_regiao_bate_com_n_transacoes_de_estatisticas_regiao():
    for _ in range(5):
        _transacao()
    _transacao(qualidade=1)  # fora por qualidade
    _transacao(uso_grupo="Garagem")  # fora por tipo
    _transacao(ano_transacao=1998, data_transacao=dt.date(1998, 1, 1))  # fora da janela
    stats = estatisticas_regiao(Transacao.objects.all())
    lista, data_min = transacoes_da_regiao(Transacao.objects.all())
    assert lista.count() == stats["n_transacoes"] == 5
    assert data_min == stats["data_min"]


@pytest.mark.django_db
def test_transacoes_da_regiao_nao_exige_rs_m2_construido():
    """Achado da #10: um SQL com cadastro defasado tem valor_transacao real e
    qualidade=0, mas pode não ter R$/m² calculável — não pode sumir da lista."""
    _transacao(rs_m2_construido=None)
    lista, _ = transacoes_da_regiao(Transacao.objects.all())
    assert lista.count() == 1


@pytest.mark.django_db
def test_transacoes_da_regiao_data_min_explicita_e_devolvida_igual():
    _transacao(ano_transacao=2020, data_transacao=dt.date(2020, 1, 1))
    lista, data_min = transacoes_da_regiao(Transacao.objects.all(), data_min=dt.date(2020, 1, 1))
    assert data_min == dt.date(2020, 1, 1)
    assert lista.count() == 1


@pytest.mark.django_db
def test_transacoes_da_regiao_sem_nenhuma_transacao_devolve_data_min_none():
    lista, data_min = transacoes_da_regiao(Transacao.objects.none())
    assert data_min is None
    assert lista.count() == 0


# ---- serie_mensal (#14) ----


@pytest.mark.django_db
def test_serie_mensal_usa_data_transacao_nao_mes_guia():
    """Critério da #14: a série é construída sobre data_transacao, nunca
    mes_guia (mes_guia é quando a guia foi paga, não quando o negócio
    aconteceu — são coisas diferentes)."""
    _transacao(data_transacao=dt.date(2026, 3, 15), ano_guia=2026, mes_guia=7)
    _transacao(data_transacao=dt.date(2026, 3, 15), ano_guia=2026, mes_guia=7)
    serie, _ = serie_mensal(Transacao.objects.all())
    assert len(serie) == 1
    assert (serie[0]["ano"], serie[0]["mes"]) == (2026, 3)


@pytest.mark.django_db
def test_serie_mensal_mediana_por_mes():
    for v in ("8000", "10000", "12000"):
        _transacao(data_transacao=dt.date(2026, 1, 10), rs_m2_construido=Decimal(v))
    serie, _ = serie_mensal(Transacao.objects.all())
    assert serie[0]["mediana_rs_m2"] == Decimal("10000")
    assert serie[0]["n_transacoes"] == 3


@pytest.mark.django_db
def test_serie_mensal_preenche_buraco_sem_pular_mes():
    """Mês sem transação entra como buraco (mediana None), não é omitido —
    senão a linha emendaria dois meses distantes como se fossem vizinhos."""
    _transacao(data_transacao=dt.date(2026, 1, 10))
    _transacao(data_transacao=dt.date(2026, 4, 10))
    serie, _ = serie_mensal(Transacao.objects.all())
    assert [(p["ano"], p["mes"]) for p in serie] == [
        (2026, 1), (2026, 2), (2026, 3), (2026, 4),
    ]
    fevereiro = serie[1]
    assert fevereiro["mediana_rs_m2"] is None
    assert fevereiro["n_transacoes"] == 0


@pytest.mark.django_db
def test_serie_mensal_marca_mes_fraco():
    for _ in range(LIMIAR_MES_FRACO - 1):
        _transacao(data_transacao=dt.date(2026, 1, 10))
    for _ in range(LIMIAR_MES_FRACO):
        _transacao(data_transacao=dt.date(2026, 2, 10))
    serie, _ = serie_mensal(Transacao.objects.all())
    assert serie[0]["fraco"] is True
    assert serie[1]["fraco"] is False


@pytest.mark.django_db
def test_serie_mensal_mes_buraco_conta_como_fraco():
    _transacao(data_transacao=dt.date(2026, 1, 10))
    _transacao(data_transacao=dt.date(2026, 2, 10))
    serie, _ = serie_mensal(Transacao.objects.all())
    assert serie[0]["fraco"] is True  # buraco no meio, n=0


@pytest.mark.django_db
def test_serie_mensal_sem_transacao_devolve_lista_vazia():
    serie, data_min = serie_mensal(Transacao.objects.none())
    assert serie == []
    assert data_min is None


@pytest.mark.django_db
def test_serie_mensal_limita_a_12_meses_do_mes_mais_recente():
    """Achado em 05/09/2026: sem teto, uma região com dado só no início e no
    fim da janela alargada (24 meses) vira uma série de 2 pontos separados por
    ~20 buracos — lê mal. A série corta pros últimos 12 meses a partir do mês
    mais recente com dado, não do calendário real."""
    _transacao(data_transacao=dt.date(2025, 1, 10), ano_transacao=2025)
    _transacao(data_transacao=dt.date(2026, 1, 10), ano_transacao=2026)
    serie, _ = serie_mensal(Transacao.objects.all(), data_min=dt.date(2025, 1, 1))
    assert (serie[0]["ano"], serie[0]["mes"]) == (2025, 2)
    assert (serie[-1]["ano"], serie[-1]["mes"]) == (2026, 1)
    assert len(serie) == 12


@pytest.mark.django_db
def test_serie_mensal_respeita_o_mesmo_filtro_de_base():
    """Reusa transacoes_da_regiao — qualidade e uso_grupo residencial valem
    aqui igual valem pra mediana e pra lista (#10/#08), não é recorte à parte."""
    _transacao(data_transacao=dt.date(2026, 1, 10))
    _transacao(data_transacao=dt.date(2026, 1, 10), uso_grupo="Garagem")
    _transacao(data_transacao=dt.date(2026, 1, 10), qualidade=1)
    serie, _ = serie_mensal(Transacao.objects.all())
    assert serie[0]["n_transacoes"] == 1


# --- só natureza de mercado na mediana ---------------------------------------


@pytest.mark.django_db
def test_leilao_nao_move_a_mediana_e_e_contado_a_parte():
    for _ in range(30):
        _transacao(rs_m2_construido=Decimal("5000"))
    _transacao(rs_m2_construido=Decimal("1000"), natureza="4.Arrematação (em leilão ou hasta pública)")
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["mediana_rs_m2"] == Decimal("5000")
    assert r["p25_rs_m2"] == Decimal("5000")
    assert r["n_com_metrica"] == 30
    assert r["n_fora_do_mercado"] == 1


@pytest.mark.django_db
def test_lista_da_regiao_continua_com_todas_as_naturezas():
    _transacao()
    _transacao(natureza="17.Resolução da alienação fiduciária por inadimplemento")
    lista, _ = transacoes_da_regiao(Transacao.objects.all())
    assert lista.count() == 2


@pytest.mark.django_db
def test_codigo_de_mercado_nao_casa_com_prefixo_de_outro():
    assert 1 in NATUREZAS_DE_MERCADO and 10 not in NATUREZAS_DE_MERCADO
    _transacao(rs_m2_construido=Decimal("5000"))
    _transacao(rs_m2_construido=Decimal("1000"), natureza="10.Cessão dos direitos do arrematante")
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["n_com_metrica"] == 1
    assert r["n_fora_do_mercado"] == 1


@pytest.mark.django_db
def test_so_mercado_false_inclui_todas_as_naturezas():
    _transacao(rs_m2_construido=Decimal("5000"))
    _transacao(rs_m2_construido=Decimal("1000"), natureza="12.Dação em pagamento por escritura pública")
    r = estatisticas_regiao(Transacao.objects.all(), so_mercado=False)
    assert r["n_com_metrica"] == 2
    assert r["n_fora_do_mercado"] == 0


@pytest.mark.django_db
def test_confianca_e_calculada_sobre_a_base_ja_filtrada():
    for _ in range(9):
        _transacao()
    for _ in range(5):
        _transacao(natureza="15.Permuta por escritura pública")
    assert estatisticas_regiao(Transacao.objects.all())["confianca"] == CONFIANCA_INSUFICIENTE


@pytest.mark.django_db
def test_serie_mensal_exclui_natureza_fora_do_mercado():
    _transacao(rs_m2_construido=Decimal("5000"))
    _transacao(rs_m2_construido=Decimal("1000"), natureza="4.Arrematação (em leilão ou hasta pública)")
    serie, _ = serie_mensal(Transacao.objects.all())
    assert serie[-1]["n_transacoes"] == 1
    assert serie[-1]["mediana_rs_m2"] == Decimal("5000")


# --- referência da Prefeitura -------------------------------------------------


@pytest.mark.django_db
def test_pct_pela_referencia_conta_base_acima_do_declarado():
    for _ in range(6):
        _transacao(vvr_proporcional=Decimal("400000"))
    for _ in range(4):
        _transacao(valor_transacao=Decimal("300000"), base_calculo=Decimal("400000"),
                   vvr_proporcional=Decimal("400000"))
    assert estatisticas_regiao(Transacao.objects.all())["pct_pela_referencia"] == 40


@pytest.mark.django_db
def test_pct_pela_referencia_e_none_sem_vvr():
    _transacao()
    assert estatisticas_regiao(Transacao.objects.all())["pct_pela_referencia"] is None
