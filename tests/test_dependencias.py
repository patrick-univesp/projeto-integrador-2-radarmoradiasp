"""O runtime não pode arrastar pandas nem shapely: o container tem 600 MB e o
ponto-em-polígono já foi feito offline (ver docs/referencia-geo.md)."""

import ast
from pathlib import Path

import pytest

RADAR = Path(__file__).resolve().parent.parent / "radar"
PROIBIDOS = {"pandas", "numpy", "shapely"}


def _modulos_importados(caminho: Path):
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            yield from (a.name.split(".")[0] for a in no.names)
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            yield no.module.split(".")[0]


@pytest.mark.parametrize("arquivo", sorted(RADAR.rglob("*.py")), ids=str)
def test_radar_nao_importa_pandas_shapely_numpy(arquivo):
    achados = PROIBIDOS.intersection(_modulos_importados(arquivo))
    assert not achados, f"{arquivo.relative_to(RADAR.parent)} importa {achados}"
