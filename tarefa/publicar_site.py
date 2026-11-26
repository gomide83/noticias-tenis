"""Publica os resumos no site aberto Tênis Notícias (GitHub Pages).

Junta as notícias novas da rodada (pasta do lote) às já publicadas em
dados/publicadas.json, guarda os últimos 7 dias, gera site/index.html,
site/sitemap.xml e site/robots.txt e envia ao GitHub, que publica o site.

Uso: python tarefa/publicar_site.py --lote tarefa/trabalho/lote
"""

import argparse
import glob
import html
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL_SITE = "https://gomide83.github.io/noticias-tenis/"
NOME = "Tênis Notícias"
DESCRICAO = "Notícias de tênis do Brasil e do mundo, resumidas em português e atualizadas ao longo do dia."
DIAS_NO_SITE = 7
BRASILIA = timezone(timedelta(hours=-3))
CATEGORIAS = ("ATP", "WTA", "Brasileiros", "Grand Slam", "Outros")
CLASSES = {"ATP": "atp", "WTA": "wta", "Brasileiros": "br", "Grand Slam": "slam", "Outros": "outros"}
IDIOMAS = {"en": "inglês", "fr": "francês", "es": "espanhol", "it": "italiano"}
DIAS_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo")
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro")


def _ler_iso(texto: str) -> datetime:
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _e(texto) -> str:
    return html.escape(str(texto or ""), quote=True)


def carregar_publicadas(caminho: str) -> list:
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


def ler_lote(pasta_lote: str) -> list:
    novas = []
    for caminho in sorted(glob.glob(os.path.join(pasta_lote, "noticias", "*.json"))):
        with open(caminho, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
        dados["id"] = os.path.splitext(os.path.basename(caminho))[0]
        novas.append(dados)
    return novas


def juntar(publicadas: list, novas: list, agora: datetime, dias: int = DIAS_NO_SITE) -> list:
    por_id = {n["id"]: n for n in publicadas}
    for nova in novas:
        por_id[nova["id"]] = nova
    corte = agora - timedelta(days=dias)
    recentes = [n for n in por_id.values() if _ler_iso(n.get("criadoEm") or n["publicadoEm"]) >= corte]
    recentes.sort(key=lambda n: n["publicadoEm"], reverse=True)
    return recentes


def _rotulo_dia(data: datetime) -> str:
    return f"{DIAS_SEMANA[data.weekday()]}, {data.day} de {MESES[data.month - 1]}"


def _fontes_html(fontes: list) -> str:
    partes, idiomas = [], []
    for fonte in fontes or []:
        nome = _e(fonte.get("nome"))
        link = fonte.get("link") or ""
        if isinstance(link, str) and link.startswith("https://"):
            partes.append(f'<a href="{_e(link)}" target="_blank" rel="noopener">{nome}</a>')
        else:
            partes.append(f"<span>{nome}</span>")
        idioma = IDIOMAS.get(fonte.get("idioma"))
        if idioma and idioma not in idiomas:
            idiomas.append(idioma)
    if not partes:
        return ""
    rotulo = "Fonte:" if len(partes) == 1 else "Fontes:"
    traduzido = f'<span class="traduzido">traduzido do {" e do ".join(idiomas)}</span>' if idiomas else ""
    return f'<p class="fontes"><span>{rotulo}</span>{"".join(partes)}{traduzido}</p>'


def _cartao(noticia: dict) -> str:
    categoria = noticia.get("categoria") if noticia.get("categoria") in CATEGORIAS else "Outros"
    quando = _ler_iso(noticia["publicadoEm"]).astimezone(BRASILIA)
    return (
        f'<article class="noticia" data-categoria="{_e(categoria)}">'
        f'<div class="meta"><span class="categoria cat-{CLASSES[categoria]}">{_e(categoria)}</span>'
        f'<time datetime="{_e(noticia["publicadoEm"])}">{quando:%H:%M}</time></div>'
        f'<h3>{_e(noticia.get("titulo"))}</h3>'
        f'<p class="resumo">{_e(noticia.get("resumo"))}</p>'
        f'{_fontes_html(noticia.get("fontes"))}'
        f"</article>"
    )


def renderizar_pagina(noticias: list, agora: datetime) -> str:
    contagem = {c: 0 for c in CATEGORIAS}
    for n in noticias:
        contagem[n.get("categoria") if n.get("categoria") in CATEGORIAS else "Outros"] += 1
    filtros = [f'<button type="button" class="chip" data-filtro="Todas" aria-pressed="true">'
               f'Todas <span class="conta">{len(noticias)}</span></button>']
    for c in CATEGORIAS:
        filtros.append(f'<button type="button" class="chip" data-filtro="{_e(c)}" aria-pressed="false">'
                       f'{_e(c)} <span class="conta">{contagem[c]}</span></button>')

    blocos, dia_atual = [], None
    for n in noticias:
        dia = _ler_iso(n["publicadoEm"]).astimezone(BRASILIA).date()
        if dia != dia_atual:
            if dia_atual is not None:
                blocos.append("</section>")
            dia_atual = dia
            blocos.append(f'<section class="dia"><h2>{_rotulo_dia(_ler_iso(n["publicadoEm"]).astimezone(BRASILIA))}</h2>')
        blocos.append(_cartao(n))
    if dia_atual is not None:
        blocos.append("</section>")
    if not noticias:
        blocos.append('<div class="mensagem"><h2>Ainda não há notícias</h2>'
                      "<p>As primeiras notícias aparecem aqui assim que forem publicadas.</p></div>")

    atualizado = agora.astimezone(BRASILIA)
    return (MODELO
            .replace("{{NOME}}", _e(NOME))
            .replace("{{DESCRICAO}}", _e(DESCRICAO))
            .replace("{{URL}}", _e(URL_SITE))
            .replace("{{ATUALIZADO}}", f"Atualizado em {atualizado:%d/%m/%Y} às {atualizado:%H:%M} (horário de Brasília)")
            .replace("{{FILTROS}}", "".join(filtros))
            .replace("{{NOTICIAS}}", "\n".join(blocos)))


def renderizar_sitemap(agora: datetime) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{URL_SITE}</loc><lastmod>{agora.astimezone(timezone.utc).isoformat(timespec='seconds')}</lastmod>"
            "<changefreq>hourly</changefreq></url>\n"
            "</urlset>\n")


