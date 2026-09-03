"""Converte valores crus de célula de planilha para tipos Python.

Uma célula do ``openpyxl`` chega como ``int``, ``float``, ``str``, ``datetime``
ou ``None``.
"""

import datetime as dt
import re

_MESES = {
    "JAN": 1, "FEV": 2, "MAR": 3, "ABR": 4, "MAI": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SET": 9, "OUT": 10, "NOV": 11, "DEZ": 12,
}
_ABA_RE = re.compile(r"^[A-Z]{3}-\d{4}$")


def para_texto(v) -> str:
    """Texto sem espaços nas pontas; ``''`` para vazio/``None``."""
    if v is None:
        return ""
    return str(v).strip()


def para_numero(v) -> float | None:
    """``float`` ou ``None``. Aceita número no formato brasileiro em texto
    (``'1.234,56'`` → ``1234.56``)."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(".", "").replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def para_sql(v) -> str | None:
    """Número do Cadastro (SQL) em 11 dígitos, com zero à esquerda reconstruído
    (a planilha traz como ``int``: ``5202800061`` é ``05202800061``). ``None``
    se não for só dígitos."""
    if v is None:
        return None
    if isinstance(v, float):
        v = int(v)
    s = str(v).strip()
    return s.zfill(11) if s.isdigit() else None


def para_cep(v) -> str:
    """CEP como 8 dígitos, zero à esquerda reconstruído; ``''`` se vazio ou 0."""
    n = para_numero(v)
    if n is None or n <= 0:
        return ""
    return str(int(n)).zfill(8)


def para_numero_porta(v) -> str:
    """Número de porta como texto, sem zeros à esquerda. ``0`` e ``99999`` são
    os códigos de "sem numeração" → ``''``. Preserva número com letra."""
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    try:
        n = int(float(s.replace(".", "").replace(",", ".")))
    except ValueError:
        return s.lstrip("0") or s
    return "" if n in (0, 99999) else str(n)


def para_data(v) -> dt.date | None:
    """``date`` ou ``None``. No ``.xlsx`` a data já vem como ``datetime``."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def mes_guia(nome_aba: str) -> int | None:
    """``'MAR-2026'`` → ``3``. É o mês do pagamento da guia, não o do negócio."""
    if not nome_aba:
        return None
    aba = nome_aba.strip().upper()
    return _MESES.get(aba[:3]) if _ABA_RE.match(aba) else None
