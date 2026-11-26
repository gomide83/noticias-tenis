"""Ranking ATP de simples para o site aberto.

Busca os 100 primeiros na ESPN (o site da ATP bloqueia robôs), guarda em
dados/ranking.json e só busca de novo depois de 6 horas. Se a ESPN falhar ou
mudar o formato, fica valendo o último ranking guardado.
"""

import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

URL_RANKING = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/rankings"
FORMATO = "%Y-%m-%dT%H:%M:%SZ"
VALIDADE = timedelta(hours=6)
MINIMO_DE_JOGADORES = 10

PAISES = {
    "ARG": "Argentina", "AUS": "Austrália", "AUT": "Áustria", "BEL": "Bélgica", "BIH": "Bósnia e Herzegovina",
    "BLR": "Belarus", "BOL": "Bolívia", "BRA": "Brasil", "BUL": "Bulgária", "CAN": "Canadá", "CHI": "Chile",
    "CHN": "China", "COL": "Colômbia", "CRO": "Croácia", "CYP": "Chipre", "CZE": "Tchéquia",
    "DEN": "Dinamarca", "ECU": "Equador", "EGY": "Egito", "ESP": "Espanha", "EST": "Estônia",
    "FIN": "Finlândia", "FRA": "França", "GBR": "Grã-Bretanha", "GEO": "Geórgia", "GER": "Alemanha",
    "GRE": "Grécia", "HKG": "Hong Kong", "HUN": "Hungria", "IND": "Índia", "IRL": "Irlanda",
    "ISR": "Israel", "ITA": "Itália", "JPN": "Japão", "KAZ": "Cazaquistão", "KOR": "Coreia do Sul",
    "LAT": "Letônia", "LTU": "Lituânia", "MDA": "Moldávia", "MEX": "México", "MON": "Mônaco",
    "NED": "Países Baixos", "NOR": "Noruega", "NZL": "Nova Zelândia", "PAR": "Paraguai", "PER": "Peru",
    "POL": "Polônia", "POR": "Portugal", "ROU": "Romênia", "RSA": "África do Sul", "RUS": "Rússia",
    "SER": "Sérvia", "SRB": "Sérvia", "SLO": "Eslovênia", "SUI": "Suíça", "SVK": "Eslováquia",
    "SWE": "Suécia", "TPE": "Taiwan", "TUN": "Tunísia", "TUR": "Turquia", "UKR": "Ucrânia",
    "URU": "Uruguai", "USA": "Estados Unidos", "UZB": "Uzbequistão",
}


def nome_do_pais(codigo, reserva: str = "") -> str:
    return PAISES.get(codigo or "", reserva or codigo or "")


def _data_iso(texto: str) -> str:
    for formato in ("%Y-%m-%dT%H:%MZ", FORMATO):
        try:
            return datetime.strptime(texto, formato).strftime(FORMATO)
        except (TypeError, ValueError):
            continue
    raise ValueError(f"data do ranking estranha: {texto!r}")


def _jogador(linha) -> dict:
    atleta = linha["athlete"]
    posicao = int(linha["current"])
    anterior = int(linha.get("previous") or 0) or None
    nome = str(atleta["displayName"]).strip()
    if posicao < 1 or not nome:
        raise ValueError("linha sem posição ou nome")
    return {"posicao": posicao, "anterior": anterior, "nome": nome,
            "pais": str(atleta.get("citizenshipCountry") or ""), "paisNome": str(atleta.get("flagAltText") or ""),
            "pontos": int(round(float(linha.get("points") or 0)))}


def interpretar_ranking(dados, limite: int = 100) -> dict:
    try:
        bloco = next(r for r in dados["rankings"] if r.get("type") == "atp")
        linhas = bloco["ranks"]
    except (KeyError, TypeError, StopIteration, AttributeError):
        raise ValueError("a resposta não tem o ranking da ATP")
    jogadores = []
    for linha in linhas:
        try:
            jogadores.append(_jogador(linha))
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
    jogadores.sort(key=lambda j: j["posicao"])
    jogadores = [j for j in jogadores if j["posicao"] <= limite]
    if len(jogadores) < MINIMO_DE_JOGADORES:
        raise ValueError("ranking com jogadores de menos")
    return {"atualizadoEm": _data_iso(bloco.get("update")), "fonte": "ESPN", "jogadores": jogadores}


def baixar_ranking(url: str = URL_RANKING, timeout: int = 20) -> dict:
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; NoticiasTenis/1.0)"})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return json.loads(resposta.read().decode("utf-8"))


def _ler_guardado(caminho: str):
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            guardado = json.load(arquivo)
        datetime.strptime(guardado["buscadoEm"], FORMATO)
        if not guardado["jogadores"]:
            return None
        return guardado
    except (OSError, ValueError, KeyError, TypeError):
        return None


def atualizar_ranking(caminho: str, agora: datetime, baixar=baixar_ranking, validade: timedelta = VALIDADE):
    guardado = _ler_guardado(caminho)
    if guardado:
        buscado = datetime.strptime(guardado["buscadoEm"], FORMATO).replace(tzinfo=timezone.utc)
        if agora - buscado < validade:
            return guardado
    try:
        novo = interpretar_ranking(baixar())
    except Exception as erro:  # fonte fora do ar ou formato novo: fica o último ranking
        print(f"ranking: não deu para atualizar ({erro})")
        return guardado
    novo["buscadoEm"] = agora.astimezone(timezone.utc).strftime(FORMATO)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(novo, arquivo, ensure_ascii=False, indent=1)
        arquivo.write("\n")
    return novo
