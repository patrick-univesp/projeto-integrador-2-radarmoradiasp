from decimal import Decimal

from django.http import Http404, HttpResponsePermanentRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django_ratelimit.decorators import ratelimit

from radar.buscas import sugerir_regioes
from radar.estatisticas import estatisticas_regiao
from radar.models import Transacao
from radar.regioes import APELIDOS, POR_SLUG

# Slugs do registro canônico — nunca string solta, pra nenhum link da home
# apontar pra um slug que a página da região não aceite.
REGIOES_DESTAQUE_SLUGS = ("mooca", "itaim-bibi", "tatuape", "santana", "vila-mariana", "butanta")

# Uma navegação por requisição — mais apertado que faria sentido pro autocomplete
# (#06, que dispara várias por busca). Issue #07.
TAXA_CONSULTA = "30/m"

# O autocomplete dispara mais de uma requisição por busca digitada (mesmo com
# debounce no cliente) — mais generoso que TAXA_CONSULTA de propósito.
TAXA_SUGESTOES = "60/m"

_MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def _rotular_periodo(ano_ini, mes_ini, ano_fim, mes_fim):
    """"janeiro de 2026" / "janeiro a julho de 2026" / "novembro de 2025 a março de 2026"."""
    if ano_ini == ano_fim and mes_ini == mes_fim:
        return f"{_MESES[mes_ini - 1]} de {ano_ini}"
    if ano_ini == ano_fim:
        return f"{_MESES[mes_ini - 1]} a {_MESES[mes_fim - 1]} de {ano_fim}"
    return f"{_MESES[mes_ini - 1]} de {ano_ini} a {_MESES[mes_fim - 1]} de {ano_fim}"


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
    periodo = _rotular_periodo(primeiro[0], primeiro[1], ultimo[0], ultimo[1]) if primeiro else ""

    return {
        "n_vendas": total,
        "total_vendas": f"{total:,}".replace(",", "."),
        "periodo": periodo,
    }


def _formatar_rs(valor):
    """"8.465" ou "8.465,50" — separador de milhar por ponto, duas casas só quando
    o valor tem centavos de verdade (issue #09: "duas casas quando couber")."""
    if valor is None:
        return None
    valor = Decimal(valor)
    negativo = valor < 0
    valor = abs(valor)
    inteiro = int(valor)
    texto = f"{inteiro:,}".replace(",", ".")
    centavos = valor - inteiro
    if centavos:
        texto = f"{texto},{int((centavos * 100).to_integral_value()):02d}"
    return f"-{texto}" if negativo else texto


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
                "A busca ainda não está ligada: falta o autocomplete que resolve um "
                "termo digitado para uma região. Esta tela existe para o caminho da "
                "interface ficar completo enquanto o restante é construído."
            ),
        },
    )


@ratelimit(key="ip", rate=TAXA_CONSULTA, block=False)
def regiao(request, slug):
    if request.limited:
        return render(request, "429.html", status=429)
    if slug in APELIDOS:
        return HttpResponsePermanentRedirect(reverse("radar:regiao", args=[APELIDOS[slug]]))
    r = POR_SLUG.get(slug)
    if r is None:
        raise Http404(f"região {slug!r} não existe")

    stats = estatisticas_regiao(Transacao.objects.filter(distrito_slug=slug))

    mediana = stats["mediana_rs_m2"]
    p25, p75 = stats["p25_rs_m2"], stats["p75_rs_m2"]
    pos_mediana_pct = None
    if mediana is not None and p75 != p25:
        # String, não número: LANGUAGE_CODE="pt-br" localiza um float no template
        # (ponto → vírgula), e "left: 50,0%" é CSS inválido.
        pos_mediana_pct = f"{float((mediana - p25) / (p75 - p25)) * 100:.1f}"
    elif mediana is not None:
        pos_mediana_pct = "50.0"

    return render(
        request,
        "radar/regiao.html",
        {
            "regiao": r,
            "stats": stats,
            "mediana_fmt": _formatar_rs(mediana),
            "p25_fmt": _formatar_rs(p25),
            "p75_fmt": _formatar_rs(p75),
            "pos_mediana_pct": pos_mediana_pct,
            "periodo": (
                _rotular_periodo(
                    stats["periodo_inicio"].year, stats["periodo_inicio"].month,
                    stats["periodo_fim"].year, stats["periodo_fim"].month,
                )
                if stats["periodo_inicio"]
                else ""
            ),
        },
    )


@ratelimit(key="ip", rate=TAXA_SUGESTOES, block=False)
def sugestoes(request):
    if request.limited:
        return JsonResponse({"sugestoes": []}, status=429)
    termo = request.GET.get("q", "")
    return JsonResponse({"sugestoes": sugerir_regioes(termo)})


def entrar(request):
    return render(request, "404.html", status=404)
