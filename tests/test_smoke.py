import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_inicio_responde(client):
    resposta = client.get(reverse("radar:inicio"))
    assert resposta.status_code == 200


@pytest.mark.django_db
def test_admin_responde(client):
    resposta = client.get(reverse("admin:login"))
    assert resposta.status_code == 200
