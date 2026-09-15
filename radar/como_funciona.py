"""Dados da página "Como funciona": uma linha real da planilha passando pela carga,
e os números da base inteira em cada etapa.

A linha de exemplo passa pela **mesma função** que a carga usa
(``_linha_para_transacao``), com a referência geo do setor dela. Se uma regra de
mineração mudar, a página muda junto — ela não tem como descrever uma carga que
não existe mais.
"""

import datetime as dt
from functools import lru_cache

from django.core.cache import cache
from django.db import connection
from django.db.models import Count

from radar.carga import geo_ref
from radar.management.commands.carregar_itbi import (
    BLOCOS_PADRAO,
    C_ACONSTR,
    C_BAIRRO,
    C_BASE,
    C_CEP,
    C_DATA,
    C_LOGR,
    C_NATUREZA,
    C_NUM,
    C_PROP,
    C_SQL,
    C_USOCOD,
    C_VALOR,
    _linha_para_transacao,
)
from radar.models import CargaMensal, Transacao

# Linha 1.331 da aba JAN-2026 de "GUIAS DE ITBI PAGAS (27082026)", célula por
# célula, na ordem das 28 colunas. Complemento, referência e matrícula ficaram
# vazios: não mudam nenhum campo derivado e identificariam a unidade.
ABA_EXEMPLO = "JAN-2026"
LINHA_EXEMPLO_NA_ABA = 1331
LINHA_EXEMPLO = (
    2702102743, "R ALM BRASIL", 243, "", "TORRE  C", "", 3164120, "1.Compra e venda",
    570000, dt.datetime(2025, 12, 12), 347661, 100, 347661, 570000,
    "99.SFI, Carteira Hipotecária, etc", 400000, "7º Cartório de Registro de Imóvel", "",
    "Ativo Predial", 4410, 67.13, 0.0055, 98, 20,
    "APARTAMENTO EM CONDOMÍNIO (EXIGE FRAÇÃO IDEAL)", 23, "RESIDENCIAL VERTICAL", 2011,
)

# (letra da coluna no Excel, cabeçalho curto, posição na tupla)
COLUNAS_EXEMPLO = (
    ("A", "SQL", C_SQL),
    ("B", "Logradouro", C_LOGR),
    ("C", "Número", C_NUM),
    ("E", "Bairro", C_BAIRRO),
    ("G", "CEP", C_CEP),
    ("H", "Natureza", C_NATUREZA),
    ("I", "Valor", C_VALOR),
    ("J", "Data", C_DATA),
    ("L", "Proporção %", C_PROP),
    ("N", "Base de cálculo", C_BASE),
    ("W", "Área constr.", C_ACONSTR),
    ("X", "Uso", C_USOCOD),
)

NUMEROS_CACHE_SEGUNDOS = 600

_SQL_NUMEROS = """
    SELECT COUNT(*),
           COALESCE(SUM(qualidade & 1 != 0), 0),
           COALESCE(SUM(qualidade & 2 != 0), 0),
           COALESCE(SUM(qualidade & 4 != 0), 0),
           COALESCE(SUM(qualidade & 8 != 0), 0),
           COALESCE(SUM(qualidade & 16 != 0), 0),
           COALESCE(SUM(qualidade & 32 != 0), 0),
           COALESCE(SUM(qualidade != 0), 0),
           COALESCE(SUM(rs_m2_construido IS NOT NULL), 0),
           COALESCE(SUM(bairro != '' AND bairro_norm = ''), 0),
           COALESCE(SUM(geo_nivel != '--'), 0),
           COALESCE(SUM(qualidade = 0 AND geo_nivel != '--'), 0)
      FROM radar_transacao
"""

_SQL_SETORES = """
    SELECT substr(sql, 1, 3), COUNT(*) FROM radar_transacao GROUP BY 1 ORDER BY 1
"""


@lru_cache(maxsize=1)
def transacao_exemplo():
    """A ``Transacao`` que a carga montaria com a linha de exemplo (não gravada)."""
    setor = f"{LINHA_EXEMPLO[C_SQL]:011d}"[:3]
    indices = geo_ref.indices_de_setor(setor)
    return _linha_para_transacao(LINHA_EXEMPLO, indices, 2026, 1)


def _numeros():
    with connection.cursor() as cur:
        cur.execute(_SQL_NUMEROS)
        (total, b1, b2, b4, b8, b16, b32, com_ressalva, com_rs_m2, bairro_lixo,
         com_ponto, com_ponto_sem_ressalva) = cur.fetchone()
        cur.execute(_SQL_SETORES)
        setores = cur.fetchall()

    por_mes = list(
        Transacao.objects.exclude(ano_guia=None).exclude(mes_guia=None)
        .values_list("ano_guia", "mes_guia").annotate(n=Count("id"))
        .order_by("ano_guia", "mes_guia")
    )
    por_geo = dict(Transacao.objects.values_list("geo_nivel").annotate(n=Count("id")))

    ultima = (
        CargaMensal.objects.filter(status=CargaMensal.CONCLUIDO)
        .exclude(terminado_em=None).order_by("-terminado_em").first()
    )
    carga = None
    if ultima:
        carga = {
            "lidas": ultima.linhas_lidas,
            "descartadas": ultima.linhas_descartadas,
            "pico_mb": ultima.pico_mb,
            "segundos": round((ultima.terminado_em - ultima.iniciado_em).total_seconds()),
        }

    return {
        "total": total,
        "por_bit": {1: b1, 2: b2, 4: b4, 8: b8, 16: b16, 32: b32},
        "com_ressalva": com_ressalva,
        "com_rs_m2": com_rs_m2,
        "bairro_lixo": bairro_lixo,
        "com_ponto": com_ponto,
        "com_ponto_sem_ressalva": com_ponto_sem_ressalva,
        "setores": setores,
        "por_mes": por_mes,
        "por_geo": por_geo,
        "carga": carga,
        "blocos": BLOCOS_PADRAO,
    }


def numeros_da_base():
    """Os números de cada etapa, lidos do banco. Só mudam quando uma carga roda,
    então ficam em cache por alguns minutos — são três varreduras da tabela."""
    return cache.get_or_set("como_funciona:numeros", _numeros, NUMEROS_CACHE_SEGUNDOS)
