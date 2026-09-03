"""Resolucao do IP real do visitante."""

from django.http import HttpRequest


def cliente_real(request: HttpRequest) -> str | None:
    """IP de quem fez a requisicao, nao o do cloudflared.

    Atras do Cloudflare Tunnel o `REMOTE_ADDR` e sempre 127.0.0.1, entao um
    bloqueio por IP trataria o mundo inteiro como um visitante so. Confiar no
    `CF-Connecting-IP` so e seguro porque nada alem do cloudflared alcanca a
    aplicacao (bind em 127.0.0.1); se a porta for exposta, o cabecalho vira
    falsificavel.
    """
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR")
