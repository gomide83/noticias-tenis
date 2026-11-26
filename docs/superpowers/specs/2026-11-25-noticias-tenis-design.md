# Notícias de Tênis — Desenho

Data: 2026-11-25

## Intenção

O dono quer um site de notícias de tênis (o esporte: jogadores, torneios,
resultados, rankings ATP/WTA), em português, atualizado a cada 30 minutos,
onde o Claude faz o trabalho de buscar e escrever as notícias.

Nas palavras do dono: "o site do github só servirá para ajudar o site do
claude. Então quando o claude ligar, ele vai pegar as notícias do github e
traduzir para o site do claude".

## Como funciona

```
~25 fontes de tênis (feeds RSS)
        │  a cada 30 min, sempre (PC ligado ou não)
        ▼
Robô coletor no GitHub (GitHub Actions + script Python)
        │  guarda noticias.json no repositório (só ajudante, sem site)
        ▼
Tarefa agendada no app do Claude
        │  a cada 30 min, quando o PC está ligado e o app aberto
        │  pega as notícias novas, traduz, resume em português
        ▼
Página privada do Claude (claude.ai)  ──── o site que o dono lê
```

## Objetivos

- Coletar notícias de tênis de muitas fontes a cada 30 minutos, sem
  depender do PC ligado, para nada se perder.
- Quando o app do Claude estiver aberto, o Claude pega as notícias novas
  do GitHub, traduz para o português, escreve um resumo curto e publica na
  página privada do Claude.
- A página privada do Claude é o único site para leitura. Tudo nela em português.

## Não-objetivos

- Não há site público para leitores. O repositório do GitHub é só depósito.
- Não cobre tênis de mesa, beach tennis, padel nem calçados ("tênis" como sneaker).
- Não tem placar ao vivo, chaves de torneio nem ranking em tempo real.
- Não tem login, comentários nem cadastro de leitores.

## Anti-objetivos (seria fracasso mesmo funcionando)

- Notícias de tênis de mesa, sneakers ou páginas de placar aparecendo como notícia.
- O mesmo fato repetido várias vezes por ter vindo de portais diferentes.
- O Claude inventar fatos que não estão na notícia original.
- Notícia em inglês ou francês aparecendo sem tradução na página.
- O robô parar sozinho depois de um tempo sem ninguém perceber.

## Restrições

- A página privada do Claude não consegue buscar dados de outros sites.
  Só o Claude, rodando no app do PC, consegue gravar nela.
- A tarefa agendada do Claude só roda com o app aberto. Se estiver
  fechado, roda quando o app abrir.
- O GitHub desliga robôs agendados de repositórios sem atividade por 60
  dias. Os commits do próprio robô contam como atividade.
- O agendamento do GitHub pode atrasar alguns minutos em horários de pico.
- O dono tem plano Max do Claude, então a tarefa pode ser generosa.
- O GitHub do dono já está conectado neste PC. Python, Node e git estão instalados.

## Abordagens consideradas

1. **Só a página privada do Claude, atualizada pelo app.** Para de coletar
   com o PC desligado, e notícias daquele período se perdem.
2. **Só um site público no GitHub.** Sempre atualizado, mas sem tradução nem
   resumos do Claude.
3. **GitHub como ajudante da página do Claude (escolhida pelo dono).** O
   robô do GitHub coleta sem parar e guarda. O Claude busca no GitHub,
   traduz e resume na página privada quando o PC liga.

## Fontes (testadas em 2026-11-25)

Português, portais:
- ge (Globo) tênis: ge.globo.com/rss/ge/tenis
- Tenis News: tenisnews.com.br/feed/
- TenisBrasil: tenisbrasil.com.br/feed/
- Olimpíada Todo Dia, tênis: olimpiadatododia.com.br/tenis/feed/
- Estadão, tênis: estadao.com.br/arc/outboundfeeds/feeds/rss/sections/esportes/tenis/
- Terra, tênis: terra.com.br/esportes/tenis/rss.xml

