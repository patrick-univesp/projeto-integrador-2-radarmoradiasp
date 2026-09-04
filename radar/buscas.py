from collections import Counter

from django.db.models import Count

from radar.carga.normalizacao import normalizar
from radar.models import Transacao
from radar.regioes import POR_SLUG


def _por_distrito(termo_norm):
    candidatos = [r for r in POR_SLUG.values() if r.distrito.startswith(termo_norm)]
    if not candidatos:
        return {}

    contagem = dict(
        Transacao.objects.filter(distrito_slug__in=[r.slug for r in candidatos])
        .values_list("distrito_slug")
        .annotate(n=Count("id"))
    )
    return {r.slug: {"texto": r.nome, "slug": r.slug, "n": contagem.get(r.slug, 0)} for r in candidatos}


def _por_bairro(termo_norm):
    linhas = (
        Transacao.objects.filter(bairro_norm__startswith=termo_norm)
        .exclude(distrito_slug="")
        .values_list("bairro_norm", "distrito_slug")
        .annotate(n=Count("id"))
    )

    por_bairro = {}
    for bairro, distrito_slug, n in linhas:
        por_bairro.setdefault(bairro, Counter())[distrito_slug] += n

    resultados = {}
    for contagem_por_distrito in por_bairro.values():
        slug, n = contagem_por_distrito.most_common(1)[0]
        r = POR_SLUG[slug]
        resultados[slug] = {"texto": r.nome, "slug": slug, "n": n}
    return resultados


def sugerir_regioes(termo, limite=8):
    termo_norm = normalizar(termo)
    if not termo_norm:
        return []

    por_slug = _por_distrito(termo_norm)
    for slug, r in _por_bairro(termo_norm).items():
        por_slug.setdefault(slug, r)

    resultados = sorted(por_slug.values(), key=lambda r: r["n"], reverse=True)
    return resultados[:limite]