ROBOTS = f"User-agent: *\nAllow: /\n\nSitemap: {URL_SITE}sitemap.xml\n"


def _gravar(caminho: str, conteudo: str) -> None:
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)


def _git(raiz: str, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", raiz, *args], capture_output=True, text=True, timeout=120)


def enviar_para_github(raiz: str, agora: datetime) -> bool:
    _git(raiz, "add", "dados", "site")
    if _git(raiz, "diff", "--cached", "--quiet").returncode == 0:
        print("site: nada mudou")
        return True
    if _git(raiz, "commit", "-q", "-m", f"site: resumos de {agora:%Y-%m-%dT%H:%MZ}").returncode != 0:
        print("site: falha no commit", file=sys.stderr)
        return False
    _git(raiz, "pull", "--rebase", "--autostash", "-q")
    envio = _git(raiz, "push", "-q")
    if envio.returncode != 0:
        print(f"site: falha ao enviar ao GitHub: {envio.stderr.strip()}", file=sys.stderr)
        return False
    print("site: enviado ao GitHub")
    return True


def main(argv=None, agora=None) -> list:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lote", required=True)
    parser.add_argument("--raiz", default=RAIZ)
    parser.add_argument("--sem-git", action="store_true", help="só gera os arquivos, sem enviar ao GitHub")
    args = parser.parse_args(argv)
    agora = agora or datetime.now(timezone.utc)

    caminho_dados = os.path.join(args.raiz, "dados", "publicadas.json")
    noticias = juntar(carregar_publicadas(caminho_dados), ler_lote(args.lote), agora)
    _gravar(caminho_dados, json.dumps(noticias, ensure_ascii=False, indent=1) + "\n")
    _gravar(os.path.join(args.raiz, "site", "index.html"), renderizar_pagina(noticias, agora))
    _gravar(os.path.join(args.raiz, "site", "sitemap.xml"), renderizar_sitemap(agora))
    _gravar(os.path.join(args.raiz, "site", "robots.txt"), ROBOTS)
    print(f"site: {len(noticias)} notícias nos últimos {DIAS_NO_SITE} dias")
    if not args.sem_git:
        enviar_para_github(args.raiz, agora)
    return noticias


MODELO = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{NOME}}</title>
<meta name="description" content="{{DESCRICAO}}">
<link rel="canonical" href="{{URL}}">
<meta property="og:type" content="website">
<meta property="og:locale" content="pt_BR">
<meta property="og:title" content="{{NOME}}">
<meta property="og:description" content="{{DESCRICAO}}">
<meta property="og:url" content="{{URL}}">
<meta name="theme-color" content="#1d4f91">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Barlow:wght@400;500;600&display=swap">
<style>
/* Faixa azul de quadra dura no topo, filtros fixos, uma coluna de notícias por dia */
:root{--quadra:#1d4f91;--linha-quadra:#fff;--bola:#d7f04a;--bola-texto:#1f2a05;--fundo:#f3f5f8;--superficie:#fff;--texto:#142032;--texto-suave:#536175;--divisoria:#dbe2ea;--link:#1d4f91;--foco:#1d4f91;--cat-atp:#1d4f91;--cat-wta:#8b2c6b;--cat-br:#1b7a3c;--cat-slam:#8a5800;--cat-outros:#536175;--fonte-titulo:"Barlow Condensed","Arial Narrow","Roboto Condensed",sans-serif;--fonte-texto:"Barlow","Segoe UI",system-ui,-apple-system,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--quadra:#16396a;--linha-quadra:#dfe9f7;--fundo:#0c1520;--superficie:#132031;--texto:#e6ecf3;--texto-suave:#9cabbc;--divisoria:#22324a;--link:#8fbaff;--foco:#d7f04a;--cat-atp:#8fbaff;--cat-wta:#eb9fd0;--cat-br:#72d697;--cat-slam:#e9bb5e;--cat-outros:#9cabbc;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--fundo);color:var(--texto);font-family:var(--fonte-texto);font-size:1rem;line-height:1.55}
a{color:var(--link)}
:focus-visible{outline:3px solid var(--foco);outline-offset:2px;border-radius:4px}
.faixa{max-width:46rem;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
.topo{background:var(--quadra);color:#fff;position:relative;overflow:hidden}
.topo .faixa{position:relative;padding-block:1.75rem 1.5rem;display:grid;gap:.35rem}
.quadra-desenho{position:absolute;right:8px;top:50%;transform:translateY(-50%);width:13rem;max-width:45%;height:auto;opacity:.28;pointer-events:none}
.quadra-desenho *{fill:none;stroke:var(--linha-quadra);stroke-width:2}
.topo h1{margin:0;font-family:var(--fonte-titulo);font-weight:700;font-size:clamp(2rem,7vw,2.75rem);line-height:1;letter-spacing:.01em;text-transform:uppercase;position:relative}
.status{margin:0;font-size:.95rem;opacity:.88;position:relative}
.filtros{position:sticky;top:0;z-index:5;background:var(--fundo);border-bottom:1px solid var(--divisoria)}
.filtros .faixa{display:flex;gap:.5rem;padding-block:.75rem;overflow-x:auto;scrollbar-width:none}
.chip{flex:0 0 auto;display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--divisoria);background:var(--superficie);color:var(--texto);font:600 .9rem/1 var(--fonte-texto);padding:.55rem .8rem;border-radius:999px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--bola);border-color:var(--bola);color:var(--bola-texto)}
.chip .conta{font-weight:500;font-size:.8rem;opacity:.75}
main .faixa{padding-block:1rem 2.5rem;display:grid;gap:1.25rem}
.dia h2{margin:0 0 .25rem;font-family:var(--fonte-titulo);font-weight:600;font-size:.95rem;letter-spacing:.08em;text-transform:uppercase;color:var(--texto-suave)}
.noticia{display:grid;gap:.35rem;padding-block:1rem;border-top:1px solid var(--divisoria);min-width:0}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:.25rem .75rem;font-size:.82rem;color:var(--texto-suave)}
.categoria{font-family:var(--fonte-titulo);font-weight:700;font-size:.85rem;letter-spacing:.06em;text-transform:uppercase;display:inline-flex;align-items:center;gap:.35rem}
.categoria::before{content:"";width:.55rem;height:.55rem;border-radius:50%;background:currentColor}
.cat-atp{color:var(--cat-atp)}.cat-wta{color:var(--cat-wta)}.cat-br{color:var(--cat-br)}.cat-slam{color:var(--cat-slam)}.cat-outros{color:var(--cat-outros)}
.noticia h3{margin:0;font-family:var(--fonte-titulo);font-weight:600;font-size:1.4rem;line-height:1.15;overflow-wrap:anywhere}
.resumo{margin:0;max-width:65ch;overflow-wrap:anywhere}
.fontes{margin:.15rem 0 0;font-size:.88rem;color:var(--texto-suave);display:flex;flex-wrap:wrap;gap:.25rem .6rem;align-items:baseline}
.fontes a{font-weight:600}
.traduzido{font-size:.78rem;border:1px solid var(--divisoria);border-radius:999px;padding:.05rem .5rem}
.mensagem{background:var(--superficie);border:1px solid var(--divisoria);border-radius:12px;padding:1.5rem}
.mensagem h2{margin:0 0 .5rem;font-family:var(--fonte-titulo)}
.rodape{border-top:1px solid var(--divisoria)}
.rodape p{margin:0;padding-block:1.25rem 2rem;font-size:.85rem;color:var(--texto-suave);max-width:65ch}
[hidden]{display:none!important}
</style>
</head>
<body>
<header class="topo">
<div class="faixa">
<svg class="quadra-desenho" viewBox="0 0 240 110" aria-hidden="true" focusable="false"><rect x="4" y="4" width="232" height="102"></rect><line x1="4" y1="17" x2="236" y2="17"></line><line x1="4" y1="93" x2="236" y2="93"></line><line x1="58" y1="17" x2="58" y2="93"></line><line x1="182" y1="17" x2="182" y2="93"></line><line x1="58" y1="55" x2="182" y2="55"></line><line x1="120" y1="2" x2="120" y2="108" stroke-dasharray="3 3"></line></svg>
<h1>{{NOME}}</h1>
<p class="status">{{ATUALIZADO}}</p>
</div>
</header>
<nav class="filtros" aria-label="Filtrar por categoria"><div class="faixa">{{FILTROS}}</div></nav>
<main><div class="faixa">
{{NOTICIAS}}
</div></main>
<footer class="rodape"><div class="faixa"><p>Resumos escritos com a ajuda do Claude a partir de portais de tênis do Brasil e do exterior. Toque no nome do portal para ler a matéria original.</p></div></footer>
<script>
(function () {
  var botoes = document.querySelectorAll(".chip");
  function aplicar(filtro) {
    botoes.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-filtro") === filtro)); });
    document.querySelectorAll(".noticia").forEach(function (n) {
      n.hidden = filtro !== "Todas" && n.getAttribute("data-categoria") !== filtro;
    });
    document.querySelectorAll(".dia").forEach(function (d) {
      d.hidden = !d.querySelector(".noticia:not([hidden])");
    });
  }
  botoes.forEach(function (b) {
    b.addEventListener("click", function () { aplicar(b.getAttribute("data-filtro")); });
  });
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
