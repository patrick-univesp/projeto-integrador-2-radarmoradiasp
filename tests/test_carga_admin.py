"""Tela de carga de planilha no admin: upload, validação, execução assíncrona."""

import shutil
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from radar import admin_carga
from radar.models import CargaMensal, Transacao

XLSX = Path(__file__).parent / "dados" / "amostra_itbi.xlsx"
URL = reverse("admin:radar_cargamensal_carregar")


@pytest.fixture
def admin_client(client, db):
    get_user_model().objects.create_superuser("op", "op@x.invalid", "s3nha-de-teste")
    client.force_login(get_user_model().objects.get(username="op"))
    return client


def _upload(nome="amostra_itbi.xlsx", conteudo=None):
    dados = conteudo if conteudo is not None else XLSX.read_bytes()
    return SimpleUploadedFile(nome, dados,
                              content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@pytest.mark.django_db
def test_tela_responde(admin_client):
    assert admin_client.get(URL).status_code == 200


@pytest.mark.django_db
def test_upload_cria_carga_e_redireciona(admin_client, monkeypatch):
    disparos = []
    monkeypatch.setattr(admin_carga.threading, "Thread",
                        lambda **kw: type("T", (), {"start": lambda s: disparos.append(kw)})())
    r = admin_client.post(URL, {"arquivo": _upload(), "substituir_mes": "on"})
    assert r.status_code == 302
    carga = CargaMensal.objects.get()
    assert carga.arquivo_nome == "amostra_itbi.xlsx"
    assert carga.substituir_mes is True
    assert carga.criado_por.username == "op"
    assert disparos, "a thread da carga não foi disparada"


@pytest.mark.django_db
def test_rodar_executa_a_carga(db, tmp_path):
    copia = tmp_path / "amostra.xlsx"
    shutil.copy(XLSX, copia)
    carga = CargaMensal.objects.create(arquivo_nome="amostra_itbi.xlsx")
    admin_carga._rodar(carga.pk, str(copia), None, True)
    carga.refresh_from_db()
    assert carga.status == CargaMensal.CONCLUIDO
    assert carga.linhas_gravadas == 10
    assert carga.pico_mb is not None
    assert Transacao.objects.count() == 10
    assert not copia.exists()  # o temp é apagado no fim


@pytest.mark.django_db
def test_recusa_arquivo_que_nao_e_xlsx(admin_client):
    r = admin_client.post(URL, {"arquivo": _upload(nome="planilha.csv", conteudo=b"a,b\n1,2\n")})
    assert r.status_code == 200
    assert b".xlsx" in r.content
    assert CargaMensal.objects.count() == 0


@pytest.mark.django_db
def test_recusa_arquivo_grande(admin_client, monkeypatch):
    monkeypatch.setattr(admin_carga, "TAMANHO_MAX_MB", 0)
    r = admin_client.post(URL, {"arquivo": _upload()})
    assert r.status_code == 200
    assert b"limite" in r.content
    assert CargaMensal.objects.count() == 0


@pytest.mark.django_db
def test_recusa_segunda_carga_com_uma_em_andamento(admin_client):
    CargaMensal.objects.create(arquivo_nome="rodando.xlsx", status=CargaMensal.RODANDO)
    r = admin_client.post(URL, {"arquivo": _upload()})
    assert r.status_code == 200
    assert "andamento" in r.content.decode()
    assert CargaMensal.objects.count() == 1  # não criou outra


@pytest.mark.django_db
def test_carga_rodando_velha_nao_bloqueia(admin_client):
    import datetime as dt

    from django.utils import timezone

    velha = CargaMensal.objects.create(arquivo_nome="morta.xlsx", status=CargaMensal.RODANDO)
    CargaMensal.objects.filter(pk=velha.pk).update(
        iniciado_em=timezone.now() - dt.timedelta(hours=3)
    )
    assert admin_carga.carga_em_andamento() is False


@pytest.mark.django_db
def test_exige_login(client):
    r = client.get(URL)
    assert r.status_code == 302
    assert "login" in r["Location"]
