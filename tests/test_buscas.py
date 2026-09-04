"""radar/buscas.py — autocomplete de região (#06): resolve um termo digitado
para regiões candidatas, casando contra o registro de distritos e contra o
bairro cru da carga (bairro_norm).
"""

import pytest

from radar.buscas import sugerir_regioes


@pytest.mark.django_db
def test_sugere_distrito_por_prefixo():
    resultado = sugerir_regioes("itaim")
    assert any(r["slug"] == "itaim-bibi" for r in resultado)


@pytest.mark.django_db
def test_termo_acentuado_casa_com_distrito_sem_acento():
    """"moóca" precisa achar "MOOCA" — normalizar() já resolve, sem código novo."""
    resultado = sugerir_regioes("moóca")
    assert any(r["slug"] == "mooca" for r in resultado)


@pytest.mark.django_db
def test_termo_vazio_nao_bate_no_banco(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert sugerir_regioes("") == []


_seq = 0


def _transacao(distrito_slug, bairro_norm=""):
    global _seq
    _seq += 1
    from radar.models import Transacao

    return Transacao.objects.create(
        sql=f"{_seq:011d}", valor_transacao=1, base_calculo=1,
        distrito_slug=distrito_slug, bairro_norm=bairro_norm,
    )


@pytest.mark.django_db
def test_ordena_por_volume_de_transacoes():
    for _ in range(5):
        _transacao("itaim-paulista")
    for _ in range(1):
        _transacao("itaim-bibi")

    resultado = sugerir_regioes("itaim")
    slugs = [r["slug"] for r in resultado]
    assert slugs.index("itaim-paulista") < slugs.index("itaim-bibi")


@pytest.mark.django_db
def test_sugere_pelo_bairro_resolvendo_pro_distrito():
    """"Vila Madalena" não é distrito — é bairro dentro de Pinheiros (mesmo caso
    do apelido em radar/regioes.py). O autocomplete precisa achar pelo bairro
    cru da carga e devolver o distrito de verdade, não o próprio nome do bairro."""
    _transacao("pinheiros", bairro_norm="VILA MADALENA")

    resultado = sugerir_regioes("vila madalena")
    assert any(r["slug"] == "pinheiros" for r in resultado)


@pytest.mark.django_db
def test_bairro_sem_distrito_resolvido_nao_vira_sugestao():
    """Sem distrito_slug não tem pra onde navegar (#09 é por distrito) — a
    linha existe (bairro preenchido, geo sem correspondência) mas não pode
    virar sugestão fantasma."""
    _transacao("", bairro_norm="VILA MADALENA")

    assert sugerir_regioes("vila madalena") == []


@pytest.mark.django_db
def test_respeita_o_limite():
    resultado = sugerir_regioes("a", limite=2)
    assert len(resultado) <= 2
