"""Coleta notícias de tênis de vários feeds e grava noticias.json.

Uso: python coletor/coletar.py [caminho_saida]
"""

import hashlib
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feeds import baixar, interpretar_feed  # noqa: E402

PASTA = os.path.dirname(os.path.abspath(__file__))
ARQUIVO_FONTES = os.path.join(PASTA, "fontes.json")
DIAS_GUARDADOS = 3
MAXIMO_NOTICIAS = 600
SINAL_DE_VIDA = timedelta(hours=2)
DIAS_VISTOS = 10  # itens sem data não voltam como novos enquanto estiverem aqui
FOLGA_FUTURO = timedelta(minutes=10)

BLOQUEADOS = [
    "tenis de mesa", "table tennis", "beach tennis", "beach tenis", "padel",
    "pickleball", "sneaker", "sneakers", "calcado", "calcados", "sapatilha",
    "sapatilhas", "placar ao vivo", "resultados ao vivo", "live score",
    "sofascore", "flashscore", "palpite", "palpites", "prognostico",
    "prognosticos", "betting", "betting odds", "casas de apostas", "casa de apostas",
    "onde apostar", "prediction", "predictions",
]
TERMOS_DE_TENIS = [
    "atp", "wta", "tenista", "tenistas", "tennis", "grand slam", "wimbledon",
    "roland garros", "us open", "australian open", "challenger", "itf",
    "copa davis", "davis cup", "billie jean", "sinner", "alcaraz", "djokovic",
    "fonseca", "haddad", "sabalenka", "swiatek", "gauff", "zverev", "medvedev",
    "masters 1000", "atp finals", "wta finals",
]


FONTES_BLOQUEADAS = [
    "sportytrader", "flashscore", "sofascore", "instagram", "facebook",
    "youtube", "tiktok",
]


def _padrao(termos):
    return re.compile(r"\b(?:" + "|".join(re.escape(t) for t in termos) + r")\b")


_BLOQUEIO = _padrao(BLOQUEADOS)
_TENIS = _padrao(TERMOS_DE_TENIS)
_NAO_LETRAS = re.compile(r"[^a-z0-9]+")


def _iso(data: datetime) -> str:
    return data.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ler_iso(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def normalizar_titulo(titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo or "")
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return _NAO_LETRAS.sub(" ", sem_acento.lower()).strip()


def id_estavel(link: str) -> str:
    partes = urlsplit(link.strip())
    consulta = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True)
                if not k.lower().startswith("utm_")]
    limpo = urlunsplit((partes.scheme.lower(), partes.netloc.lower(), partes.path,
                        urlencode(consulta), ""))
    return hashlib.sha1(limpo.encode("utf-8")).hexdigest()[:16]


def eh_tenis(item: dict, exige_termo: bool) -> bool:
    fonte = normalizar_titulo(item.get("fonte", "")).replace(" ", "")
    if any(bloqueada in fonte for bloqueada in FONTES_BLOQUEADAS):
        return False
    texto = normalizar_titulo(item.get("titulo", "") + " " + item.get("trecho", ""))
    if _BLOQUEIO.search(texto):
        return False
    if exige_termo and not _TENIS.search(texto):
        return False
    return True


def mesclar(antigas: list, novas: list, agora: datetime, vistos=None) -> list:
    agora_iso = _iso(agora)
    limite_futuro = agora + FOLGA_FUTURO
    corte = agora - timedelta(days=DIAS_GUARDADOS)

    vistos_id, vistos_titulo, juntas = set(), set(), []
    for noticia in antigas:
        vistos_id.add(noticia["id"])
        vistos_titulo.add(normalizar_titulo(noticia["titulo"]))
        juntas.append(noticia)

    for bruta in novas:
        noticia = dict(bruta)
        noticia["id"] = id_estavel(noticia["link"])
        titulo_norm = normalizar_titulo(noticia["titulo"])
        if noticia["id"] in vistos_id or titulo_norm in vistos_titulo or noticia["id"] in (vistos or {}):
            continue
        noticia["coletadoEm"] = agora_iso
        publicado = noticia.get("publicadoEm")
        if not publicado or _ler_iso(publicado) > limite_futuro:
            noticia["publicadoEm"] = agora_iso
            noticia["dataEstimada"] = True
        vistos_id.add(noticia["id"])
        vistos_titulo.add(titulo_norm)
        juntas.append(noticia)

    recentes = [n for n in juntas if _ler_iso(n["publicadoEm"]) >= corte]
    recentes.sort(key=lambda n: n["publicadoEm"], reverse=True)
    return recentes[:MAXIMO_NOTICIAS]


def atualizar_vistos(vistos: dict, noticias: list, agora: datetime) -> dict:
    corte = agora - timedelta(days=DIAS_VISTOS)
    atualizados = {i: quando for i, quando in (vistos or {}).items() if _ler_iso(quando) >= corte}
    for noticia in noticias:
        if noticia.get("dataEstimada"):
            atualizados.setdefault(noticia["id"], noticia["coletadoEm"])
    return atualizados


def precisa_salvar(anterior, novas_noticias: list, agora: datetime) -> bool:
    if not anterior:
        return True
    ids_antes = {n["id"] for n in anterior.get("noticias", [])}
    if ids_antes != {n["id"] for n in novas_noticias}:
        return True
    try:
        ultima = _ler_iso(anterior["atualizadoEm"])
    except (KeyError, ValueError):
        return True
    return agora - ultima >= SINAL_DE_VIDA


def _carregar_json(caminho):
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _coletar_fonte(fonte: dict):
    try:
        itens = interpretar_feed(baixar(fonte["url"]), fonte)
    except Exception as erro:  # qualquer falha de uma fonte não derruba as outras
        return fonte, None, erro
    filtrados = [i for i in itens if eh_tenis(i, bool(fonte.get("exigeTermo")))]
    return fonte, filtrados, None


def main(caminho_saida: str = "noticias.json", fontes=None, agora=None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    fontes = fontes if fontes is not None else _carregar_json(ARQUIVO_FONTES)
    anterior = _carregar_json(caminho_saida)

    with ThreadPoolExecutor(max_workers=8) as executor:
        resultados = list(executor.map(_coletar_fonte, fontes))

    novas, falhas = [], []
    for fonte, itens, erro in resultados:  # ordem do fontes.json: portais diretos antes do Google
        if erro is not None:
            falhas.append(fonte["nome"])
            print(f"  falha em {fonte['nome']}: {erro}", file=sys.stderr)
        else:
            novas.extend(itens)

    antigas = anterior.get("noticias", []) if anterior else []
    vistos = anterior.get("vistos", {}) if anterior else {}
    noticias = mesclar(antigas, novas, agora, vistos)
    vistos = atualizar_vistos(vistos, noticias, agora)
    ids_antes = {n["id"] for n in antigas}
    quantas_novas = sum(1 for n in noticias if n["id"] not in ids_antes)

    resultado = {"atualizadoEm": _iso(agora), "totalFontes": len(fontes), "fontesComFalha": falhas,
                 "vistos": vistos, "noticias": noticias}
    if precisa_salvar(anterior, noticias, agora):
        with open(caminho_saida, "w", encoding="utf-8", newline="\n") as arquivo:
            json.dump(resultado, arquivo, ensure_ascii=False, indent=1)
            arquivo.write("\n")
        print(f"{quantas_novas} novas, {len(noticias)} total, falhas: {falhas}")
    else:
        print(f"nada mudou ({len(noticias)} total), falhas: {falhas}")
    return resultado


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "noticias.json")
