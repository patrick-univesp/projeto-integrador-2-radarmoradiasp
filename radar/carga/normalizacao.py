"""Normalização de bairro e logradouro para busca.

Substitui o que o PostgreSQL daria de graça (``unaccent``, ``pg_trgm``): como o
banco é SQLite, a normalização acontece na carga e o autocomplete roda sobre a
lista de bairros já normalizados. Detalhe: ``docs/carga-mineracao.md``.
"""

import re
import unicodedata

from radar.carga.grafias_bairro import GRAFIAS

_ABREVIACOES = {
    "R": "RUA", "AV": "AVENIDA", "AL": "ALAMEDA", "PC": "PRACA", "PR": "PRACA",
    "TV": "TRAVESSA", "ESTR": "ESTRADA", "LGO": "LARGO", "VD": "VIADUTO",
    "ROD": "RODOVIA",
    "VL": "VILA", "JD": "JARDIM", "JDN": "JARDIM", "PQ": "PARQUE",
    "PRQ": "PARQUE", "STO": "SANTO", "STA": "SANTA", "CID": "CIDADE",
    "CD": "CIDADE", "CJ": "CONJUNTO", "CONJ": "CONJUNTO", "CH": "CHACARA",
    "CHAC": "CHACARA", "RES": "RESIDENCIAL", "NS": "NOSSA SENHORA",
}

# "bairro" que na verdade é complemento (torre, subsolo, bloco, vaga, sala…):
# ~8% das linhas preenchidas. Ancorada — nenhum bairro real casa.
_LIXO_BAIRRO = re.compile(
    r"^("
    r"TORRE\s*[0-9IVX]+|TORRE\s+[A-Z]\d?|BLOCOS?\s*[A-Z]?\d+|BL\s*\d+|"
    r"\d+\s*(SUBSOLO|SUB\s+SOLO|SS|DP|DORM|VG|VGS|VAGAS?|ANDAR|PAV|PAVTO|PISO)|"
    r"(SUBSOLO|SUB\s+SOLO|SS|SL|TERREO|MEZANINO|COBERTURA|LOJA|SALA|GARAGEM|DEPOSITO)\s*\d*|"
    r"E\s+\d+\s*(VGS?|DP)|AP(TO)?\s*\d+|CASA\s*\d*|LOTE\s*\d+|QUADRA\s*[A-Z0-9]+"
    r")$"
)


def _basico(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c)).upper()
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    t = " ".join(t.split())
    return " ".join(_ABREVIACOES.get(p, p) for p in t.split()) if t else ""


def normalizar(texto) -> str:
    """``'Itaim Bibi'`` → ``'ITAIM BIBI'``; ``'ITAIMBIBI'`` → ``'ITAIM BIBI'``;
    ``'R Sen Otavio'`` → ``'RUA SEN OTAVIO'``. ``''`` para vazio."""
    if texto is None:
        return ""
    base = _basico(str(texto))
    return GRAFIAS.get(base, base) if base else ""


def eh_lixo_de_bairro(texto_normalizado: str) -> bool:
    """``True`` quando o valor normalizado é, na verdade, complemento."""
    return bool(texto_normalizado) and bool(_LIXO_BAIRRO.match(texto_normalizado))


def normalizar_bairro(texto) -> str:
    """``normalizar`` + descarte do lixo de complemento. É o que a carga grava
    em ``bairro_norm`` (sem tocar no ``bairro`` cru)."""
    n = normalizar(texto)
    return "" if eh_lixo_de_bairro(n) else n
