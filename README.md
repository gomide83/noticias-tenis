# Tênis Notícias

Notícias de tênis do Brasil e do mundo, em português, atualizadas a cada 30 minutos,
com o ranking da ATP e da WTA.

**Site:** https://gomide83.github.io/noticias-tenis/

## Como funciona

- Um robô junta as manchetes de portais de tênis do Brasil e do exterior a cada 30 minutos
  (`coletor/`; as fontes ficam em `coletor/fontes.json`).
- O Claude junta as notícias repetidas, traduz as estrangeiras e escreve resumos curtos (`tarefa/`).
- O site é gerado na pasta `site/` e publicado pelo GitHub Pages.
