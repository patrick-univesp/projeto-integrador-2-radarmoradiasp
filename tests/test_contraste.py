"""Contraste WCAG AA calculado a partir de `static/css/tokens.css`.

`--text-3` já reprovou contraste duas vezes nesta base (ver `docs/local/interface.md`
§2) porque a verificação era sempre manual — a própria doc pede um teste que calcule
os pares críticos a partir do token, em vez de conferir a olho depois de cada ajuste.
"""

import re
from pathlib import Path

import pytest

TOKENS = Path("static/css/tokens.css").read_text()


def _hex_de(token):
    """Primeira declaração hex de `--token` no arquivo (a segunda, oklch, não
    tem `#` e não entra no regex — "primeira vence" já é a certa)."""
    m = re.search(rf"--{re.escape(token)}:\s*(#[0-9A-Fa-f]{{6}})", TOKENS)
    assert m, f"token --{token} não encontrado em tokens.css"
    return m.group(1)


def _luminancia_relativa(hex_cor):
    """WCAG 2.x: https://www.w3.org/TR/WCAG21/#dfn-relative-luminance"""
    hex_cor = hex_cor.lstrip("#")
    r, g, b = (int(hex_cor[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def canal(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = canal(r), canal(g), canal(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(token_a, token_b):
    la, lb = _luminancia_relativa(_hex_de(token_a)), _luminancia_relativa(_hex_de(token_b))
    claro, escuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (escuro + 0.05)


# Texto normal (<18,66px em negrito, <24px normal): AA exige 4,5:1.
TEXTO_AA = 4.5
# Texto grande, ou indicador de UI não-textual (WCAG 1.4.11, ex.: anel de foco,
# borda de aviso): AA exige 3:1.
UI_AA = 3.0

SUPERFICIES = ("bg", "surface", "surface-2", "surface-3")


@pytest.mark.parametrize("superficie", SUPERFICIES)
@pytest.mark.parametrize("texto", ["text", "text-2", "text-3"])
def test_texto_sobre_superficie_passa_aa(texto, superficie):
    assert contraste(texto, superficie) >= TEXTO_AA, f"--{texto} sobre --{superficie}"


def test_accent_ink_sobre_bg_e_accent_soft_passa_aa():
    """`--accent-ink` é a cor de link/texto de ação (ex.: "Comparar com outra região")."""
    assert contraste("accent-ink", "bg") >= TEXTO_AA
    assert contraste("accent-ink", "accent-soft") >= TEXTO_AA


def test_accent_on_sobre_accent_passa_aa():
    """Texto branco de botão (`.busca__botao`) sobre o preenchimento `--accent`."""
    assert contraste("accent-on", "accent") >= TEXTO_AA


@pytest.mark.parametrize("superficie", ["bg", "surface"])
def test_anel_de_foco_passa_ui_aa(superficie):
    """`--accent-line` é o anel de foco de teclado — WCAG 1.4.11, não é texto."""
    assert contraste("accent-line", superficie) >= UI_AA


@pytest.mark.parametrize(("tinta", "suave", "linha"), [
    ("erro", "erro-suave", "erro-linha"),
    ("aviso", "aviso-suave", "aviso-linha"),
])
def test_estado_erro_e_aviso_passa_aa(tinta, suave, linha):
    assert contraste(tinta, "bg") >= TEXTO_AA, f"--{tinta} sobre --bg"
    assert contraste(tinta, suave) >= TEXTO_AA, f"--{tinta} sobre --{suave}"
    assert contraste(linha, "bg") >= UI_AA, f"--{linha} sobre --bg (borda)"
    assert contraste(linha, suave) >= UI_AA, f"--{linha} sobre --{suave} (borda)"


@pytest.mark.parametrize("degrau", ["r1", "r2", "r3", "r4"])
def test_rampa_de_magnitude_com_tinta_escura_passa_aa(degrau):
    """r1–r4 usam `--r-ink-baixo` (escura) por cima — r5 é o único degrau
    escuro o bastante para precisar de tinta branca (`--r-ink-alto`)."""
    assert contraste("text", degrau) >= TEXTO_AA, f"--text sobre --{degrau}"


def test_rampa_r5_com_tinta_clara_passa_aa():
    assert contraste("r-ink-alto", "r5") >= TEXTO_AA
