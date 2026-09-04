"""Adapta os 11 glifos de uso_grupo (#18) a partir de ícones prontos da Tabler
Icons (MIT, https://tabler.io/icons) em vez de desenhar do zero — pedido do
Patrick depois de ver a primeira leva desenhada à mão.

Cada arquivo de origem é baixado uma vez do pacote outline oficial:
  https://raw.githubusercontent.com/tabler/tabler-icons/main/icons/outline/<nome>.svg
e salvo em ORIGEM antes de rodar este script (curl simples, sem dependência
de rede no momento de gerar o asset final — mesma postura do
processar_ilustracoes.py, que também parte de um arquivo já baixado).

Uso: venv/bin/python scripts/adaptar_icones_uso.py

Ajuste feito em cada SVG: remove o comentário de metadata da Tabler, tira
`width`/`height` fixos (o viewBox já define a proporção, quem usa o ícone
controla o tamanho de exibição), e troca `stroke="currentColor"` pela cor
baked `#62554D` (--text-2, tokens.css) — `<img src="...">` não herda
`currentColor` do CSS da página que o referencia, só um `<svg>` inline
herdaria.
"""

import re
from pathlib import Path

ORIGEM = Path("/tmp/claude-1001/-home-patrick-Downloads-UNIVESP-PI2/c29c6c9b-4a6f-4a46-94c7-c2176dc17648/scratchpad/tabler")
DESTINO = Path("static/img/uso")
COR_TRACO = "#62554D"

# slug (#18) -> nome do ícone Tabler outline
MAPA = {
    "apartamento": "building",
    "terreno": "fence",
    "casa": "building-cottage",
    "loja": "building-store",
    "industria": "building-warehouse",
    "garagem": "car-garage",
    "escritorio": "building-skyscraper",
    "institucional": "building-bank",
    "oficina": "tool",
    "hotel-saude": "building-hospital",
    "deposito": "package",
}


def main():
    for slug, nome_tabler in MAPA.items():
        svg = (ORIGEM / f"{nome_tabler}.svg").read_text()
        svg = re.sub(r"<!--.*?-->\s*", "", svg, flags=re.DOTALL)
        svg = svg.replace('width="24"\n  height="24"\n  ', "")
        svg = svg.replace('stroke="currentColor"', f'stroke="{COR_TRACO}"')
        svg = svg.replace("<svg\n", '<svg role="img" aria-hidden="true"\n', 1)

        caminho = DESTINO / f"{slug}.svg"
        caminho.write_text(svg)
        print(f"{caminho} <- tabler/{nome_tabler}.svg ({caminho.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
