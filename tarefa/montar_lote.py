"""Transforma as decisões do Claude em gravações para o banco da página.

Uso:
  python tarefa/montar_lote.py --noticias noticias.json --db tarefa/trabalho/db \
      --decisoes tarefa/trabalho/decisoes.json --saida tarefa/trabalho/lote

decisoes.json (escrito pelo Claude):
  {"fatos": [{"titulo", "resumo", "categoria", "idsRobo": [...]}], "descartados": [ids]}

Grava um arquivo JSON por documento e <saida>/writes.json, a lista de entradas
pronta para o "batch" do ArtifactData. Links e fontes vêm sempre do noticias.json.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preparar import carregar_corpo  # noqa: E402

CATEGORIAS = ("ATP", "WTA", "Brasileiros", "Grand Slam", "Outros")


def _iso(data: datetime) -> str:
    return data.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def montar_noticia(fato: dict, por_id: dict, agora: datetime):
    titulo = (fato.get("titulo") or "").strip()
    resumo = (fato.get("resumo") or "").strip()
    ids = []
    for id_ in fato.get("idsRobo", []):
        if id_ in por_id and id_ not in ids:
            ids.append(id_)
    if not ids or not titulo or not resumo:
        return None

    fontes, nomes = [], set()
    for id_ in ids:
        item = por_id[id_]
        if item["fonte"] not in nomes:
            nomes.add(item["fonte"])
            fontes.append({"nome": item["fonte"], "link": item["link"]})

    categoria = fato.get("categoria")
    dados = {
        "titulo": titulo,
        "resumo": resumo,
        "categoria": categoria if categoria in CATEGORIAS else "Outros",
        "fontes": fontes,
        "publicadoEm": min(por_id[i]["publicadoEm"] for i in ids),
        "criadoEm": _iso(agora),
        "idsRobo": ids,
    }
    return "n-" + ids[0], dados


def novos_tratados(antigos: list, decisoes: dict, ids_atuais: set) -> list:
    todos = list(antigos)
    for fato in decisoes.get("fatos", []):
        todos.extend(fato.get("idsRobo", []))
    todos.extend(decisoes.get("descartados", []))
    vistos, resultado = set(), []
    for id_ in todos:
        if id_ in ids_atuais and id_ not in vistos:
            vistos.add(id_)
            resultado.append(id_)
    return resultado


def _versao(caminho: str):
    if not os.path.exists(caminho):
        return None
    with open(caminho, encoding="utf-8") as arquivo:
        conteudo = json.load(arquivo)
    versao = conteudo.get("version") if isinstance(conteudo, dict) else None
    return versao if isinstance(versao, int) else None


def _gravar(saida: str, colecao: str, doc_id: str, dados: dict, versao=None) -> dict:
    caminho = os.path.abspath(os.path.join(saida, colecao, doc_id + ".json"))
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=1)
    entrada = {"op": "set", "collection": colecao, "doc_id": doc_id, "file_path": caminho}
    if versao is not None:
        entrada["if_version"] = versao
    return entrada


def main(argv=None, agora=None) -> list:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--noticias", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--decisoes", required=True)
    parser.add_argument("--saida", required=True)
    args = parser.parse_args(argv)
    agora = agora or datetime.now(timezone.utc)

    with open(args.noticias, encoding="utf-8") as arquivo:
        robo = json.load(arquivo)
    with open(args.decisoes, encoding="utf-8") as arquivo:
        decisoes = json.load(arquivo)

    caminho_tratados = os.path.join(args.db, "meta", "tratados.json")
    antigos = carregar_corpo(caminho_tratados).get("ids", []) if os.path.exists(caminho_tratados) else []
    ja_tratados = set(antigos)
    por_id = {n["id"]: n for n in robo.get("noticias", []) if n["id"] not in ja_tratados}

    writes, usados = [], set()
    for fato in decisoes.get("fatos", []):
        montada = montar_noticia(fato, por_id, agora)
        if montada is None or montada[0] in usados:
            continue
        doc_id, dados = montada
        usados.add(doc_id)
        writes.append(_gravar(args.saida, "noticias", doc_id, dados))

    ids_atuais = {n["id"] for n in robo.get("noticias", [])}
    tratados = novos_tratados(antigos, decisoes, ids_atuais)
    writes.append(_gravar(args.saida, "meta", "tratados", {"ids": tratados}, _versao(caminho_tratados)))
    estado = {
        "atualizadoEm": _iso(agora),
        "coletaEm": robo.get("atualizadoEm"),
        "fontesComFalha": robo.get("fontesComFalha", []),
        "novasNaRodada": len(usados),
    }
    caminho_estado = os.path.join(args.db, "meta", "estado.json")
    writes.append(_gravar(args.saida, "meta", "estado", estado, _versao(caminho_estado)))

    with open(os.path.join(args.saida, "writes.json"), "w", encoding="utf-8") as arquivo:
        json.dump(writes, arquivo, ensure_ascii=False, indent=1)
    descartados = len(decisoes.get("descartados", []))
    print(f"{len(usados)} fatos, {descartados} descartados, {len(writes)} gravações em {os.path.abspath(args.saida)}")
    return writes


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
