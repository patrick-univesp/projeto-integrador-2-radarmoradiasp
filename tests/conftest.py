import pytest


@pytest.fixture(autouse=True)
def _hash_rapido(settings):
    """PBKDF2 domina o tempo dos testes de login; aqui a forca do hash e irrelevante."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _sem_limite_de_taxa(settings):
    """O cache do django-ratelimit e compartilhado entre TODOS os testes do mesmo
    processo pytest — sem isto, testes sem nada a ver com a #07 acumulariam
    requisicoes em /regiao/<slug>/ e um deles acabaria travando com 429 por
    acidente. Os testes da propria #07 religam explicitamente."""
    settings.RATELIMIT_ENABLE = False


@pytest.fixture(autouse=True)
def _sugestoes_sem_memoria():
    """As listas de bairros e ruas das sugestões ficam em memória por uma hora; entre
    testes, cada um cria as próprias transações."""
    from radar import buscas

    buscas._memo.clear()
