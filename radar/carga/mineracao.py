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

# Abaixo disso o valor declarado é taxa/parcela/emolumento, não o preço do
# negócio — auditoria da base real encontrou linhas de R$ 0,01 a R$ 1,00 que
# passavam como qualidade=0 porque o Valor Venal de Referência "fechava" a
# base de cálculo mesmo com o declarado simbólico.
VALOR_TRANSACAO_MINIMO = 1000

# Faixa de anos plausível para a data do negócio. A base real observada vai de
# 1994 a 2026 sem problema (contrato de gaveta regularizado tardiamente é
# legítimo) — o teto/piso aqui é só para pegar erro de digitação óbvio
# (ex.: "2099"), não para reclassificar dado real já visto.
ANO_TRANSACAO_MINIMO = 1990
ANO_TRANSACAO_MAXIMO = ANO_BASE

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


# Status de "Situação do SQL" (normalizados por _sem_acento) em que a Prefeitura
# não reconhece mais o cadastro — uso/área/padrão da linha não valem. "Cancelado
# Territorial" fica de fora: quase sempre é lote-mãe subdividido pra empreendimento
# novo (venda legítima de lançamento), e terreno já não entra na mediana.
_SITUACAO_SQL_INVALIDA = frozenset(("CANCELADO PREDIAL", "NAO_EXISTE_EXERCICIO"))


def situacao_sql_invalida(situacao_sql) -> bool:
    """``True`` para "Cancelado Predial" e "Não_Existe_Exercício" — ver ``_SITUACAO_SQL_INVALIDA``."""
    return _sem_acento(str(situacao_sql or "")).strip() in _SITUACAO_SQL_INVALIDA


def valor_inconsistente(base_calculo, valor_transacao, vvr_proporcional) -> bool:
    """A planilha define ``base = max(declarado, VVR proporcional)``. Em algumas
    linhas isso não fecha — quase todas com base zerada apesar de valor
    declarado."""
    esperada = max(valor_transacao or 0, vvr_proporcional or 0)
    atual = base_calculo if base_calculo is not None else -1
    return abs(atual - esperada) > 1


def valor_irrisorio(valor_transacao) -> bool:
    """``True`` quando o valor declarado é simbólico (taxa/parcela/emolumento
    digitado no campo do imóvel) — mesmo que o Valor Venal de Referência tenha
    "corrigido" a base de cálculo depois, o valor de origem já denuncia a
    linha. Achado real: R$ 0,01 e R$ 1,00 passando como boas."""
    return valor_transacao is not None and valor_transacao < VALOR_TRANSACAO_MINIMO


def financiamento_incompativel(valor_transacao, valor_financiado) -> bool:
    """``True`` quando o banco financiou mais do que o comprador declarou ter
    pago — o declarado não é o preço do negócio (mesmo sintoma do
    ``valor_irrisorio``, capturável mesmo sem VVR baixo o bastante pra marcar
    ``inconsistente``)."""
    if not valor_transacao or not valor_financiado:
        return False
    return valor_financiado > valor_transacao


def data_implausivel(data_transacao) -> bool:
    """``True`` só para erro de digitação óbvio (ano fora de 1990–ano da
    carga) — não para contrato antigo regularizado tardiamente, que é
    legítimo e já visto na base real (mais antigo: 1994)."""
    if data_transacao is None:
        return False
    return not (ANO_TRANSACAO_MINIMO <= data_transacao.year <= ANO_TRANSACAO_MAXIMO)


def qualidade(deslocada, inconsistente, irrisorio=False, financiamento_ruim=False,
              data_ruim=False, sql_ruim=False) -> int:
    """Bitmask: 1 colunas deslocadas · 2 valores que não fecham · 4 valor
    irrisório · 8 financiamento maior que o declarado · 16 data implausível ·
    32 registro cadastral do SQL cancelado/inexistente.
    0 é bom; ``!= 0`` sai do cálculo por padrão."""
    return (
        int(bool(deslocada))
        + 2 * int(bool(inconsistente))
        + 4 * int(bool(irrisorio))
        + 8 * int(bool(financiamento_ruim))
        + 16 * int(bool(data_ruim))
        + 32 * int(bool(sql_ruim))
    )


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
