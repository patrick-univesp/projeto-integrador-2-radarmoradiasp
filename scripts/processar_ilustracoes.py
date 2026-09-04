"""Recorta a folha de ilustrações isométricas (11 peças em grade 4x3 sobre fundo
magenta) e exporta cada uma como WebP com fundo transparente, em 96/192/384 px.

Uso: venv/bin/python scripts/processar_ilustracoes.py tmp/img.png

Script de geração de asset, não roda em produção — mesma categoria do
cairosvg usado pra marca (CLAUDE.md). numpy é dependência ad-hoc, só do venv
de quem regenerar as ilustrações.

Fluxo, ver docs/local/prompt-ilustracoes.md §8:
  1. remove o magenta da folha inteira (chroma key com faixa de transição,
     despill de spill) de uma vez só
  2. acha os 11 componentes conexos do alfa na folha inteira e ordena em
     ordem de leitura — não recorta em 12 células de tamanho fixo, porque a
     peça nem sempre cabe dentro da célula "no papel" (ver recortes_por_
     componente: a primeira versão cortava o pé dos prédios da linha 1)
  3. centraliza cada peça num canvas quadrado, redimensiona pros 3 tamanhos,
     exporta WebP
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SLUGS = [
    "apartamento", "terreno", "casa", "loja", "industria", "garagem",
    "escritorio", "institucional", "oficina", "hotel-saude", "deposito",
]
GRID_COLS = 4  # só pra ordenar os componentes em ordem de leitura, ver main()
TAMANHOS = (96, 192, 384)
DESTINO = Path("static/img/uso")

# Faixa de "magenta-idade" (ver remover_magenta) que separa fundo de peça —
# não distância de cor bruta, que confundiria cinza-claro do prédio (perto do
# magenta em luminância) com fundo de verdade.
LIMIAR_BAIXO, LIMIAR_ALTO = 0.12, 0.45
MARGEM_AUTOCROP = 0.07  # 7% do lado maior da peça, de respiro no canvas quadrado


def remover_magenta(celula: np.ndarray, bg: np.ndarray) -> np.ndarray:
    """RGB (H,W,3) float0-255 -> RGBA (H,W,4) com o magenta removido.

    Magenta = R e B altos, G baixo. Em vez de distância de cor bruta (que
    reage à luminância e criava franja rosa em prédio cinza-claro, perto do
    magenta em brilho), mede só o "excesso de magenta" ``(R+B)/2 - G`` de
    cada pixel, igual à técnica de despill de chroma key verde/azul, com R e
    B como canais de tela em vez de G. Isso separa fundo de peça mesmo
    quando a peça é clara, e a supressão de spill zera o resíduo de cor sem
    precisar desmisturar pixel a pixel contra o fundo.
    """
    r, g, b = celula[..., 0], celula[..., 1], celula[..., 2]
    magentice = np.clip((r + b) / 2 - g, 0, None)
    magentice_bg = max((bg[0] + bg[2]) / 2 - bg[1], 1.0)

    alpha_fundo = np.clip((magentice / magentice_bg - LIMIAR_BAIXO) / (LIMIAR_ALTO - LIMIAR_BAIXO), 0, 1)
    alpha = 1 - alpha_fundo

    excesso = np.clip(magentice, 0, None)
    fg_r = np.clip(r - excesso, 0, 255)
    fg_b = np.clip(b - excesso, 0, 255)

    saida = np.zeros((*celula.shape[:2], 4), dtype=np.uint8)
    saida[..., 0] = fg_r.astype(np.uint8)
    saida[..., 1] = g.astype(np.uint8)
    saida[..., 2] = fg_b.astype(np.uint8)
    saida[..., 3] = (alpha * 255).astype(np.uint8)
    return saida


def recortes_por_componente(rgba: np.ndarray, n_esperado: int):
    """Bounding box de cada componente conexo do alfa na folha inteira, em
    ordem de leitura (linha, depois coluna) — não a grade 4x3 nominal.

    A primeira versão recortava a folha em 12 células de tamanho fixo antes
    de remover o magenta, e várias peças da linha 1 têm o pé (base do prédio)
    abaixo da fronteira teórica da célula — a grade "no papel" não bate com
    onde o modelo realmente desenhou cada peça, e o corte cortava o pé.
    Achar os componentes na imagem inteira usa a extensão real de cada peça,
    não uma suposição de grade.
    """
    mascara = rgba[..., 3] > 40
    rotulos, n = ndimage.label(mascara)
    if n != n_esperado:
        raise ValueError(f"esperava {n_esperado} componentes, achou {n} — folha mudou?")

    caixas = ndimage.find_objects(rotulos)
    centros_y = [ (c[0].start + c[0].stop) / 2 for c in caixas ]
    ordem_linha = np.argsort(centros_y)

    linhas_por_ordem = [GRID_COLS, GRID_COLS, n_esperado - 2 * GRID_COLS]
    peca_por_linha = []
    cursor = 0
    for tamanho_linha in linhas_por_ordem:
        indices = ordem_linha[cursor:cursor + tamanho_linha]
        indices = sorted(indices, key=lambda i: (caixas[i][1].start + caixas[i][1].stop) / 2)
        peca_por_linha += indices
        cursor += tamanho_linha

    return [rgba[caixas[i]] for i in peca_por_linha]


def centralizar_em_canvas_quadrado(peca: Image.Image) -> Image.Image:
    lado = int(round(max(peca.size) * (1 + MARGEM_AUTOCROP * 2)))
    canvas = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    x = (lado - peca.width) // 2
    y = (lado - peca.height) // 2
    canvas.paste(peca, (x, y), peca)
    return canvas


def main():
    origem = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tmp/img.png")
    folha = Image.open(origem).convert("RGB")
    bg = np.array(folha.getpixel((2, 2)), dtype=np.float64)
    folha_np = np.array(folha, dtype=np.float64)

    rgba_folha = remover_magenta(folha_np, bg)
    pecas = recortes_por_componente(rgba_folha, len(SLUGS))

    DESTINO.mkdir(parents=True, exist_ok=True)
    for slug, rgba in zip(SLUGS, pecas, strict=True):
        peca = Image.fromarray(rgba, mode="RGBA")
        quadro = centralizar_em_canvas_quadrado(peca)

        for tamanho in TAMANHOS:
            redimensionada = quadro.resize((tamanho, tamanho), Image.LANCZOS)
            caminho = DESTINO / f"{slug}-{tamanho}.webp"
            redimensionada.save(caminho, "WEBP", quality=88, method=6)
            print(f"{caminho} ({caminho.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
