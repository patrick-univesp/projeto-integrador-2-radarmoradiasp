"""Regras de mineração portadas do pipeline de referência (``tmp/ITBI``).

Recebem os campos crus já coeridos (``radar/carga/coercao.py``) e devolvem os
derivados. Mudar uma regra aqui obriga a recarregar o banco. Detalhe e casos
reais: ``docs/carga-mineracao.md``.
"""

import datetime as dt
import re
import unicodedata

ALIQUOTA_ITBI = 0.03
ANO_BASE = 2026
PROPORCAO_MIN_METRICA = 99.0
FRACAO_MIN_TERRENO = 0.99
PROPORCAO_MIN_AGIO = 5.0
PROPORCAO_PEQUENA = 5.0

_GRUPOS_USO = {
    "Terreno": (0,),
    "Casa / residência horizontal": (10, 12, 13, 14),
    "Apartamento / res. vertical": (20, 21, 22, 25),
    "Garagem": (23, 24, 62, 63),
    "Escritório / consultório": (30, 31, 32),
    "Loja / comércio": (40, 41, 42, 43),
    "Indústria / armazém": (50, 51),
    "Oficina / serviços": (60, 61, 64),
    "Institucional": (70, 71, 72, 74, 83),
    "Hotel / saúde / especial": (80, 81, 82, 84, 85),
    "Depósito": (26,),
}
_USO_PARA_GRUPO = {c: g for g, cs in _GRUPOS_USO.items() for c in cs}
GRUPO_OUTROS = "Outros"

_PROGRAMAS_HABITACIONAIS = (
    "MINHA CASA MINHA VIDA",
    "CASA VERDE E AMARELA",
    "SFH",
    "SISTEMA FINANCEIRO DE HABITACAO",
)
_USOS_CADASTRO_FRACO = frozenset((0, 70, 71, 72, 73, 74, 83))


def _razao(a, b):
    """``a / b``, ou ``None`` se algum lado é nulo ou não-positivo. Sem
    numerador positivo não há preço a calcular (base de cálculo zerada é linha
    defeituosa, não R$ 0/m²); um zero aqui contaminaria a mediana da tela."""
    if a is None or b is None or a <= 0 or b <= 0:
        return None
    return a / b


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).upper()


def grupo_de_uso(uso_cod) -> str:
    """Código ``uso`` do IPTU → grupo legível. Código desconhecido (a planilha
    tem ``73`` e ``91``, fora da Tabela de USOS) → ``"Outros"``."""
    if uso_cod is None:
        return GRUPO_OUTROS
    try:
        return _USO_PARA_GRUPO.get(int(uso_cod), GRUPO_OUTROS)
    except (TypeError, ValueError):
        return GRUPO_OUTROS


def rs_m2_construido(base_calculo, area_construida, proporcao):
    """R$/m² construído. ``None`` (nunca ``0``) quando a proporção transmitida é
    parcial ou a área construída é zero (terreno)."""
    if proporcao is None or proporcao < PROPORCAO_MIN_METRICA:
        return None
    return _razao(base_calculo, area_construida)


def rs_m2_terreno(base_calculo, area_terreno, proporcao, fracao_ideal):
    """R$/m² de terreno. Exige também ``fracao_ideal ≥ 0,99`` — num apartamento a
    área do lote é a do condomínio inteiro."""
    if proporcao is None or proporcao < PROPORCAO_MIN_METRICA:
        return None
    if fracao_ideal is None or fracao_ideal < FRACAO_MIN_TERRENO:
        return None
    return _razao(base_calculo, area_terreno)


def agio(valor_transacao, vvr_proporcional, proporcao):
    """Quanto o declarado passou da referência da Prefeitura. Só com
    ``proporcao ≥ 5%`` — abaixo disso a razão vira lixo."""
    if proporcao is None or proporcao < PROPORCAO_MIN_AGIO:
        return None
    return _razao(valor_transacao, vvr_proporcional)


def itbi_estimado(base_calculo):
    """Alíquota nominal de 3%, sem isenções nem alíquota reduzida."""
    if base_calculo is None:
        return None
    return base_calculo * ALIQUOTA_ITBI


def cod_natureza(texto):
    """``'1.Compra e venda'`` → ``1``; ``None`` se não casar."""
    if not texto:
        return None
    m = re.match(r"\s*(\d+)\s*\.", str(texto))
    return int(m.group(1)) if m else None


def idade(acc):
    """Anos desde o término da construção (``acc``); ``None`` se vazio ou
    implausível."""
    if acc is None:
        return None
    ano = int(acc)
    if ano <= 1000 or ano > ANO_BASE:
        return None
    return ANO_BASE - ano


def linha_deslocada(situacao_sql_bruto, tipo_financiamento_bruto) -> bool:
    """Colunas escorregaram na planilha: campos de texto vieram como data ou
    número."""
    if isinstance(situacao_sql_bruto, (dt.datetime, dt.date)):
        return True
    if isinstance(situacao_sql_bruto, (int, float)) and not isinstance(situacao_sql_bruto, bool):
        return True
    return isinstance(tipo_financiamento_bruto, (int, float)) and not isinstance(
        tipo_financiamento_bruto, bool
    )


def valor_inconsistente(base_calculo, valor_transacao, vvr_proporcional) -> bool:
    """A planilha define ``base = max(declarado, VVR proporcional)``. Em algumas
    linhas isso não fecha — quase todas com base zerada apesar de valor
    declarado."""
    esperada = max(valor_transacao or 0, vvr_proporcional or 0)
    atual = base_calculo if base_calculo is not None else -1
    return abs(atual - esperada) > 1


def qualidade(deslocada, inconsistente) -> int:
    """0 ok · 1 colunas deslocadas · 2 valores que não fecham · 3 os dois.
    ``≠ 0`` sai do cálculo por padrão."""
    return int(bool(deslocada)) + 2 * int(bool(inconsistente))


def cadastro_defasado(natureza, tipo_financiamento, proporcao, uso_cod) -> bool:
    """``True`` quando o cadastro do IPTU não acompanhou a realidade: compra e
    venda, financiamento habitacional, proporção pequena e ``uso`` de terreno ou
    institucional. Não reclassifica nada — só marca."""
    if cod_natureza(natureza) != 1:
        return False
    fin = _sem_acento(str(tipo_financiamento or ""))
    if not any(p in fin for p in _PROGRAMAS_HABITACIONAIS):
        return False
    if proporcao is None or proporcao >= PROPORCAO_PEQUENA:
        return False
    try:
        return int(uso_cod) in _USOS_CADASTRO_FRACO
    except (TypeError, ValueError):
        return False


def ano_transacao(data):
    return data.year if data is not None else None


def mes_transacao(data):
    return data.month if data is not None else None
