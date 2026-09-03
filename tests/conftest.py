import pytest


@pytest.fixture(autouse=True)
def _hash_rapido(settings):
    """PBKDF2 domina o tempo dos testes de login; aqui a forca do hash e irrelevante."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
