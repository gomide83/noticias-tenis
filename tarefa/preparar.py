"""Separa as notícias do robô que o Claude ainda não tratou.

Uso:
  python tarefa/preparar.py --noticias noticias.json --db tarefa/trabalho/db \
      --saida tarefa/trabalho/candidatos.json

--db é a pasta onde o ArtifactData salvou os documentos (out_dir):
  <db>/meta/tratados.json e <db>/noticias/*.json (publicadas nas últimas 24 h).
"""

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta, timezone

LIMITE_TRECHO = 300
BRASILIA = timezone(timedelta(hours=-3))
HORA_DO_RESUMO = 21  # horário de Brasília
CAMPOS = ("id", "titulo", "link", "fonte", "via", "idioma", "publicadoEm")


def _ler_iso(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def carregar_corpo(caminho: str) -> dict:
    with open(caminho, encoding="utf-8") as arquivo:
        conteudo = json.load(arquivo)
    if isinstance(conteudo, dict) and isinstance(conteudo.get("data"), dict):
        return conteudo["data"]
    return conteudo


def carregar_tratados(pasta_db: str) -> set:
    caminho = os.path.join(pasta_db, "meta", "tratados.json")
    if not os.path.exists(caminho):
        return set()
    return set(carregar_corpo(caminho).get("ids", []))


def titulos_publicados(pasta_db: str) -> list:
    titulos = []
    for caminho in sorted(glob.glob(os.path.join(pasta_db, "noticias", "*.json"))):
        titulo = carregar_corpo(caminho).get("titulo")
        if titulo:
            titulos.append(titulo)
    return titulos


def resumo_do_dia(pasta_db: str, agora: datetime):
    """Depois das 21h de Brasília, pede o resumo do dia dos brasileiros, uma vez por dia."""
    local = agora.astimezone(BRASILIA)
    if local.hour < HORA_DO_RESUMO:
        return None
    data = local.strftime("%Y-%m-%d")
    pasta = os.path.join(pasta_db, "noticias")
    if os.path.exists(os.path.join(pasta, f"resumo-{data}.json")):
        return None
    do_dia = []
    for caminho in sorted(glob.glob(os.path.join(pasta, "*.json"))):
        corpo = carregar_corpo(caminho)
        if corpo.get("categoria") != "Brasileiros" or os.path.basename(caminho).startswith("resumo-"):
            continue
        datas = {_ler_iso(corpo[c]).astimezone(BRASILIA).strftime("%Y-%m-%d")
                 for c in ("publicadoEm", "criadoEm") if corpo.get(c)}
        if data in datas:
            do_dia.append({"titulo": corpo.get("titulo", ""), "resumo": corpo.get("resumo", "")})
    if not do_dia:
        return None
    return {"data": data, "brasileirasDeHoje": do_dia}


def selecionar_candidatos(noticias: list, tratados: set, agora: datetime,
                          max_idade_h: int = 24, limite: int = 80) -> list:
    corte = agora - timedelta(hours=max_idade_h)
    novas = [n for n in noticias if n["id"] not in tratados and _ler_iso(n["publicadoEm"]) >= corte]
    novas.sort(key=lambda n: n["publicadoEm"], reverse=True)
    candidatos = []
    for n in novas[:limite]:
        candidato = {campo: n.get(campo) for campo in CAMPOS}
        candidato["trecho"] = (n.get("trecho") or "")[:LIMITE_TRECHO]
        candidatos.append(candidato)
    return candidatos


def main(argv=None, agora=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noticias", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    agora = agora or datetime.now(timezone.utc)

    with open(args.noticias, encoding="utf-8") as arquivo:
        robo = json.load(arquivo)
    candidatos = selecionar_candidatos(robo.get("noticias", []), carregar_tratados(args.db), agora)
    resultado = {
        "robo": {"atualizadoEm": robo.get("atualizadoEm"), "fontesComFalha": robo.get("fontesComFalha", [])},
        "jaPublicadas": titulos_publicados(args.db),
        "candidatos": candidatos,
        "resumoDoDia": resumo_do_dia(args.db, agora),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.saida)), exist_ok=True)
    with open(args.saida, "w", encoding="utf-8") as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=1)
    print(f"{len(candidatos)} candidatos")
    if resultado["resumoDoDia"]:
        print(f"resumo do dia dos brasileiros pendente: {resultado['resumoDoDia']['data']}")
    return resultado


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
