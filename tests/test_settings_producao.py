"""CSP de produção (#11). config.settings.production não é o settings module
dos testes (é config.settings.development, ver pytest.ini) — os testes abaixo
importam o módulo de produção direto e simulam a config dele por cima do
client de teste, sem precisar rodar a suíte inteira sob DEBUG=False.
"""

import pytest
from django.urls import reverse

from config.settings.production import CONTENT_SECURITY_POLICY


@pytest.mark.django_db
def test_csp_header_presente_com_configuracao_de_producao(client, settings):
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, "csp.middleware.CSPMiddleware"]
    settings.CONTENT_SECURITY_POLICY = CONTENT_SECURITY_POLICY

    r = client.get(reverse("radar:inicio"))

    assert "Content-Security-Policy" in r
    politica = r["Content-Security-Policy"]
    assert "default-src 'self'" in politica
    assert "script-src 'self'" in politica
    assert "'unsafe-inline'" not in politica


@pytest.mark.django_db
def test_csp_permite_os_dominios_do_carto_pros_tiles_do_mapa(client, settings):
    settings.MIDDLEWARE = [*settings.MIDDLEWARE, "csp.middleware.CSPMiddleware"]
    settings.CONTENT_SECURITY_POLICY = CONTENT_SECURITY_POLICY

    politica = client.get(reverse("radar:inicio"))["Content-Security-Policy"]

    assert "https://basemaps.cartocdn.com" in politica
    assert "https://*.basemaps.cartocdn.com" in politica


def test_csp_nao_referencia_nenhum_cdn_de_script_ou_estilo():
    """Critério de aceitação da #11: nenhum JS ou CSS de CDN — só os tiles do
    CARTO (img-src/connect-src) são externos, por decisão documentada."""
    diretivas = CONTENT_SECURITY_POLICY["DIRECTIVES"]
    assert diretivas["script-src"] == ["'self'"]
    assert diretivas["style-src"] == ["'self'"]


def test_vendor_do_maplibre_existe():
    from pathlib import Path

    assert Path("static/vendor/maplibre-gl.js").exists()
    assert Path("static/vendor/maplibre-gl.css").exists()


def test_distritos_geojson_existe():
    from pathlib import Path

    assert Path("static/data/distritos.geojson").exists()
