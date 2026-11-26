"""Passo 1 da tarefa: limpa a pasta de trabalho, calcula os horários e
atualiza as notícias do robô. Funciona igual no Bash e no PowerShell.

Se os dados do robô do GitHub tiverem mais de 45 minutos (o agendamento gratuito
do GitHub atrasa ou pula execuções), coleta as notícias aqui mesmo no PC, numa
cópia dentro da pasta de trabalho, sem mexer no noticias.json do repositório.

Uso: python tarefa/inicio.py
Imprime: H24 <iso>, D7 <iso>, NOTICIAS <caminho ou NENHUM> e ORIGEM <github|pc>.
"""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL_COPIA = "https://raw.githubusercontent.com/gomide83/noticias-tenis/main/noticias.json"
FORMATO = "%Y-%m-%dT%H:%M:%SZ"
LIMITE_DADOS = timedelta(minutes=45)


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


def idade_dos_dados(caminho: str, agora: datetime):
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            atualizado = json.load(arquivo)["atualizadoEm"]
        return agora - datetime.strptime(atualizado, FORMATO).replace(tzinfo=timezone.utc)
    except (OSError, ValueError, KeyError, TypeError):
        return None


def coletar_no_pc(destino: str) -> None:
    sys.path.insert(0, os.path.join(RAIZ, "coletor"))
    import coletar
    coletar.main(caminho_saida=destino)


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

    resultado["ORIGEM"] = "github"
    noticias = resultado["NOTICIAS"]
    idade = idade_dos_dados(noticias, agora) if noticias else None
    if idade is not None and idade > LIMITE_DADOS:
        copia = os.path.join(trabalho, "noticias.json")
        if os.path.abspath(noticias) != os.path.abspath(copia):
            shutil.copyfile(noticias, copia)
        try:
            coletar_no_pc(copia)
            resultado["ORIGEM"] = "pc"
        except Exception as erro:  # sem coleta local, segue com os dados do GitHub
            print(f"coleta no PC falhou: {erro}", file=sys.stderr)
        resultado["NOTICIAS"] = copia

    for chave in ("H24", "D7", "NOTICIAS", "ORIGEM"):
        print(chave, resultado[chave] or "NENHUM")
    return resultado


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
