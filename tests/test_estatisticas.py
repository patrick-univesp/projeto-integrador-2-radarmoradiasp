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
    estatisticas_regiao,
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
def test_ano_min_explicito_sobrepoe_a_janela_automatica():
    _transacao(ano_transacao=2020, data_transacao=dt.date(2020, 1, 1))
    _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 1, 1))
    r = estatisticas_regiao(Transacao.objects.all(), ano_min=2020)
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
def test_estatisticas_expoe_o_ano_min_usado():
    _transacao(ano_transacao=2026, data_transacao=dt.date(2026, 6, 1))
    r = estatisticas_regiao(Transacao.objects.all())
    assert r["ano_min"] == 2025  # JANELA_ANOS_PADRAO=2: 2026 e 2025


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
    lista, ano_min = transacoes_da_regiao(Transacao.objects.all())
    assert lista.count() == stats["n_transacoes"] == 5
    assert ano_min == stats["ano_min"]


@pytest.mark.django_db
def test_transacoes_da_regiao_nao_exige_rs_m2_construido():
    """Achado da #10: um SQL com cadastro defasado tem valor_transacao real e
    qualidade=0, mas pode não ter R$/m² calculável — não pode sumir da lista."""
    _transacao(rs_m2_construido=None)
    lista, _ = transacoes_da_regiao(Transacao.objects.all())
    assert lista.count() == 1


@pytest.mark.django_db
def test_transacoes_da_regiao_ano_min_explicito_e_devolvido_igual():
    _transacao(ano_transacao=2020, data_transacao=dt.date(2020, 1, 1))
    lista, ano_min = transacoes_da_regiao(Transacao.objects.all(), ano_min=2020)
    assert ano_min == 2020
    assert lista.count() == 1


@pytest.mark.django_db
def test_transacoes_da_regiao_sem_nenhuma_transacao_devolve_ano_min_none():
    lista, ano_min = transacoes_da_regiao(Transacao.objects.none())
    assert ano_min is None
    assert lista.count() == 0
