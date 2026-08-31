#!/bin/sh
# Script + exec para o gunicorn receber SIGTERM direto; em CMD shell-form o sinal
# nao chega e o `docker stop` espera o timeout de 10s.
set -e

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 60 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --no-control-socket \
  --access-logfile - \
  --error-logfile -
