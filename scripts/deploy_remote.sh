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

VERSAO="2026-08-31b"
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

subir() {
  docker rm -f "$CONTAINER" > /dev/null 2>&1 || true
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
    "$1" > /dev/null
}

saudavel() {
  for tentativa in $(seq 1 20); do
    if curl -fsS -o /dev/null -H "Host: $HOST_HEADER" http://127.0.0.1:8000/; then
      echo "OK: aplicacao respondendo na tentativa $tentativa."
      return 0
    fi
    sleep 3
  done
  return 1
}

echo "==> Autenticando no GHCR e baixando a imagem"
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_ACTOR" --password-stdin
docker pull "$IMAGE:latest"

# Host forjado a partir de ALLOWED_HOSTS: curl direto em 127.0.0.1 receberia 400.
# Validado antes de tocar no container: config incompleta nao derruba o que esta no ar.
HOST_HEADER=$(grep '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d= -f2- | cut -d, -f1)
: "${HOST_HEADER:?ALLOWED_HOSTS ausente na configuracao}"

# ID da imagem, nao a tag: o pull acima ja moveu o :latest para a imagem nova.
ANTERIOR=$(docker inspect --format '{{.Image}}' "$CONTAINER" 2>/dev/null || true)

# O entrypoint roda `migrate` ao subir, e migration nao volta com rollback de imagem.
# O snapshot e o unico jeito de desfazer uma migration destrutiva.
echo "==> Snapshot do banco (antes do migrate do entrypoint)"
docker run --rm -i -v "$VOLUME":/app/data --entrypoint python "$IMAGE:latest" - <<'PY'
import os, sqlite3
banco = "/app/data/db.sqlite3"
alvo = "/app/data/db-pre-deploy.sqlite3"
if not os.path.exists(banco):
    print("sem banco ainda (primeiro deploy): nada a salvar")
else:
    if os.path.exists(alvo):
        os.remove(alvo)
    # isolation_level=None: VACUUM nao roda dentro de transacao.
    con = sqlite3.connect(banco, isolation_level=None)
    con.execute("VACUUM INTO '/app/data/db-pre-deploy.sqlite3'")
    con.close()
    print("snapshot: %.1f MB" % (os.path.getsize(alvo) / 1048576))
PY

echo "==> Substituindo o container"
subir "$IMAGE:latest"

echo "==> Aguardando a aplicacao responder (Host: $HOST_HEADER)"
if saudavel; then
  docker image prune -f > /dev/null
  exit 0
fi

echo "ERRO: a aplicacao nao respondeu em 60s. Ultimos 50 logs:" >&2
docker logs --tail 50 "$CONTAINER" >&2 || true

if [ -z "$ANTERIOR" ]; then
  echo "Sem versao anterior para restaurar (primeiro deploy)." >&2
  exit 1
fi

echo "==> Restaurando a versao anterior ($ANTERIOR)" >&2
subir "$ANTERIOR"
if saudavel; then
  echo "ROLLBACK OK: a versao anterior esta no ar." >&2
else
  echo "CRITICO: o rollback tambem nao respondeu. A aplicacao esta fora." >&2
fi

# Restaurar banco automaticamente e destrutivo demais para um health check decidir:
# se a versao nova gravou algo antes de falhar, o restore joga fora. Fica manual.
cat >&2 <<TXT

O BANCO NAO FOI RESTAURADO. Se este deploy trouxe migration destrutiva, o codigo
antigo vai falhar contra o esquema novo. Snapshot pre-deploy, com o container parado:

  docker stop $CONTAINER
  sudo cp /var/lib/docker/volumes/$VOLUME/_data/db-pre-deploy.sqlite3 \\
          /var/lib/docker/volumes/$VOLUME/_data/db.sqlite3
  docker start $CONTAINER
TXT
exit 1
