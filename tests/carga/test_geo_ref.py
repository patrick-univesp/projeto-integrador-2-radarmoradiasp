"""Lookup na referência geo versionada. Sem shapely, sem rede — usa a amostra
em tests/dados/dados_geo_amostra/."""

from pathlib import Path

import pytest

from radar.carga import geo_ref
from radar.carga.geo_ref import carregar_indices, resolver

AMOSTRA = Path(__file__).parent.parent / "dados" / "dados_geo_amostra"


@pytest.fixture(scope="module")
def indices():
    return carregar_indices(AMOSTRA)


def test_geo_ref_nao_importa_shapely_nem_rede():
    import ast
    import inspect

    arvore = ast.parse(inspect.getsource(geo_ref))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module:
            importados.add(no.module.split(".")[0])
    assert "shapely" not in importados
    assert importados.isdisjoint({"urllib", "http", "socket", "requests"})


def test_t1_lote_exato_traz_distrito(indices):
    # setor 001, quadra 036, lote 0428 (RUA BRIG TOBIAS, REPUBLICA)
    lon, lat, nivel, distrito, subpref, regiao = resolver("00103604280", "R Brig Tobias", "391", indices)
    assert nivel == "T1"
    assert distrito == "REPUBLICA"
    assert regiao == "Centro"
    assert lon is not None and lat is not None


def test_t2_endereco_na_quadra(indices):
    # lote 9999 não existe; casa pelo endereço (quadra 036, RUA BRIG TOBIAS 391)
    _, _, nivel, distrito, _, _ = resolver("00103609999", "R Brig Tobias", "391", indices)
    assert nivel == "T2"
    assert distrito == "REPUBLICA"


def test_t4_centroide_da_quadra(indices):
    # sem lote nem logradouro: cai no centroide da quadra 036
    _, _, nivel, distrito, _, _ = resolver("00103600000", "", None, indices)
    assert nivel == "T4"
    assert distrito == "REPUBLICA"


def test_sem_correspondencia(indices):
    assert resolver("99999999999", "R X", 1, indices) == (None, None, "--", "", "", "")


def test_sql_invalido(indices):
    assert resolver("", "R X", 1, indices)[2] == "--"
    assert resolver("123", "R X", 1, indices)[2] == "--"


def test_distrito_preenchido_sempre_que_ha_geo(indices):
    for sql in ("00103604280", "16526701080"):
        r = resolver(sql, "", None, indices)
        assert r[2] != "--"
        assert r[3]  # distrito não vazio
