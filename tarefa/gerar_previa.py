"""Gera site/previa.png, a imagem que aparece quando alguém compartilha o site.

Uso: python tarefa/gerar_previa.py   (precisa do Pillow; roda no PC, uma vez)
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LARGURA, ALTURA = 1200, 630
AZUL = (29, 79, 145)
AZUL_ESCURO = (23, 63, 117)
BOLA = (215, 240, 74)
BRANCO = (255, 255, 255)
FONTES_TITULO = ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTES_TEXTO = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def _fonte(caminhos, tamanho, variacao=None):
    from PIL import ImageFont
    for caminho in caminhos:
        if os.path.exists(caminho):
            fonte = ImageFont.truetype(caminho, tamanho)
            if variacao:
                try:
                    fonte.set_variation_by_name(variacao)
                except (OSError, ValueError, AttributeError):
                    pass
            return fonte
    return ImageFont.load_default(tamanho)


def gerar(destino: str) -> None:
    from PIL import Image, ImageDraw

    imagem = Image.new("RGB", (LARGURA, ALTURA), AZUL)
    desenho = ImageDraw.Draw(imagem)

    # quadra vista de cima, à direita, em linhas finas
    linhas = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    traco = ImageDraw.Draw(linhas)
    cor = (255, 255, 255, 70)
    x0, y0, x1, y1 = 720, 90, 1140, 540
    traco.rectangle([x0, y0, x1, y1], outline=cor, width=4)
    traco.line([x0, y0 + 55, x1, y0 + 55], fill=cor, width=3)
    traco.line([x0, y1 - 55, x1, y1 - 55], fill=cor, width=3)
    traco.line([x0 + 100, y0 + 55, x0 + 100, y1 - 55], fill=cor, width=3)
    traco.line([x1 - 100, y0 + 55, x1 - 100, y1 - 55], fill=cor, width=3)
    traco.line([x0 + 100, (y0 + y1) // 2, x1 - 100, (y0 + y1) // 2], fill=cor, width=3)
    for y in range(y0 - 20, y1 + 20, 18):
        traco.line([(x0 + x1) // 2, y, (x0 + x1) // 2, y + 9], fill=(255, 255, 255, 110), width=4)
    imagem.paste(linhas, (0, 0), linhas)

    # bola
    desenho.ellipse([960, 400, 1040, 480], fill=BOLA)
    desenho.arc([925, 395, 995, 485], start=300, end=60, fill=AZUL_ESCURO, width=5)
    desenho.arc([1005, 395, 1075, 485], start=120, end=240, fill=AZUL_ESCURO, width=5)

    # faixa amarela fina e textos
    desenho.rectangle([80, 120, 200, 130], fill=BOLA)
    titulo = _fonte(FONTES_TITULO, 112, "Bold Condensed")
    desenho.text((76, 170), "TÊNIS", font=titulo, fill=BRANCO)
    desenho.text((76, 290), "NOTÍCIAS", font=titulo, fill=BRANCO)
    texto = _fonte(FONTES_TEXTO, 34)
    desenho.text((80, 445), "Notícias do Brasil e do mundo,", font=texto, fill=(225, 233, 245))
    desenho.text((80, 490), "resumidas em português.", font=texto, fill=(225, 233, 245))

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    imagem.save(destino, "PNG", optimize=True)


if __name__ == "__main__":
    gerar(os.path.join(RAIZ, "site", "previa.png"))
    print("site/previa.png gerada")
    sys.exit(0)
