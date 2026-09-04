from datetime import timedelta
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config("ALLOWED_HOSTS", default="").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "axes",
    "radar",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Precisa ser o ultimo: o axes le o resultado da autenticacao ja resolvido.
    "axes.middleware.AxesMiddleware",
]

# AxesStandaloneBackend precisa vir primeiro para interceptar a tentativa antes do
# ModelBackend confirmar a senha.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Bloqueio de forca bruta no login (inclusive o do admin).
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_RESET_ON_SUCCESS = True
AXES_CLIENT_IP_CALLABLE = "config.ip.cliente_real"

# [usuario, ip] trava o par; [ip] trava o IP que varre varios usuarios. Travar
# so por usuario ficou de fora: qualquer um trancaria a conta da equipe.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"], "ip_address"]

# Limite de taxa nos endpoints publicos de consulta (issue #07). Mesmo callable do
# axes acima: atras do Cloudflare Tunnel o REMOTE_ADDR e sempre 127.0.0.1.
#
# "django_ratelimit" fica de fora do INSTALLED_APPS de proposito: registrar o app
# liga o check de sistema que reprova (Error) o cache padrao (LocMemCache, por
# nao ser compartilhado entre processos) e derrubaria "manage.py runserver"/
# "migrate"/os testes. Sem CACHES redis/memcached (infra que este projeto evita
# de proposito — SQLite sem servidor, VM unica), o limite conta por worker do
# gunicorn (WEB_CONCURRENCY=2 por padrao, scripts/entrypoint.sh): o teto real e
# ate ~2x o valor nominal, nao um limite global exato. Aceitavel para o MVP —
# ainda protege contra um loop batendo sem parar; nao contra um ataque
# coordenado. Ver docs/local/issues/fechada/07-rate-limit.md.
RATELIMIT_IP_META_KEY = "config.ip.cliente_real"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# DB_PATH aponta para o volume Docker em producao (/app/data/db.sqlite3)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": config("DB_PATH", default=str(BASE_DIR / "db.sqlite3")),
        "OPTIONS": {
            # A carga segura o lock de escrita por um mês inteiro; sem busy_timeout,
            # um segundo escritor (sessão, axes) pega o padrão de 5 s e toma erro.
            "init_command": (
                "PRAGMA journal_mode=WAL;"
                " PRAGMA synchronous=NORMAL;"
                " PRAGMA busy_timeout=15000;"
            ),
            "transaction_mode": "IMMEDIATE",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
