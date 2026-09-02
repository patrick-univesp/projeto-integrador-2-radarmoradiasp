from django.shortcuts import render
from django.utils.text import slugify

REGIOES_DESTAQUE = [
    "Mooca",
    "Itaim Bibi",
    "Tatuapé",
    "Santana",
    "Vila Mariana",
    "Butantã",
]

TOTAL_VENDAS = "113.095"
PERIODO = "janeiro a junho de 2026"


def inicio(request):
    return render(
        request,
        "radar/inicio.html",
        {
            "regioes_destaque": [{"nome": n, "slug": slugify(n)} for n in REGIOES_DESTAQUE],
            "total_vendas": TOTAL_VENDAS,
            "periodo": PERIODO,
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
    termo_legivel = slug.replace("-", " ").title()
    return render(
        request,
        "radar/em_breve.html",
        {
            "titulo": termo_legivel,
            "mensagem": (
                "A página da região mostrará o valor típico do metro quadrado, a faixa "
                "de preços e quantas vendas sustentam o número. Ainda não está pronta."
            ),
        },
    )


def entrar(request):
    return render(request, "404.html", status=404)

