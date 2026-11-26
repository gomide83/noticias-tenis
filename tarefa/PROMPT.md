# Tarefa: Notícias de Tênis (a cada 30 minutos)

Você atualiza a página privada "Notícias de Tênis" no claude.ai com resumos em português
das notícias de tênis que um robô coleta no GitHub. Trabalhe sozinho, sem fazer perguntas:
ninguém está acompanhando. Seja econômico: leia só os arquivos indicados aqui.

## Dados fixos

- Pasta do projeto: `C:/Users/Rafae/Claude/Tomas/Site` (repositório git `gomide83/noticias-tenis`)
- Página: `https://claude.ai/artifact/RHkVaGoZ83bRcDnFLN3h9g`
- Banco da página: ferramenta `ArtifactData`. Se ela não estiver carregada, carregue com
  `ToolSearch` (query `select:ArtifactData`).
- Pasta de trabalho: `C:/Users/Rafae/Claude/Tomas/Site/tarefa/trabalho` (apagada a cada rodada)
- Rode os comandos a partir da pasta do projeto. Todos são `python ...` e funcionam
  igual no Bash e no PowerShell.

## Passo 1 — Pasta de trabalho, horários e notícias do robô

```
python tarefa/inicio.py
```

Ele limpa a pasta de trabalho, atualiza o repositório (`git pull`, ou baixa uma cópia do
GitHub se o pull falhar) e imprime três linhas: `H24 <data>`, `D7 <data>` e
`NOTICIAS <caminho>`. Anote os três. Se `NOTICIAS` for `NENHUM`, encerre respondendo
"Sem acesso às notícias do robô."

## Passo 2 — Ler o banco da página

Três chamadas `ArtifactData`, todas com `url` da página e
`out_dir: C:/Users/Rafae/Claude/Tomas/Site/tarefa/trabalho/db`:

1. `action: "get"`, `collection: "meta"`, `doc_id: "tratados"`. Anote a `version` mostrada
   (VT). Se o documento não existir, não há VT.
2. `action: "get"`, `collection: "meta"`, `doc_id: "estado"`. Anote a `version` (VE), se existir.
3. `action: "query"`, `collection: "noticias"`,
   `query: {"where": [["criadoEm", ">=", "<H24>"]], "limit": 200}`.

## Passo 3 — Separar os candidatos

```bash
python tarefa/preparar.py --noticias <NOTICIAS> --db tarefa/trabalho/db --saida tarefa/trabalho/candidatos.json
```

Se imprimir `0 candidatos`, grave `tarefa/trabalho/decisoes.json` com
`{"fatos": [], "descartados": []}` e vá para o Passo 5.

## Passo 4 — Decidir e escrever (o trabalho editorial)

Leia `tarefa/trabalho/candidatos.json`. Ele tem `candidatos` (notícias novas do robô, mais
recentes primeiro) e `jaPublicadas` (títulos que a página já mostra, das últimas 24 h).

Monte **até 15 fatos**:

- Um fato é um acontecimento. Junte em `idsRobo` todos os candidatos sobre o mesmo
  acontecimento, mesmo de portais e idiomas diferentes. Os ids vêm só de `candidatos`.
- Prioridade: tenistas brasileiros (João Fonseca, Bia Haddad, Guto Miguel e outros),
  Grand Slams, top 10, títulos e finais, lesões e polêmicas importantes; depois o resto,
  dos mais recentes para os mais antigos.
- `titulo`: português do Brasil, informativo, até uns 90 caracteres, sem sensacionalismo.
- `resumo`: 2 a 4 frases em português do Brasil, traduzindo quando a fonte for em inglês
  ou francês. Use só o que está no título, no trecho ou na matéria aberta. Nunca invente
  placar, data, número ou declaração.
- Se o trecho for vazio ou curto demais para um fato importante, você pode abrir a matéria
  pelo `link` do candidato (no máximo 5 matérias por rodada). Links `news.google.com` não
  abrem: nesses casos, escreva só com o título, de forma curta e cuidadosa.
- `categoria`, exatamente uma destas:
  - `Brasileiros` — o protagonista é brasileiro;
  - `Grand Slam` — o assunto é Australian Open, Roland Garros, Wimbledon ou US Open;
  - `ATP` — tênis masculino (inclui Copa Davis);
  - `WTA` — tênis feminino (inclui Billie Jean King Cup);
  - `Outros` — história, negócios, curiosidades, assuntos gerais do circuito.

Coloque em `descartados` os ids de candidatos que:
- não são tênis do esporte (tênis de mesa, beach tennis, padel, outros esportes, calçados);
- são palpites, apostas, placares ao vivo ou propaganda;
- repetem um fato que já está em `jaPublicadas`.

Candidatos que você juntou a um fato vão em `idsRobo` daquele fato, não em `descartados`.
Candidatos que ficaram de fora **só por causa do limite de 15** não entram em nenhuma lista:
eles voltam na próxima rodada.

Grave `tarefa/trabalho/decisoes.json` (UTF-8) neste formato:

```json
{"fatos": [{"titulo": "...", "resumo": "...", "categoria": "ATP", "idsRobo": ["id1", "id2"]}],
 "descartados": ["id3"]}
```

## Passo 5 — Montar as gravações

```bash
python tarefa/montar_lote.py --noticias <NOTICIAS> --db tarefa/trabalho/db --decisoes tarefa/trabalho/decisoes.json --saida tarefa/trabalho/lote --versao-tratados <VT> --versao-estado <VE>
```

Omita `--versao-tratados` se não havia VT, e `--versao-estado` se não havia VE.

## Passo 6 — Gravar na página

Leia `tarefa/trabalho/lote/writes.json` e chame `ArtifactData` com `action: "batch"`, `url`
da página e `writes` igual a essa lista, sem mudar nada. Se o batch for recusado por versão
desatualizada, refaça os Passos 2, 5 e 6 uma única vez.

## Passo 7 — Apagar notícias antigas

`ArtifactData` `action: "query"`, `collection: "noticias"`,
`query: {"where": [["criadoEm", "<", "<D7>"]], "limit": 50}`. Se vier algum documento,
apague todos com um `batch` de entradas `{"op": "delete", "collection": "noticias",
"doc_id": ..., "if_version": <version mostrada>}`.

## Passo 8 — Resposta final

Uma linha: "<N> notícias publicadas, <M> descartadas, fontes com falha: <lista ou nenhuma>."
