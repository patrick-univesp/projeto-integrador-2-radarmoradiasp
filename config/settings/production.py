from csp.constants import NONE, SELF
from decouple import config

from .base import *  # noqa: F403

DEBUG = False

# TLS termina na Cloudflare; o cloudflared repassa X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # "Always Use HTTPS" ja redireciona na borda
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Padrao do Django e duas semanas. A unica sessao que existe hoje e a de quem
# administra, entao vale encurtar a janela de uma sessao roubada.
SESSION_COOKIE_AGE = 8 * 60 * 60

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in config("CSRF_TRUSTED_ORIGINS", default="").split(",") if o.strip()
]

MIDDLEWARE.insert(0, "django.middleware.gzip.GZipMiddleware")  # noqa: F405
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

# "csp" fica fora do INSTALLED_APPS de proposito, mesmo raciocinio do
# django_ratelimit em base.py: o middleware le CONTENT_SECURITY_POLICY direto
# das settings, nao precisa do app registrado — so os checks do app dependem
# disso, e sao so avisos de formato de settings antigo, nada que valha o
# registro.
MIDDLEWARE.append("csp.middleware.CSPMiddleware")  # noqa: F405

# Issue #11. Vendorizado em static/vendor/ (sem CDN pra JS/CSS); os tiles do
# mapa (#12) sao externos por decisao — CARTO Positron (vetorial) sobre
# OpenStreetMap, unico tema claro do projeto (interface.md). Dominios exatos
# conferidos no style.json de producao do CARTO: basemaps.cartocdn.com serve o
# style.json inicial, tiles-{a..d}.basemaps.cartocdn.com os tiles/sprite/glyphs
# — o wildcard cobre os dois niveis de subdominio.
_CARTO = ("https://basemaps.cartocdn.com", "https://*.basemaps.cartocdn.com")

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": [SELF],
        "script-src": [SELF],
        "style-src": [SELF],
        "font-src": [SELF],
        # Ícones dos controles do MapLibre (zoom, bussola) sao data: URI no
        # CSS vendorizado.
        "img-src": [SELF, "data:", *_CARTO],
        "connect-src": [SELF, *_CARTO],
        # MapLibre roda o parser de tile numa Web Worker criada via blob:.
        "worker-src": [SELF, "blob:"],
        "object-src": [NONE],
        "base-uri": [SELF],
        "form-action": [SELF],
        "frame-ancestors": [NONE],
    }
}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

WHITENOISE_MANIFEST_STRICT = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simples": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simples"},
    },
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        # Sem isto o traceback da thread de carga se perde e a falha fica sem contexto.
        "radar": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
