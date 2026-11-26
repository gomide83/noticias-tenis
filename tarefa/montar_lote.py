"""Transforma as decisões do Claude em gravações para o banco da página.

Uso:
  python tarefa/montar_lote.py --noticias noticias.json --db tarefa/trabalho/db \
      --decisoes tarefa/trabalho/decisoes.json --saida tarefa/trabalho/lote

decisoes.json (escrito pelo Claude):
  {"fatos": [{"titulo", "resumo", "categoria", "idsRobo": [...]}], "descartados": [ids]}

Grava um arquivo JSON por documento e <saida>/writes.json, a lista de entradas
pronta para o "batch" do ArtifactData. Links e fontes vêm sempre do noticias.json.
--versao-tratados e --versao-estado: a "version" que o ArtifactData get mostrou para
meta/tratados e meta/estado (os arquivos do out_dir não trazem a versão).
--rankings: pasta com ranking.json e ranking-wta.json (padrão: dados/ do projeto, que o
publicar_site.py atualiza). Viram meta/ranking-atp e meta/ranking-wta na página, só quando
o ranking mudou e só com --versao-ranking-atp / --versao-ranking-wta (a página recusa
regravar um documento sem a versão lida no Passo 2).
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from preparar import carregar_corpo  # noqa: E402
from ranking import nome_do_pais  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANKINGS = (("ranking-atp", "ranking.json", "versao_ranking_atp"),
            ("ranking-wta", "ranking-wta.json", "versao_ranking_wta"))
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
            fontes.append({"nome": item["fonte"], "link": item["link"], "idioma": item.get("idioma", "pt")})

    categoria = fato.get("categoria")
    dados = {
        "titulo": titulo,
        "resumo": resumo,
        "categoria": categoria if categoria in CATEGORIAS else "Outros",
        "fontes": fontes,
        "publicadoEm": max(por_id[i]["publicadoEm"] for i in ids),
        "criadoEm": _iso(agora),
        "idsRobo": ids,
    }
    return "n-" + ids[0], dados


def montar_resumo_do_dia(fato: dict, agora: datetime):
    data = str(fato.get("resumoDoDia") or "")
    titulo = (fato.get("titulo") or "").strip()
    resumo = (fato.get("resumo") or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data) or not titulo or not resumo:
        return None
    dados = {"titulo": titulo, "resumo": resumo, "categoria": "Brasileiros", "fontes": [],
             "publicadoEm": _iso(agora), "criadoEm": _iso(agora), "idsRobo": []}
    return "resumo-" + data, dados


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


def documento_ranking(caminho: str):
    """Lê um ranking salvo pelo publicar_site.py e devolve o documento da página, ou None."""
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            return documento_ranking_de(json.load(arquivo))
    except (OSError, ValueError):
        return None


def documento_ranking_de(dados):
    try:
        jogadores = [{"posicao": int(j["posicao"]), "anterior": j.get("anterior"), "nome": str(j["nome"]),
                      "pais": nome_do_pais(j.get("pais"), j.get("paisNome")), "pontos": int(j.get("pontos") or 0),
                      "br": j.get("pais") == "BRA"} for j in dados["jogadores"]]
        if not jogadores:
            return None
        return {"atualizadoEm": dados["atualizadoEm"], "fonte": dados.get("fonte") or "ESPN",
                "buscadoEm": dados.get("buscadoEm"), "jogadores": jogadores}
    except (ValueError, KeyError, TypeError, AttributeError):
        return None


def _mesmo_ranking(a: dict, b: dict) -> bool:
    def sem_busca(doc):
        return {k: v for k, v in doc.items() if k != "buscadoEm"}
    return sem_busca(a) == sem_busca(b)


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
    parser.add_argument("--versao-tratados", type=int, default=None,
                        help="version de meta/tratados lida no ArtifactData get (omita se não existe)")
    parser.add_argument("--versao-estado", type=int, default=None,
                        help="version de meta/estado lida no ArtifactData get (omita se não existe)")
    parser.add_argument("--rankings", default=os.path.join(RAIZ, "dados"),
                        help="pasta com ranking.json e ranking-wta.json")
    parser.add_argument("--versao-ranking-atp", type=int, default=None,
                        help="version de meta/ranking-atp lida no ArtifactData get (sem ela, não regrava)")
    parser.add_argument("--versao-ranking-wta", type=int, default=None,
                        help="version de meta/ranking-wta lida no ArtifactData get (sem ela, não regrava)")
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

    writes, usados, aceitos = [], set(), []
    for fato in decisoes.get("fatos", []):
        if "resumoDoDia" in fato:
            especial = montar_resumo_do_dia(fato, agora)
            if especial and especial[0] not in usados:
                usados.add(especial[0])
                writes.append(_gravar(args.saida, "noticias", especial[0], especial[1]))
            continue
        montada = montar_noticia(fato, por_id, agora)
        if montada is None:
            continue  # fato rejeitado: seus ids voltam como candidatos na próxima rodada
        _, dados = montada
        doc_id = next(("n-" + i for i in dados["idsRobo"] if "n-" + i not in usados), None)
        if doc_id is None:
            continue
        usados.add(doc_id)
        aceitos.append({"idsRobo": dados["idsRobo"]})
        writes.append(_gravar(args.saida, "noticias", doc_id, dados))

    for doc_id, arquivo_ranking, campo_versao in RANKINGS:
        versao = getattr(args, campo_versao)
        if versao is None:
            continue  # o documento já existe na página: sem a versão, o batch inteiro seria recusado
        documento = documento_ranking(os.path.join(args.rankings, arquivo_ranking))
        if not documento:
            continue
        caminho_pagina = os.path.join(args.db, "meta", doc_id + ".json")
        if os.path.exists(caminho_pagina):
            try:
                if _mesmo_ranking(carregar_corpo(caminho_pagina), documento):
                    continue
            except (OSError, ValueError, AttributeError):
                pass
        writes.append(_gravar(args.saida, "meta", doc_id, documento, versao))

    ids_atuais = {n["id"] for n in robo.get("noticias", [])}
    tratados = novos_tratados(antigos, {"fatos": aceitos, "descartados": decisoes.get("descartados", [])},
                              ids_atuais)
    writes.append(_gravar(args.saida, "meta", "tratados", {"ids": tratados}, args.versao_tratados))
    coletas = [n["coletadoEm"] for n in robo.get("noticias", []) if n.get("coletadoEm")]
    estado = {
        "atualizadoEm": _iso(agora),
        "coletaEm": robo.get("atualizadoEm"),
        "fontesComFalha": robo.get("fontesComFalha", []),
        "totalFontes": robo.get("totalFontes"),
        "novidadeEm": max(coletas) if coletas else None,
        "novasNaRodada": len(usados),
    }
    writes.append(_gravar(args.saida, "meta", "estado", estado, args.versao_estado))

    with open(os.path.join(args.saida, "writes.json"), "w", encoding="utf-8") as arquivo:
        json.dump(writes, arquivo, ensure_ascii=False, indent=1)
    descartados = len(decisoes.get("descartados", []))
    print(f"{len(usados)} fatos, {descartados} descartados, {len(writes)} gravações em {os.path.abspath(args.saida)}")
    return writes


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
