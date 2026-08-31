#!/usr/bin/env bash
#
# Roda NA VM, instalado em /usr/local/bin/radar-deploy.sh e amarrado ao forced
# command da chave do CI em ~/.ssh/authorized_keys.
#
# A configuracao chega pelo stdin da sessao SSH no formato:
#
#   <variaveis de runtime do app>
#   ---DEPLOY---
#   <variaveis usadas so por este script>
set -euo pipefail

VERSAO="2026-08-31"
CONTAINER=radar
VOLUME=radar_data

echo "==> radar-deploy.sh versao $VERSAO"

umask 077
ENV_FILE=$(mktemp /tmp/radar.env.XXXXXX)
VARS_FILE=$(mktemp /tmp/radar.vars.XXXXXX)

limpar() {
  rm -f "$ENV_FILE" "$VARS_FILE"
  docker logout ghcr.io > /dev/null 2>&1 || true
}
trap limpar EXIT

# GHCR_TOKEN fica em VARS_FILE e nunca entra no container.
awk -v env_file="$ENV_FILE" -v vars_file="$VARS_FILE" '
  /^---DEPLOY---$/ { secao = 1; next }
  { if (secao) print > vars_file; else print > env_file }
'

if [ ! -s "$ENV_FILE" ] || [ ! -s "$VARS_FILE" ]; then
  echo "ERRO: configuracao ausente ou incompleta no stdin." >&2
  exit 1
fi

# shellcheck source=/dev/null
. "$VARS_FILE"
: "${IMAGE:?IMAGE ausente}"
: "${GHCR_ACTOR:?GHCR_ACTOR ausente}"
: "${GHCR_TOKEN:?GHCR_TOKEN ausente}"

echo "==> Autenticando no GHCR e baixando a imagem"
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_ACTOR" --password-stdin
docker pull "$IMAGE:latest"

echo "==> Substituindo o container"
docker stop "$CONTAINER" 2>/dev/null || true
docker rm "$CONTAINER" 2>/dev/null || true

# A VM tem 1 GB: sem teto, um vazamento derruba o host inteiro, sshd incluso.
docker run -d \
  --name "$CONTAINER" \
  --restart unless-stopped \
  --memory 600m \
  --memory-swap 1g \
  --pids-limit 200 \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m \
  -p 127.0.0.1:8000:8000 \
  -v "$VOLUME":/app/data \
  --env-file "$ENV_FILE" \
  "$IMAGE:latest"

# Host forjado a partir de ALLOWED_HOSTS: curl direto em 127.0.0.1 receberia 400.
HOST_HEADER=$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d= -f2- | cut -d, -f1)
: "${HOST_HEADER:?ALLOWED_HOSTS ausente na configuracao}"

echo "==> Aguardando a aplicacao responder (Host: $HOST_HEADER)"
for tentativa in $(seq 1 20); do
  if curl -fsS -o /dev/null -H "Host: $HOST_HEADER" http://127.0.0.1:8000/; then
    echo "OK: aplicacao respondendo na tentativa $tentativa."
    docker image prune -f > /dev/null
    exit 0
  fi
  sleep 3
done

echo "ERRO: a aplicacao nao respondeu em 60s. Ultimos 50 logs:" >&2
docker logs --tail 50 "$CONTAINER" >&2 || true
exit 1
