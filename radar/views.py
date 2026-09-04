from django.http import Http404, HttpResponsePermanentRedirect
from django.shortcuts import render
from django.urls import reverse

from radar.models import Transacao
from radar.regioes import APELIDOS, POR_SLUG

# Slugs do registro canônico — nunca string solta, pra nenhum link da home
# apontar pra um slug que a página da região não aceite.
REGIOES_DESTAQUE_SLUGS = ("mooca", "itaim-bibi", "tatuape", "santana", "vila-mariana", "butanta")

_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _resumo_da_base():
    """Total de transações e período coberto (pelo mês da guia), lidos do banco.

    Ficam vazios se a carga não rodou neste ambiente — a home renderiza igual.
    """
    total = Transacao.objects.count()
    guias = (
        Transacao.objects.filter(ano_guia__isnull=False, mes_guia__isnull=False)
        .order_by("ano_guia", "mes_guia")
        .values_list("ano_guia", "mes_guia")
    )
    primeiro, ultimo = guias.first(), guias.last()

    if not primeiro:
        periodo = ""
    elif primeiro == ultimo:
        periodo = f"{_MESES[primeiro[1] - 1]} de {primeiro[0]}"
    elif primeiro[0] == ultimo[0]:
        periodo = f"{_MESES[primeiro[1] - 1]} a {_MESES[ultimo[1] - 1]} de {ultimo[0]}"
    else:
        periodo = (
            f"{_MESES[primeiro[1] - 1]} de {primeiro[0]} a "
            f"{_MESES[ultimo[1] - 1]} de {ultimo[0]}"
        )

    return {
        "n_vendas": total,
        "total_vendas": f"{total:,}".replace(",", "."),
        "periodo": periodo,
    }


def inicio(request):
    return render(
        request,
        "radar/inicio.html",
        {
            "regioes_destaque": [POR_SLUG[s] for s in REGIOES_DESTAQUE_SLUGS],
            **_resumo_da_base(),
        },
    )


def busca(request):
    termo = (request.GET.get("q") or "").strip()
    return render(
        request,
        "radar/em_breve.html",
        {
            "titulo": f"Busca por “{termo}”" if termo else "Busca",
            "mensagem": (
                "A busca ainda não está ligada: a base de transações do ITBI não foi "
                "carregada neste ambiente. Esta tela existe para o caminho da interface "
                "ficar completo enquanto o restante é construído."
            ),
        },
    )


def regiao(request, slug):
    if slug in APELIDOS:
        return HttpResponsePermanentRedirect(reverse("radar:regiao", args=[APELIDOS[slug]]))
    r = POR_SLUG.get(slug)
    if r is None:
        raise Http404(f"região {slug!r} não existe")
    return render(
        request,
        "radar/em_breve.html",
        {
            "titulo": r.nome,
            "mensagem": (
                "A página da região mostrará o valor típico do metro quadrado, a faixa "
                "de preços e quantas vendas sustentam o número. Ainda não está pronta."
            ),
        },
    )


def entrar(request):
    return render(request, "404.html", status=404)