Português, buscas no Google Notícias (pt-BR, e uma em pt-PT):
- tênis em geral; tênis ATP ou WTA; "João Fonseca"; "Bia Haddad";
  Sinner ou Alcaraz ou Djokovic; ténis ATP (Portugal)

Inglês:
- BBC Sport Tennis, ESPN Tennis, The Guardian Tennis, Sky Sports Tennis,
  Yahoo Sports Tennis, Tennis Majors, Tennishead, Tennis365, Ubitennis,
  Sportskeeda Tennis, EssentiallySports Tennis

Francês:
- L'Équipe Tennis

Ficaram de fora: Metrópoles (parado desde 2023), Marca e AS (datas
antigas no feed), e portais que não responderam ou não têm feed.
A lista fica num arquivo de configuração fácil de editar.

## Partes

### 1. Repositório no GitHub (depósito)

- Repositório novo na conta do dono, nome `noticias-tenis`, público.
  (Decisão de quem constrói: público dá robô grátis sem limite de minutos,
  e o conteúdo são manchetes públicas de portais.)
- Sem GitHub Pages. Ninguém lê o repositório diretamente.
- Pasta local: `C:\Users\Rafae\Claude\Tomas\Site` (vira o repositório).

### 2. Robô coletor (script Python + GitHub Actions)

- Roda a cada 30 minutos pelo GitHub Actions, e também pode ser disparado
  manualmente.
- Lê todas as fontes. Se uma fonte falha, segue com as outras.
- Filtra o que não é tênis (tênis de mesa, beach tennis, padel, calçados,
  páginas de placar ao vivo).
- Remove duplicadas: mesmo link, ou título praticamente igual.
- Guarda em `noticias.json` as notícias dos últimos 3 dias, no máximo 600,
  mais a hora da última coleta e quais fontes falharam.
- Cada notícia tem: id estável, título original, link, fonte, idioma,
  data de publicação, data em que foi coletada e um trecho do texto quando
  o feed traz.
- Faz commit só se algo mudou.
- Usa só a biblioteca padrão do Python.

### 3. Página privada do Claude (claude.ai)

- Página publicada pelo Claude, privada do dono (ele pode compartilhar se quiser).
- Guarda as notícias resumidas no banco de dados da própria página.
- Mostra cada notícia com título em português, resumo de 2 a 4 frases,
  categoria (ATP, WTA, Brasileiros, Grand Slam, Outros), fontes, horário
  e links "Ler no portal".
- Permite filtrar por categoria.
- Mostra quando o Claude atualizou pela última vez e avisa se faz muito
  tempo (por exemplo, mais de 2 horas) sem atualização.
- Funciona no celular e no computador, com modo claro e escuro.

### 4. Tarefa agendada do Claude

- Roda a cada 30 minutos no app do Claude no PC.
- Busca o `noticias.json` mais recente do GitHub.
- Vê no banco da página quais notícias do robô já foram tratadas.
- Escolhe até 15 fatos novos por rodada, priorizando os mais recentes e os
  mais importantes (Grand Slams, top 10, brasileiros). Ignora o que tem mais
  de 24 horas quando o PC ficou desligado muito tempo.
- Junta numa só notícia o que vários portais contaram sobre o mesmo fato,
  guardando todos os links.
- Para cada fato: título e resumo em português, traduzindo quando a fonte é
  estrangeira, só com o que a notícia diz. Abre a matéria quando o trecho do
  feed não basta (plano Max permite).
- Descarta o que não for tênis de verdade e marca como tratado.
- Apaga da página as notícias com mais de 7 dias.
- Avisa na página se o robô do GitHub está sem coletar há mais de 2 horas.

## Decisões que ficam com quem constrói

- Visual exato da página, desde que siga o tom de portal esportivo,
  em português, legível no celular.
- Palavras exatas do filtro do robô.
- Regra exata para considerar dois títulos "a mesma notícia".
- Como a página registra quais notícias do robô já foram tratadas.
