"""Baixa e interpreta feeds RSS 2.0 e Atom."""

import html
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# Identificador simples: o ESPN recusa o de navegador completo, e todas as fontes aceitam este.
USER_AGENT = "Mozilla/5.0 (compatible; NoticiasTenis/1.0)"
LIMITE_TRECHO = 500

_TAGS = re.compile(r"<[^>]+>")
_ESPACOS = re.compile(r"\s+")


def baixar(url: str, timeout: int = 15) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def limpar_texto(texto) -> str:
    if not texto:
        return ""
    texto = html.unescape(texto)
    texto = _TAGS.sub(" ", texto)
    texto = html.unescape(texto)
    texto = texto.replace("\xa0", " ")
    return _ESPACOS.sub(" ", texto).strip()


def _formatar_utc(data: datetime) -> str:
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def para_iso(data_texto):
    if not data_texto or not data_texto.strip():
        return None
    data_texto = data_texto.strip()
    try:
        return _formatar_utc(parsedate_to_datetime(data_texto))
    except (TypeError, ValueError, IndexError):
        pass
    try:
        iso = data_texto[:-1] + "+00:00" if data_texto.endswith("Z") else data_texto
        return _formatar_utc(datetime.fromisoformat(iso))
    except ValueError:
        return None


def _nome(elemento) -> str:
    return elemento.tag.split("}")[-1]


def _filho(elemento, nome):
    for filho in elemento:
        if _nome(filho) == nome:
            return filho
    return None


def _texto_filho(elemento, *nomes) -> str:
    for nome in nomes:
        filho = _filho(elemento, nome)
        if filho is not None and (filho.text or "").strip():
            return filho.text
    return ""


def _link_atom(entrada) -> str:
    for filho in entrada:
        if _nome(filho) == "link" and filho.get("rel", "alternate") == "alternate":
            return filho.get("href", "")
    link = _filho(entrada, "link")
    return link.get("href", "") if link is not None else ""


def interpretar_feed(xml: bytes, fonte: dict) -> list:
    try:
        raiz = ET.fromstring(xml)
    except ET.ParseError as erro:
        raise ValueError(f"XML inválido em {fonte.get('nome')}: {erro}") from erro

    google = bool(fonte.get("google"))
    itens = []
    for elemento in raiz.iter():
        tipo = _nome(elemento)
        if tipo == "item":
            link = (_texto_filho(elemento, "link") or "").strip()
            data = _texto_filho(elemento, "pubDate", "date", "published", "updated")
            trecho = _texto_filho(elemento, "description", "encoded", "summary")
        elif tipo == "entry":
            link = _link_atom(elemento).strip()
            data = _texto_filho(elemento, "published", "updated")
            trecho = _texto_filho(elemento, "summary", "content")
        else:
            continue

        titulo = limpar_texto(_texto_filho(elemento, "title"))
        if not titulo or not link:
            continue

        nome_fonte = fonte.get("nome", "")
        via = ""
        if google:
            via = "Google Notícias"
            origem = _filho(elemento, "source")
            if origem is not None and (origem.text or "").strip():
                nome_fonte = origem.text.strip()
                sufixo = " - " + nome_fonte
                if titulo.endswith(sufixo):
                    titulo = titulo[: -len(sufixo)].strip()
            trecho = ""  # a descrição do Google só repete links de outras manchetes

        itens.append({
            "titulo": titulo,
            "link": link,
            "fonte": nome_fonte,
            "via": via,
            "idioma": fonte.get("idioma", "pt"),
            "publicadoEm": para_iso(data),
            "trecho": limpar_texto(trecho)[:LIMITE_TRECHO],
        })
    return itens
