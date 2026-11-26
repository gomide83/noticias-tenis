# Ranking ATP no site aberto — design curto

**Pedido do usuário (2026-11-26):** mostrar o ranking da ATP no site. Escolheu o **Top 100**.

## Intenção
Quem lê as notícias quer ver também a posição dos jogadores, em português, sem sair do site.

## O que entra
- Página nova `site/ranking.html` ("Ranking ATP | Tênis Notícias"), com link no topo de todas as páginas e no sitemap.
- Tabela com os 100 primeiros de simples: posição, jogador, país (em português), pontos e se subiu ou caiu
  em relação ao ranking anterior. Brasileiros ficam destacados (chamada minha: o site é brasileiro).
- Data dos dados e a fonte (ESPN) escritas na página.

## Fonte e atualização
- O site da ATP bloqueia robôs (Cloudflare, 403). A ESPN publica os 150 primeiros em
  `https://site.api.espn.com/apis/site/v2/sports/tennis/atp/rankings` (JSON, sem chave).
- `tarefa/publicar_site.py` (Passo 6b de cada rodada) busca o ranking no máximo a cada 6 horas e guarda em
  `dados/ranking.json`. Se a ESPN falhar ou mudar o formato, a página continua com o último ranking salvo;
  sem nenhum salvo, mostra um aviso.

## Abordagens consideradas
- **ESPN (escolhida):** grátis, testada, traz pontos, país e posição anterior. Risco: não é oficial e pode mudar.
- Site da ATP: bloqueia robôs.
- Planilhas públicas no GitHub (Sackmann): o arquivo de ranking atual não existe mais (404).

## Fora do escopo
- Ranking na página do Claude (artifact): dá para fazer depois, se o usuário pedir.

## Acréscimo (mesmo dia): ranking da WTA
O usuário pediu também a WTA. Mesma fonte (`.../tennis/wta/rankings`), página `site/ranking-wta.html`,
dados em `dados/ranking-wta.json`, link "Ranking WTA" no menu. Sem brasileiras no top 100, a página diz isso.
