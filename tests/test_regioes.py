"""radar/regioes.py — o registro canônico dos 96 distritos. Ver
docs/local/issues/24-registro-canonico-de-regioes.md.
"""

import gzip
import json
from pathlib import Path

from radar.carga.normalizacao import _basico
from radar.regioes import _REGIOES, APELIDOS, POR_DISTRITO, POR_SLUG, buscar, slug_de_distrito

# Exceção documentada: o GeoSampa abrevia "São Miguel Paulista" para "SAO MIGUEL".
_EXCECOES_ROUND_TRIP = {"SAO MIGUEL"}


def test_tem_as_96_regioes():
    assert len(_REGIOES) == 96


def test_slugs_e_distritos_sao_unicos():
    assert len(POR_SLUG) == 96
    assert len(POR_DISTRITO) == 96


def test_nome_acentuado_bate_com_o_distrito_por_round_trip():
    """normalizacao._basico() é a mesma transformação que o GeoSampa já aplicou
    (NFKD + remove diacrítico + caixa alta). Se o nome curado estiver certo, o
    round-trip fecha sozinho — sem isso, um typo de acento passaria despercebido."""
    divergentes = [
        r for r in _REGIOES
        if r.distrito not in _EXCECOES_ROUND_TRIP and _basico(r.nome) != r.distrito
    ]
    assert not divergentes, divergentes


def test_sao_miguel_e_a_unica_excecao_do_round_trip():
    r = POR_DISTRITO["SAO MIGUEL"]
    assert r.nome == "São Miguel Paulista"
    assert _basico(r.nome) != r.distrito  # confirma que a exceção é real, não sobra


def test_todo_distrito_da_referencia_geo_esta_no_registro():
    """Varre radar/dados_geo/ (a mesma referência que a carga usa) e garante que
    nenhum distrito real fica de fora do registro — é o que evitaria a #24 ter
    ficado desatualizada num refresh futuro."""
    encontrados = set()
    raiz = Path(__file__).resolve().parent.parent / "radar" / "dados_geo"
    for arq in raiz.glob("*.json.gz"):
        with gzip.open(arq, "rt") as f:
            dados = json.load(f)
        for lote in dados["lotes"]:
            if lote[7]:
                encontrados.add(lote[7])
    assert encontrados <= set(POR_DISTRITO)


def test_zonas_sao_as_cinco_documentadas():
    assert {r.zona for r in _REGIOES} == {"Centro", "Leste", "Norte", "Oeste", "Sul"}


def test_marsilac_esta_no_registro_mesmo_sem_transacao():
    """Marsilac tem zero lotes na referência geo — é por isso que o registro não
    pode ser derivado das transações (achado de 03/09/2026)."""
    assert "marsilac" in POR_SLUG


def test_slug_de_distrito_e_lookup_puro():
    assert slug_de_distrito("BUTANTA") == "butanta"
    assert slug_de_distrito("SE") == "se"
    assert slug_de_distrito("") == ""
    assert slug_de_distrito("NAO EXISTE") == ""


def test_buscar_resolve_nome_e_apelido():
    assert buscar("Mooca").distrito == "MOOCA"
    assert buscar("mooca").distrito == "MOOCA"
    assert buscar("Vila Madalena").slug == "pinheiros"
    assert buscar("xpto-nao-existe") is None


def test_todo_apelido_aponta_para_slug_valido():
    for apelido, slug in APELIDOS.items():
        assert slug in POR_SLUG, f"apelido {apelido!r} aponta para slug inexistente {slug!r}"
