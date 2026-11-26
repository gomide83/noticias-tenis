"""Gera o kit de divulgação do Tênis Notícias para o YouTube.

Cria em divulgacao/youtube/:
  - short-tenis-noticias.mp4  vídeo em pé (1080x1920), uns 21 segundos, sem som
  - capa-do-canal.png         2560x1440 (o texto fica na área que aparece em todos os aparelhos)
  - foto-de-perfil.png        800x800 (o YouTube mostra em círculo)

O vídeo mostra o top 3 dos rankings ATP e WTA salvos em dados/ pelo site.
Uso: python divulgacao/gerar_youtube.py   (precisa de Pillow e imageio-ffmpeg; roda no PC)
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAIDA = os.path.join(RAIZ, "divulgacao", "youtube")
URL_LINHAS = ("gomide83.github.io", "/noticias-tenis")

AZUL = (29, 79, 145)
AZUL_ESCURO = (16, 45, 85)
BOLA = (215, 240, 74)
BOLA_TEXTO = (31, 42, 5)
BRANCO = (255, 255, 255)
CLARO = (225, 233, 245)
BRASILIA = timezone(timedelta(hours=-3))
FONTES_TITULO = ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
FONTES_TEXTO = ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
FONTES_TEXTO_FORTE = ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
                      "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


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


def titulo(tamanho):
    return _fonte(FONTES_TITULO, tamanho, "Bold Condensed")


def texto(tamanho, forte=False):
    return _fonte(FONTES_TEXTO_FORTE if forte else FONTES_TEXTO, tamanho)


def _pontos(valor) -> str:
    return f"{int(valor or 0):,}".replace(",", ".")


def top3(ranking: dict) -> list:
    jogadores = sorted(ranking.get("jogadores") or [], key=lambda j: j["posicao"])[:3]
    return [(int(j["posicao"]), str(j["nome"]), _pontos(j.get("pontos"))) for j in jogadores]


def _data(ranking: dict) -> str:
    try:
        quando = datetime.strptime(ranking["atualizadoEm"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return quando.astimezone(BRASILIA).strftime("%d/%m/%Y")
    except (KeyError, TypeError, ValueError):
        return ""


# ---------- desenhos ----------

def desenhar_bola(desenho, cx, cy, raio):
    desenho.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], fill=BOLA)
    largura = max(3, raio // 9)
    desenho.arc([cx - raio * 1.85, cy - raio * 1.1, cx - raio * 0.15, cy + raio * 1.1],
                start=308, end=52, fill=AZUL_ESCURO, width=largura)
    desenho.arc([cx + raio * 0.15, cy - raio * 1.1, cx + raio * 1.85, cy + raio * 1.1],
                start=128, end=232, fill=AZUL_ESCURO, width=largura)


def _quadra_vertical(largura, altura, opacidade=64):
    """Quadra vista de cima, em pé, em linhas finas brancas."""
    from PIL import Image, ImageDraw
    camada = Image.new("RGBA", (largura, altura), (0, 0, 0, 0))
    traco = ImageDraw.Draw(camada)
    cor = (255, 255, 255, opacidade)
    x0, x1 = int(largura * 0.12), int(largura * 0.88)
    y0, y1 = int(altura * 0.36), int(altura * 1.12)
    corredor = int((x1 - x0) * 0.12)
    meio = (y0 + y1) // 2
    saque = int((y1 - y0) * 0.27)
    traco.rectangle([x0, y0, x1, y1], outline=cor, width=6)
    traco.line([x0 + corredor, y0, x0 + corredor, y1], fill=cor, width=4)
    traco.line([x1 - corredor, y0, x1 - corredor, y1], fill=cor, width=4)
    traco.line([x0 + corredor, meio - saque, x1 - corredor, meio - saque], fill=cor, width=4)
    traco.line([x0 + corredor, meio + saque, x1 - corredor, meio + saque], fill=cor, width=4)
    traco.line([(x0 + x1) // 2, meio - saque, (x0 + x1) // 2, meio + saque], fill=cor, width=4)
    for x in range(x0 - 30, x1 + 30, 26):  # rede tracejada
        traco.line([x, meio, x + 13, meio], fill=(255, 255, 255, opacidade + 20), width=5)
    return camada


def _fundo_video():
    from PIL import Image
    fundo = Image.new("RGBA", (1080, 1920), AZUL + (255,))
    # leve degradê para o rodapé
    from PIL import ImageDraw
    desenho = ImageDraw.Draw(fundo)
    for y in range(1200, 1920, 4):
        t = (y - 1200) / 720
        cor = tuple(int(a + (b - a) * t) for a, b in zip(AZUL, AZUL_ESCURO))
        desenho.rectangle([0, y, 1080, y + 4], fill=cor + (255,))
    fundo.alpha_composite(_quadra_vertical(1080, 1920))
    return fundo


def _bloco(linhas, largura=1080):
    """Desenha um bloco de linhas centralizadas e devolve (imagem RGBA recortada, altura).

    linhas: lista de (texto, fonte, cor) ou ("faixa", texto, fonte) para a pílula amarela.
    """
    from PIL import Image, ImageDraw
    rascunho = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    medidas, total = [], 0
    for linha in linhas:
        if linha[0] == "espaco":
            medidas.append(linha[1])
            total += linha[1]
            continue
        texto_linha, fonte = (linha[1], linha[2]) if linha[0] == "faixa" else (linha[0], linha[1])
        caixa = rascunho.textbbox((0, 0), texto_linha, font=fonte)
        altura = caixa[3] - caixa[1] + (40 if linha[0] == "faixa" else 18)
        medidas.append(altura)
        total += altura
    imagem = Image.new("RGBA", (largura, total + 20), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    y = 0
    for linha, altura in zip(linhas, medidas):
        if linha[0] == "espaco":
            y += altura
            continue
        if linha[0] == "faixa":
            _, texto_linha, fonte = linha
            caixa = desenho.textbbox((0, 0), texto_linha, font=fonte)
            w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
            x = (largura - w) // 2
            desenho.rounded_rectangle([x - 34, y, x + w + 34, y + h + 30], radius=(h + 30) // 2, fill=BOLA)
            desenho.text((x - caixa[0], y + 15 - caixa[1]), texto_linha, font=fonte, fill=BOLA_TEXTO)
        else:
            texto_linha, fonte, cor = linha
            caixa = desenho.textbbox((0, 0), texto_linha, font=fonte)
            x = (largura - (caixa[2] - caixa[0])) // 2 - caixa[0]
            desenho.text((x, y - caixa[1]), texto_linha, font=fonte, fill=cor)
        y += altura
    return imagem


def _bloco_ranking(nome, ranking):
    from PIL import Image, ImageDraw
    linhas = top3(ranking)
    largura, altura_linha = 900, 170
    imagem = Image.new("RGBA", (1080, 210 + altura_linha * len(linhas) + 90), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(imagem)
    cabecalho = _bloco([("faixa", nome, titulo(84))])
    imagem.alpha_composite(cabecalho, (0, 0))
    x0 = (1080 - largura) // 2
    y = 200
    for posicao, jogador, pontos in linhas:
        desenho.rounded_rectangle([x0, y, x0 + largura, y + altura_linha - 22], radius=26,
                                  fill=(16, 45, 85, 215))
        desenho.text((x0 + 40, y + 18), f"{posicao}º", font=titulo(104), fill=BOLA)
        desenho.text((x0 + 190, y + 18), jogador, font=texto(54, forte=True), fill=BRANCO)
        desenho.text((x0 + 190, y + 86), f"{pontos} pontos", font=texto(40), fill=CLARO)
        y += altura_linha
    data = _data(ranking)
    if data:
        legenda = f"Ranking de {data}"
        caixa = desenho.textbbox((0, 0), legenda, font=texto(36))
        desenho.text(((1080 - (caixa[2] - caixa[0])) // 2, y + 12), legenda, font=texto(36), fill=CLARO)
    return imagem


# ---------- vídeo ----------

def _suave(t):
    return 1 - (1 - t) ** 3


def cenas(ranking_atp, ranking_wta):
    """Lista de cenas: (início, fim, [(bloco RGBA, y do topo)], mostra_bola)."""
    nome = _bloco([("TÊNIS", titulo(250), BRANCO), ("NOTÍCIAS", titulo(250), BRANCO)])
    return [
        (0.0, 3.6, [(nome, 640)], True),
        (3.6, 7.2, [(_bloco([("Notícias de tênis", titulo(120), BRANCO),
                            ("do Brasil e do mundo", titulo(120), BRANCO),
                            ("espaco", 40),
                            ("faixa", "EM PORTUGUÊS", titulo(90))]), 640)], False),
        (7.2, 10.6, [(_bloco([("Atualizado a cada", titulo(120), BRANCO),
                             ("30 minutos", titulo(220), BOLA),
                             ("espaco", 30),
                             ("ATP • WTA • Brasileiros • Grand Slams", texto(42, forte=True), CLARO)]), 620)], False),
        (10.6, 14.2, [(_bloco_ranking("RANKING ATP", ranking_atp), 520)], False),
        (14.2, 17.8, [(_bloco_ranking("RANKING WTA", ranking_wta), 520)], False),
        (17.8, 21.5, [(_bloco([("Acompanhe em", titulo(110), BRANCO),
                              ("espaco", 30),
                              (URL_LINHAS[0], titulo(112), BOLA),
                              (URL_LINHAS[1], titulo(112), BOLA),
                              ("espaco", 50),
                              ("Link na descrição", texto(46, forte=True), CLARO)]), 600)], True),
    ]


def _com_alfa(bloco, alfa):
    if alfa >= 0.999:
        return bloco
    camada = bloco.copy()
    camada.putalpha(bloco.getchannel("A").point(lambda v: int(v * alfa)))
    return camada


def quadro(fundo, lista_cenas, t):
    from PIL import ImageDraw
    imagem = fundo.copy()
    for indice, (inicio, fim, blocos, bola) in enumerate(lista_cenas):
        if not inicio <= t < fim:
            continue
        ultima = indice == len(lista_cenas) - 1
        dentro = t - inicio
        entrada = min(1.0, dentro / 0.45)
        saida = 1.0 if ultima else min(1.0, (fim - t) / 0.3)
        alfa = _suave(entrada) * saida
        deslocamento = int((1 - _suave(entrada)) * 70)
        for bloco, y in blocos:
            imagem.alpha_composite(_com_alfa(bloco, alfa), (0, y + deslocamento))
        if bola:
            desenho = ImageDraw.Draw(imagem)
            queda = min(1.0, dentro / 1.1)
            altura = abs(math.cos(queda * math.pi * 1.5)) * (1 - queda) * 420
            desenhar_bola(desenho, 820, int(470 - altura), 62)
    return imagem.convert("RGB")


def gerar_video(destino: str, ranking_atp: dict, ranking_wta: dict, fps: int = 30) -> None:
    import imageio_ffmpeg
    lista = cenas(ranking_atp, ranking_wta)
    duracao = lista[-1][1]
    fundo = _fundo_video()
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    escritor = imageio_ffmpeg.write_frames(
        destino, (1080, 1920), fps=fps, codec="libx264", pix_fmt_in="rgb24", quality=None,
        pix_fmt_out="yuv420p", output_params=["-crf", "20", "-preset", "medium", "-movflags", "+faststart"],
        macro_block_size=1)
    escritor.send(None)
    for n in range(int(duracao * fps)):
        escritor.send(quadro(fundo, lista, n / fps).tobytes())
    escritor.close()


# ---------- canal ----------

def gerar_capa(destino: str) -> None:
    """Capa 2560x1440. Tudo que importa fica no centro (1546x423), que aparece em celular, PC e TV."""
    from PIL import Image, ImageDraw
    imagem = Image.new("RGBA", (2560, 1440), AZUL + (255,))
    linhas = Image.new("RGBA", (2560, 1440), (0, 0, 0, 0))
    traco = ImageDraw.Draw(linhas)
    cor = (255, 255, 255, 60)
    x0, y0, x1, y1 = 180, 330, 2380, 1110  # quadra deitada, atrás do texto
    traco.rectangle([x0, y0, x1, y1], outline=cor, width=6)
    traco.line([x0, y0 + 95, x1, y0 + 95], fill=cor, width=4)
    traco.line([x0, y1 - 95, x1, y1 - 95], fill=cor, width=4)
    traco.line([x0 + 520, y0 + 95, x0 + 520, y1 - 95], fill=cor, width=4)
    traco.line([x1 - 520, y0 + 95, x1 - 520, y1 - 95], fill=cor, width=4)
    traco.line([x0 + 520, (y0 + y1) // 2, x1 - 520, (y0 + y1) // 2], fill=cor, width=4)
    for y in range(y0 - 40, y1 + 40, 30):
        traco.line([1280, y, 1280, y + 15], fill=(255, 255, 255, 60), width=6)
    imagem.alpha_composite(linhas)
    bloco = _bloco([("TÊNIS NOTÍCIAS", titulo(190), BRANCO),
                    ("espaco", 34),
                    ("Notícias de tênis do Brasil e do mundo, em português", texto(52, forte=True), CLARO)],
                   largura=2560)
    altura = bloco.size[1]
    imagem.alpha_composite(bloco, (0, 720 - altura // 2 + 10))
    desenho = ImageDraw.Draw(imagem)
    desenho.rectangle([1180, 515, 1380, 527], fill=BOLA)
    desenhar_bola(desenho, 1960, 610, 48)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    imagem.convert("RGB").save(destino, "PNG", optimize=True)


def gerar_perfil(destino: str) -> None:
    from PIL import Image, ImageDraw
    imagem = Image.new("RGB", (800, 800), AZUL)
    desenho = ImageDraw.Draw(imagem)
    # linhas da quadra atrás da bola
    cor = (90, 130, 190)
    desenho.line([0, 250, 800, 250], fill=cor, width=10)
    desenho.line([0, 550, 800, 550], fill=cor, width=10)
    desenho.line([400, 250, 400, 550], fill=cor, width=10)
    desenhar_bola(desenho, 400, 340, 170)
    bloco = _bloco([("TÊNIS NOTÍCIAS", titulo(92), BRANCO)], largura=800)
    imagem.paste(bloco, (0, 545), bloco)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    imagem.save(destino, "PNG", optimize=True)


def _ler_ranking(nome: str) -> dict:
    with open(os.path.join(RAIZ, "dados", nome), encoding="utf-8") as arquivo:
        return json.load(arquivo)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    gerar_perfil(os.path.join(SAIDA, "foto-de-perfil.png"))
    gerar_capa(os.path.join(SAIDA, "capa-do-canal.png"))
    gerar_video(os.path.join(SAIDA, "short-tenis-noticias.mp4"), _ler_ranking("ranking.json"),
                _ler_ranking("ranking-wta.json"))
    print(f"kit do YouTube gerado em {SAIDA}")
