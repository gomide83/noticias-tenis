"""Passo 1 da tarefa: limpa a pasta de trabalho, calcula os horários e
atualiza as notícias do robô. Funciona igual no Bash e no PowerShell.

Uso: python tarefa/inicio.py
Imprime três linhas: H24 <iso>, D7 <iso> e NOTICIAS <caminho ou NENHUM>.
"""

import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL_COPIA = "https://raw.githubusercontent.com/gomide83/noticias-tenis/main/noticias.json"
FORMATO = "%Y-%m-%dT%H:%M:%SZ"


def horarios(agora: datetime) -> dict:
    return {
        "H24": (agora - timedelta(hours=24)).strftime(FORMATO),
        "D7": (agora - timedelta(days=7)).strftime(FORMATO),
    }


def atualizar_repositorio(raiz: str) -> bool:
    try:
        resultado = subprocess.run(["git", "-C", raiz, "pull", "--ff-only", "-q"],
                                   capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return resultado.returncode == 0


def baixar_copia(destino: str) -> bool:
    try:
        pedido = urllib.request.Request(URL_COPIA, headers={"User-Agent": "NoticiasTenis/1.0"})
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            dados = resposta.read()
    except OSError:
        return False
    with open(destino, "wb") as arquivo:
        arquivo.write(dados)
    return True


def main(raiz: str = RAIZ, agora=None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    trabalho = os.path.join(raiz, "tarefa", "trabalho")
    shutil.rmtree(trabalho, ignore_errors=True)
    os.makedirs(trabalho)

    resultado = horarios(agora)
    if atualizar_repositorio(raiz):
        resultado["NOTICIAS"] = os.path.join(raiz, "noticias.json")
    else:
        copia = os.path.join(trabalho, "noticias.json")
        resultado["NOTICIAS"] = copia if baixar_copia(copia) else None

    for chave in ("H24", "D7", "NOTICIAS"):
        print(chave, resultado[chave] or "NENHUM")
    return resultado


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
