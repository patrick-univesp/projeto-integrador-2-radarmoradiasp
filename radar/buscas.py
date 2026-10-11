import threading
import time
from collections import Counter
from urllib.parse import urlencode

from django.db import connection
from django.db.models import Count
from django.urls import reverse

from radar.carga.normalizacao import normalizar, normalizar_logradouro
from radar.models import Transacao
from radar.regioes import POR_SLUG

# Bairros e ruas distintos, com a contagem, ficam em memória em cada worker: filtrar
# algumas dezenas de milhares de nomes em Python leva milissegundos, contra ~0,7 s de
# LIKE + GROUP BY sobre a base inteira a cada tecla (medido em produção com 780 mil
# transações, 11/10/2026). Passada a validade, a lista antiga continua respondendo
# enquanto uma thread monta a nova: só a primeira consulta depois de subir o worker
# espera. Uma carga nova aparece nas sugestões em até uma hora.
VALIDADE_SEGUNDOS = 3600
_memo = {}
_renovando = set()


def _renovar(nome, calcular):
    try:
        _memo[nome] = (calcular(), time.monotonic())
    finally:
        _renovando.discard(nome)
        connection.close()


def _memorizado(nome, calcular):
    valor, quando = _memo.get(nome, (None, None))
    if quando is None:
        valor = calcular()
        _memo[nome] = (valor, time.monotonic())
    elif time.monotonic() - quando > VALIDADE_SEGUNDOS and nome not in _renovando:
        _renovando.add(nome)
        threading.Thread(target=_renovar, args=(nome, calcular), daemon=True).start()
    return valor


def _bairros():
    return list(
        Transacao.objects.exclude(bairro_norm="").exclude(distrito_slug="")
        .values_list("bairro_norm", "distrito_slug")
        .annotate(n=Count("id"))
    )


def _ruas():
    return list(
        Transacao.objects.exclude(logradouro_norm="")
        .values_list("logradouro_norm")
        .annotate(n=Count("id"))
        .order_by("-n")
    )


def _por_distrito(termo_norm):
    candidatos = [r for r in POR_SLUG.values() if r.distrito.startswith(termo_norm)]
    if not candidatos:
        return {}

    contagem = dict(
        Transacao.objects.filter(distrito_slug__in=[r.slug for r in candidatos])
        .values_list("distrito_slug")
        .annotate(n=Count("id"))
    )
    return {r.slug: _regiao(r, contagem.get(r.slug, 0)) for r in candidatos}


def _por_bairro(termo_norm):
    por_bairro = {}
    for bairro, distrito_slug, n in _memorizado("bairros", _bairros):
        if bairro.startswith(termo_norm):
            por_bairro.setdefault(bairro, Counter())[distrito_slug] += n

    resultados = {}
    for contagem_por_distrito in por_bairro.values():
        slug, n = contagem_por_distrito.most_common(1)[0]
        resultados[slug] = _regiao(POR_SLUG[slug], n)
    return resultados


def _regiao(r, n):
    return {"texto": r.nome, "slug": r.slug, "tipo": "regiao",
            "url": reverse("radar:regiao", args=[r.slug]), "n": n}


def sugerir_regioes(termo, limite=8):
    termo_norm = normalizar(termo)
    if not termo_norm:
        return []

    por_slug = _por_distrito(termo_norm)
    for slug, r in _por_bairro(termo_norm).items():
        por_slug.setdefault(slug, r)

    resultados = sorted(por_slug.values(), key=lambda r: r["n"], reverse=True)
    return resultados[:limite]


# Abaixo disso, a busca por rua devolveria metade da cidade ("RUA A" casa com tudo).
MINIMO_RUA = 3
_MINUSCULAS = {"DE", "DA", "DO", "DOS", "DAS", "E"}


def nome_de_rua(chave):
    """``'RUA BARAO DE ITAPETININGA'`` → ``'Rua Barao de Itapetininga'``. A chave
    não tem acento, então o nome exibido também não tem."""
    return " ".join(
        p.lower() if i and p in _MINUSCULAS else p.capitalize() for i, p in enumerate(chave.split())
    )


def url_de_rua(chave):
    return f"{reverse('radar:rua')}?{urlencode({'nome': chave})}"


def sugerir_ruas(termo, limite=5):
    """Ruas cujo nome tem uma palavra começando pelo termo ("dente" acha "RUA CORONEL
    JOAO DENTE"), das com mais transações para as com menos."""
    chave = normalizar_logradouro(termo)
    if len(chave) < MINIMO_RUA:
        return []
    meio = " " + chave
    achadas = []
    for nome, n in _memorizado("ruas", _ruas):
        if nome.startswith(chave) or meio in nome:
            achadas.append({"texto": nome_de_rua(nome), "tipo": "rua", "url": url_de_rua(nome), "n": n})
            if len(achadas) == limite:
                break
    return achadas


def sugerir(termo, limite=8, ruas=True):
    """Regiões primeiro (é o que a página principal mostra), ruas completam a lista."""
    regioes = sugerir_regioes(termo, limite)
    if not ruas or len(regioes) >= limite:
        return regioes
    return regioes + sugerir_ruas(termo, limite - len(regioes))
