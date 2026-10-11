"""Resultado caro guardado em memória em cada worker do gunicorn, por uma hora.

Usado onde recalcular a cada requisição pesa (lista de ruas das sugestões, valor típico
de todos os distritos no mapa da cidade). Passada a validade, o valor antigo continua
respondendo enquanto uma thread calcula o novo: só a primeira requisição depois de subir
o worker espera. Sem cache compartilhado entre workers (o projeto não tem Redis), cada
um calcula o seu; uma carga nova aparece em até uma hora.
"""

import threading
import time

from django.db import connection

VALIDADE_SEGUNDOS = 3600
_memo = {}
_renovando = set()


def _renovar(nome, calcular):
    try:
        _memo[nome] = (calcular(), time.monotonic())
    finally:
        _renovando.discard(nome)
        connection.close()


def memorizado(nome, calcular):
    valor, quando = _memo.get(nome, (None, None))
    if quando is None:
        valor = calcular()
        _memo[nome] = (valor, time.monotonic())
    elif time.monotonic() - quando > VALIDADE_SEGUNDOS and nome not in _renovando:
        _renovando.add(nome)
        threading.Thread(target=_renovar, args=(nome, calcular), daemon=True).start()
    return valor
