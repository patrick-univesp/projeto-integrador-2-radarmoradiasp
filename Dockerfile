FROM python:3.15.0-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --system --gid 1001 radar \
    && useradd --system --uid 1001 --gid radar --home-dir /app radar

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# SECRET_KEY de build fica no historico da imagem: nunca passe a real aqui.
ENV DJANGO_SETTINGS_MODULE=config.settings.production
RUN SECRET_KEY=build-only-key ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

# Criar /app/data aqui faz o volume nascer com dono radar; senao o Docker o cria como root.
RUN mkdir -p /app/data && chown -R radar:radar /app/data /app/staticfiles

USER radar

EXPOSE 8000

# Host vem de ALLOWED_HOSTS: sem isso o Django responde 400 (DisallowedHost).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,sys,urllib.request as u; h=os.environ.get('ALLOWED_HOSTS','localhost').split(',')[0].strip(); r=u.Request('http://127.0.0.1:8000/',headers={'Host':h}); sys.exit(0 if u.urlopen(r,timeout=4).status==200 else 1)"

ENTRYPOINT ["/app/scripts/entrypoint.sh"]
