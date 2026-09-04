"""Protecoes da tela de login do admin e limite de taxa nas consultas publicas."""

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from radar.views import TAXA_CONSULTA

SENHA = "senha-correta-de-teste-123"
_LIMITE = int(TAXA_CONSULTA.split("/")[0])


@pytest.fixture
def usuario(db):
    return get_user_model().objects.create_superuser(
        username="operador", email="operador@exemplo.invalid", password=SENHA
    )


def _tentar(client, usuario_nome, senha, ip="203.0.113.10"):
    return client.post(
        reverse("admin:login"),
        {"username": usuario_nome, "password": senha},
        REMOTE_ADDR=ip,
    )


@pytest.mark.django_db
def test_bloqueia_apos_o_limite_de_tentativas(client, usuario, settings):
    for _ in range(settings.AXES_FAILURE_LIMIT):
        _tentar(client, "operador", "errada")

    # Depois do limite, nem a senha certa passa.
    resposta = _tentar(client, "operador", SENHA)
    assert resposta.status_code == 429  # AXES_HTTP_RESPONSE_CODE


@pytest.mark.django_db
def test_ip_diferente_nao_herda_o_bloqueio_do_par(client, usuario, settings):
    """Trava por [usuario, ip] nao pode trancar a equipe inteira.

    Sem isto, uma forca bruta de fora deixaria quem esta em outro IP sem acesso.
    """
    for _ in range(settings.AXES_FAILURE_LIMIT):
        _tentar(client, "operador", "errada", ip="203.0.113.10")

    resposta = _tentar(client, "operador", SENHA, ip="198.51.100.20")
    assert resposta.status_code == 302  # login aceito


@pytest.mark.django_db
def test_usa_o_cabecalho_do_cloudflare_e_nao_o_do_tunel(client, usuario, settings):
    """Atras do tunel, REMOTE_ADDR e sempre 127.0.0.1.

    Se o axes olhasse so o REMOTE_ADDR, uma forca bruta trancaria todo mundo junto.
    """
    for _ in range(settings.AXES_FAILURE_LIMIT):
        client.post(
            reverse("admin:login"),
            {"username": "operador", "password": "errada"},
            REMOTE_ADDR="127.0.0.1",
            HTTP_CF_CONNECTING_IP="203.0.113.10",
        )

    # Mesmo REMOTE_ADDR do cloudflared, outro visitante real: passa.
    resposta = client.post(
        reverse("admin:login"),
        {"username": "operador", "password": SENHA},
        REMOTE_ADDR="127.0.0.1",
        HTTP_CF_CONNECTING_IP="198.51.100.20",
    )
    assert resposta.status_code == 302


# --- Limite de taxa em /regiao/<slug>/ (issue #07) -------------------------
#
# RATELIMIT_ENABLE fica desligado por padrão pra suíte inteira (conftest.py,
# _sem_limite_de_taxa) — os testes abaixo religam e limpam o cache do
# django-ratelimit antes e depois, pra não vazar contagem pros outros testes.


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.django_db
def test_regiao_bloqueia_apos_muitas_requisicoes(client):
    cache.clear()
    url = reverse("radar:regiao", args=["mooca"])
    for _ in range(_LIMITE):
        assert client.get(url, REMOTE_ADDR="203.0.113.30").status_code == 200

    resposta = client.get(url, REMOTE_ADDR="203.0.113.30")
    assert resposta.status_code == 429
    assert "Muitas requisições" in resposta.content.decode()
    cache.clear()


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.django_db
def test_regiao_ip_diferente_nao_herda_o_bloqueio(client):
    """Trava por IP não pode trancar quem nunca fez a requisição em excesso."""
    cache.clear()
    url = reverse("radar:regiao", args=["mooca"])
    for _ in range(_LIMITE + 1):
        client.get(url, REMOTE_ADDR="203.0.113.31")

    resposta = client.get(url, REMOTE_ADDR="198.51.100.31")
    assert resposta.status_code == 200
    cache.clear()


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.django_db
def test_regiao_usa_o_cabecalho_do_cloudflare_e_nao_o_do_tunel(client):
    """Atras do túnel, REMOTE_ADDR é sempre 127.0.0.1 — sem o CF-Connecting-IP,
    um visitante em loop trancaria todo mundo que passa pelo túnel junto."""
    cache.clear()
    url = reverse("radar:regiao", args=["mooca"])
    for _ in range(_LIMITE + 1):
        client.get(url, REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.32")

    # Mesmo REMOTE_ADDR do cloudflared, outro visitante real: passa.
    resposta = client.get(url, REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="198.51.100.32")
    assert resposta.status_code == 200
    cache.clear()


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.django_db
def test_regiao_uso_normal_nao_atinge_o_limite(client):
    cache.clear()
    url = reverse("radar:regiao", args=["mooca"])
    for _ in range(5):
        assert client.get(url, REMOTE_ADDR="203.0.113.33").status_code == 200
    cache.clear()
