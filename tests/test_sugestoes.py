"""GET /api/sugestoes/ — endpoint HTTP do autocomplete (#06). O serviço puro
(radar/buscas.py) tem os próprios testes; aqui é só o contrato HTTP.
"""

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from radar.views import TAXA_SUGESTOES

_LIMITE = int(TAXA_SUGESTOES.split("/")[0])


@pytest.mark.django_db
def test_endpoint_responde_200(client):
    r = client.get(reverse("radar:sugestoes"), {"q": "itaim"})
    assert r.status_code == 200


@pytest.mark.django_db
def test_endpoint_devolve_json_com_a_sugestao(client):
    r = client.get(reverse("radar:sugestoes"), {"q": "itaim"})
    corpo = r.json()
    assert any(s["slug"] == "itaim-bibi" for s in corpo["sugestoes"])


@pytest.mark.django_db
def test_sem_termo_devolve_lista_vazia(client):
    r = client.get(reverse("radar:sugestoes"))
    assert r.json() == {"sugestoes": []}


@override_settings(RATELIMIT_ENABLE=True)
@pytest.mark.django_db
def test_bloqueia_apos_muitas_requisicoes(client):
    cache.clear()
    url = reverse("radar:sugestoes")
    for _ in range(_LIMITE):
        assert client.get(url, {"q": "a"}, REMOTE_ADDR="203.0.113.40").status_code == 200

    resposta = client.get(url, {"q": "a"}, REMOTE_ADDR="203.0.113.40")
    assert resposta.status_code == 429
    cache.clear()
