# Notícias de Tênis — Plano de Construção

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Robô no GitHub coleta notícias de tênis de ~25 feeds a cada 30 min; uma tarefa agendada do Claude traduz, resume e publica numa página privada do claude.ai.

**Architecture:** Script Python (só biblioteca padrão) roda no GitHub Actions e grava `noticias.json` no repositório público `gomide83/noticias-tenis`. A tarefa agendada do app do Claude faz `git pull`, usa dois scripts auxiliares para separar candidatos e montar as gravações, e grava no banco (`db`) de um Artifact privado. O Artifact só lê o banco.

**Tech Stack:** Python 3.10+ (stdlib: urllib, xml.etree, concurrent.futures, unittest), GitHub Actions, HTML/CSS/JS puro no Artifact com capability `db`.

**Spec:** `docs/superpowers/specs/2026-11-25-noticias-tenis-design.md`

## Global Constraints

- Tudo que o leitor vê está em português (pt-BR).
- Tema: tênis, o esporte. Fora: tênis de mesa, beach tennis, padel, pickleball, calçados, placar ao vivo, palpites/apostas.
- Robô: a cada 30 min (`7,37 * * * *`), também manual (`workflow_dispatch`); guarda 3 dias, no máximo 600 notícias.
- Tarefa do Claude: a cada 30 min; até 15 fatos novos por rodada; ignora candidatos com mais de 24 h; apaga da página notícias com mais de 7 dias.
- Categorias exatas: `ATP`, `WTA`, `Brasileiros`, `Grand Slam`, `Outros`.
- Avisos: página avisa se o Claude não atualiza há mais de 2 h e se o robô não coleta há mais de 3 h. (Decisão de quem constrói: o robô grava um "sinal de vida" a cada 2 h mesmo sem notícia nova, então 3 h de silêncio significa robô parado.)
- Python compatível com 3.10 (local) e 3.12 (Actions). Sem dependências externas.
- Datas sempre em ISO 8601 UTC com sufixo `Z` (ordenam como texto).
- Links só aparecem como link na página se começarem com `https://`.
- O Claude nunca digita links: fontes e links vêm do `noticias.json` pelo id do robô.

## Review Focus

1. Feed fora do ar, lento ou devolvendo HTML em vez de XML: o robô segue com as outras fontes e registra a fonte em `fontesComFalha`.
2. Item sem data ou com data em formato estranho: usa a hora da coleta, nunca derruba a coleta.
3. Títulos com entidades HTML, CDATA e tags dentro do resumo do feed: texto limpo, sem `<b>`, `&amp;` etc.
4. Mesma notícia vinda do Google Notícias ("Título - ge") e do portal direto ("Título"): fica uma só.
5. Decisão do Claude citando id do robô que não existe ou categoria inválida: id ignorado, fato sem id válido descartado, categoria vira `Outros`.

---

## Estrutura de arquivos

```
Site/
  coletor/
    fontes.json        lista de fontes {id, nome, url, idioma, exigeTermo, google}
    feeds.py           baixar e interpretar RSS/Atom
    coletar.py         filtrar, deduplicar, juntar, salvar noticias.json
  tarefa/
    preparar.py        separa candidatos novos para o Claude
    montar_lote.py     transforma decisões do Claude em gravações do banco
    PROMPT.md          instruções completas da tarefa agendada
    trabalho/          arquivos temporários de cada rodada (no .gitignore)
  pagina/
    noticias-tenis.html  página privada do Claude (Artifact)
  tests/
    test_feeds.py  test_coletar.py  test_preparar.py  test_montar_lote.py
  .github/workflows/coletar.yml
  noticias.json        gerado pelo robô
  .gitignore           tarefa/trabalho/, __pycache__/
```

Formato de uma notícia do robô (em `noticias.json` → `noticias[]`):
`{id, titulo, link, fonte, via, idioma, publicadoEm, coletadoEm, trecho}`
- `id`: 16 primeiros hex do sha1 do link normalizado.
- `via`: `"Google Notícias"` quando veio de busca do Google, senão `""`.
- `trecho`: texto limpo, até 500 caracteres.
Topo do arquivo: `{atualizadoEm, fontesComFalha: [nomes], noticias: [...]}`.

Banco da página (Artifact `db`):
- `noticias/<docId>`: `{titulo, resumo, categoria, fontes: [{nome, link}], publicadoEm, criadoEm, idsRobo: [ids]}`; `docId = "n-" + idsRobo[0]`.
- `meta/estado`: `{atualizadoEm, coletaEm, fontesComFalha, novasNaRodada}`.
- `meta/tratados`: `{ids: [ids do robô já tratados]}`.
- Regras: `[{path: "", read: "view", write: "owner"}]` (só o dono, via Claude, grava).

---

### Task 1: Leitura de feeds

**Files:**
- Create: `coletor/feeds.py`, `coletor/__init__.py`, `tests/__init__.py`
- Test: `tests/test_feeds.py`

**Interfaces:**
- Produces:
  - `limpar_texto(html: str) -> str` — remove tags, desfaz entidades, junta espaços.
  - `para_iso(data_texto: str | None) -> str | None` — RFC 822 ou ISO 8601 → `"YYYY-MM-DDTHH:MM:SSZ"` em UTC; `None` se não der.
  - `interpretar_feed(xml: bytes, fonte: dict) -> list[dict]` — RSS 2.0 e Atom; devolve itens `{titulo, link, fonte, via, idioma, publicadoEm, trecho}`. Para fonte com `"google": true`, tira o sufixo `" - <fonte>"` do título, usa `<source>` como `fonte` e `via = "Google Notícias"`. Lança `ValueError` se o XML for inválido.
  - `baixar(url: str, timeout: int = 15) -> bytes` — urllib com User-Agent de navegador.

- [ ] **Step 1: Escrever os testes**

```python
RSS = RSS 2.0 com: item 1 título CDATA "Fonseca vence &amp; avança", link https://a.com/1,
      pubDate "Wed, 25 Nov 2026 20:11:09 -0000", description "&lt;p&gt;João <b>venceu</b>&lt;/p&gt;";
      item 2 "Sem data", link https://a.com/2, sem pubDate.
ATOM = entry "Sinner wins", <link href="https://b.com/x"/>, updated "2026-11-25T10:00:00Z", summary "Text".
GOOGLE = item "Alcaraz lamenta - ge", link news.google.com/..., pubDate GMT, <source url="https://ge.globo.com">ge</source>.

def test_rss_basico():  # titulo "Fonseca vence & avança", publicadoEm "2026-11-25T20:11:09Z", trecho "João venceu"
def test_rss_sem_data():  # publicadoEm is None
def test_atom():  # titulo "Sinner wins", link "https://b.com/x", publicadoEm "2026-11-25T10:00:00Z", idioma da fonte
def test_google_tira_sufixo():  # titulo "Alcaraz lamenta", fonte "ge", via "Google Notícias"
def test_xml_invalido():  # interpretar_feed(b"<html>oops", fonte) raises ValueError
def test_para_iso_formatos():  # "2026-11-26T00:22:58+01:00" -> "2026-11-25T23:22:58Z"; "lixo" -> None; None -> None
def test_limpar_texto():  # "<p>A&nbsp;&amp;  B</p>" -> "A & B"
```

- [ ] **Step 2: Rodar e ver falhar** — `python -m unittest tests.test_feeds -v` → erro de import.
- [ ] **Step 3: Implementar `coletor/feeds.py`** — `xml.etree.ElementTree.fromstring`, ignorar namespace pelo sufixo da tag (`tag.split('}')[-1]`); `email.utils.parsedate_to_datetime` e `datetime.fromisoformat` (trocar `Z` por `+00:00` antes, por causa do 3.10); `html.unescape` + regex de tags; trecho cortado em 500.
- [ ] **Step 4: Rodar e ver passar** — `python -m unittest tests.test_feeds -v` → OK.
- [ ] **Step 5: Commit** — `git add coletor tests && git commit -m "feat: leitura de feeds RSS e Atom"`

### Task 2: Coletor completo e lista de fontes

**Files:**
- Create: `coletor/coletar.py`, `coletor/fontes.json`, `.gitignore`
- Test: `tests/test_coletar.py`

**Interfaces:**
- Consumes: `baixar`, `interpretar_feed`, `limpar_texto` (Task 1).
- Produces:
  - `normalizar_titulo(t: str) -> str` — minúsculas, sem acentos, sem pontuação, espaços únicos.
  - `id_estavel(link: str) -> str` — sha1 do link sem `utm_*`/fragmento, 16 hex.
  - `eh_tenis(item: dict, exige_termo: bool) -> bool`
  - `mesclar(antigas: list[dict], novas: list[dict], agora: datetime) -> list[dict]` — dedup por id e por título normalizado (fica a mais antiga em `coletadoEm`), descarta `publicadoEm` com mais de 3 dias, ordena por data desc, corta em 600. Novas sem `publicadoEm` recebem `coletadoEm`.
  - `precisa_salvar(anterior: dict | None, novas_noticias: list[dict], agora: datetime) -> bool` — True se a lista de ids mudou ou se `anterior["atualizadoEm"]` tem 2 h ou mais.
  - `main(caminho_saida="noticias.json")` — baixa todas as fontes em paralelo (`ThreadPoolExecutor`, 8 workers); fonte com exceção vai para `fontesComFalha` e não derruba o resto; grava só se `precisa_salvar`; imprime resumo `"N novas, M total, falhas: [...]"`.

Filtro (`eh_tenis`), sobre `titulo + " " + trecho` normalizados:
- Bloqueia se contiver: `tenis de mesa`, `table tennis`, `beach tennis`, `beach tenis`, `padel`, `pickleball`, `sneaker`, `calcado`, `sapatilha`, `placar ao vivo`, `resultados ao vivo`, `live score`, `sofascore`, `flashscore`, `palpite`, `prognostico`, `odds`, `aposta`, `betting`, `prediction`.
- Se `exige_termo`, exige ao menos um de: `atp`, `wta`, `tenista`, `tennis`, `grand slam`, `wimbledon`, `roland garros`, `us open`, `australian open`, `challenger`, `itf`, `copa davis`, `davis cup`, `billie jean`, `sinner`, `alcaraz`, `djokovic`, `fonseca`, `haddad`, `sabalenka`, `swiatek`, `gauff`, `zverev`, `medvedev`, `masters 1000`, `atp finals`, `wta finals`.

`fontes.json` (portais com `exigeTermo: false`; buscas do Google com `exigeTermo: true, google: true`). Buscas Google: base `https://news.google.com/rss/search?hl=pt-BR&gl=BR&ceid=BR:pt-419&q=` com `t%C3%AAnis+when:1d`, `t%C3%AAnis+(ATP+OR+WTA)+when:1d`, `%22Jo%C3%A3o+Fonseca%22+when:2d`, `%22Bia+Haddad%22+when:3d`, `(Sinner+OR+Alcaraz+OR+Djokovic)+when:1d`; Portugal: `https://news.google.com/rss/search?hl=pt-PT&gl=PT&ceid=PT:pt-150&q=t%C3%A9nis+ATP+when:2d`. Portais: as seis URLs brasileiras da spec, mais `https://feeds.bbci.co.uk/sport/tennis/rss.xml`, `https://www.espn.com/espn/rss/tennis/news`, `https://www.theguardian.com/sport/tennis/rss`, `https://www.skysports.com/rss/12110`, `https://sports.yahoo.com/tennis/rss/`, `https://www.tennismajors.com/feed`, `https://tennishead.net/feed/`, `https://www.tennis365.com/feed`, `https://www.ubitennis.net/feed/`, `https://www.sportskeeda.com/feed/tennis`, `https://www.essentiallysports.com/category/tennis/feed/`, `https://dwh.lequipe.fr/api/edito/rss?path=/Tennis/`.

- [ ] **Step 1: Escrever os testes**

```python
def test_normalizar_titulo():  # "Fonseca  VENCE: João!" -> "fonseca vence joao"
def test_id_estavel_ignora_utm():  # id_estavel("https://a.com/x?utm_source=y#z") == id_estavel("https://a.com/x")
def test_eh_tenis_bloqueia():  # "Torneio de tênis de mesa" -> False; "Palpite Sinner x Alcaraz" -> False
def test_eh_tenis_exige_termo():  # "Novo tênis da Nike" exige=True -> False; "Fonseca vence" exige=True -> True; "Qualquer" exige=False -> True
def test_mesclar_dedup_titulo_google():  # "Alcaraz lamenta" (ge direto) + "Alcaraz lamenta" (Google) -> 1 item
def test_mesclar_descarta_velhas():  # publicadoEm 4 dias atrás -> fora
def test_mesclar_sem_data_usa_coleta():  # publicadoEm None -> publicadoEm == coletadoEm
def test_mesclar_limite_600():  # 700 itens -> 600, mais recentes primeiro
def test_precisa_salvar():  # mesmos ids e 30 min -> False; mesmos ids e 2h -> True; id novo -> True; anterior None -> True
def test_main_fonte_quebrada(): # baixar() trocado por mock que lança numa fonte: a outra entra, a quebrada vai para fontesComFalha
```

- [ ] **Step 2: Rodar e ver falhar** — `python -m unittest tests.test_coletar -v`.
- [ ] **Step 3: Implementar `coletor/coletar.py` e `coletor/fontes.json`.** `main` lê `noticias.json` anterior se existir; roda como `python coletor/coletar.py` (ajustar `sys.path` para importar `feeds`).
- [ ] **Step 4: Rodar e ver passar** — `python -m unittest discover -s tests -v` → OK.
- [ ] **Step 5: Rodar de verdade** — `python coletor/coletar.py` → centenas de notícias, no máximo 3 fontes com falha; conferir 15 títulos aleatórios: nenhum de tênis de mesa, calçado ou aposta.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: coletor de notícias de tênis"`

### Task 3: Repositório e robô no GitHub

**Files:**
- Create: `.github/workflows/coletar.yml`, `README.md` (3 linhas: o que é, que é só depósito)

**Interfaces:**
- Consumes: `python coletor/coletar.py` (Task 2).
- Produces: `https://github.com/gomide83/noticias-tenis` com `noticias.json` atualizado pelo robô.

Workflow: `on: schedule: cron "*/30 * * * *"` e `workflow_dispatch`; `permissions: contents: write`; `concurrency: coletar`; job `ubuntu-latest`, `timeout-minutes: 10`; passos: checkout, setup-python 3.12, `python -m unittest discover -s tests`, `python coletor/coletar.py`, commit como `github-actions[bot]` só se `noticias.json` mudou, `git pull --rebase` e `git push`.

- [ ] **Step 1: Criar repositório público** — `git init -b main`, commit das Tasks 1-2, `gh repo create gomide83/noticias-tenis --public --source . --push`.
- [ ] **Step 2: Subir o workflow** — commit + push.
- [ ] **Step 3: Disparar manualmente** — `gh workflow run coletar.yml` e `gh run watch` → sucesso.
- [ ] **Step 4: Verificar** — `git pull` traz commit do robô; `noticias.json` com `atualizadoEm` de minutos atrás.

### Task 4: Scripts auxiliares da tarefa

**Files:**
- Create: `tarefa/preparar.py`, `tarefa/montar_lote.py`
- Test: `tests/test_preparar.py`, `tests/test_montar_lote.py`

**Interfaces:**
- Consumes: formato de `noticias.json` (Task 2); arquivos salvos pelo `ArtifactData` com `out_dir` (`<out_dir>/meta/tratados.json`, `<out_dir>/noticias/*.json`). O formato exato desses arquivos é conferido na Task 6; os leitores aceitam o corpo do documento no topo ou dentro de `"data"`.
- Produces:
  - `preparar.py`: `carregar_corpo(caminho: str) -> dict`; `selecionar_candidatos(noticias: list[dict], tratados: set[str], agora: datetime, max_idade_h: int = 24, limite: int = 80) -> list[dict]` (não tratados, dentro de 24 h, mais recentes primeiro, campos `id, titulo, fonte, via, idioma, publicadoEm, trecho[:300]`). CLI: `python tarefa/preparar.py --noticias noticias.json --db tarefa/trabalho/db --saida tarefa/trabalho/candidatos.json` grava `{robo: {atualizadoEm, fontesComFalha}, jaPublicadas: [títulos das últimas 24h], candidatos: [...]}` e imprime `"N candidatos"`.
  - `montar_lote.py`: `montar_noticia(fato: dict, por_id: dict, agora: datetime) -> tuple[str, dict] | None`; `novos_tratados(antigos: list[str], decisoes: dict, ids_atuais: set[str]) -> list[str]`. CLI: `python tarefa/montar_lote.py --noticias noticias.json --db tarefa/trabalho/db --decisoes tarefa/trabalho/decisoes.json --saida tarefa/trabalho/lote` grava um arquivo por documento e `lote/writes.json` (lista de entradas `{op, collection, doc_id, file_path}` com caminhos absolutos, pronta para o `batch`), e imprime quantos fatos e descartes.

Formato de `decisoes.json` (escrito pelo Claude): `{"fatos": [{"titulo", "resumo", "categoria", "idsRobo": [...]}], "descartados": [ids]}`.

Regras de `montar_noticia`: ignora ids desconhecidos; sem id válido → `None`; categoria fora da lista → `"Outros"`; `fontes` = `{nome: fonte, link}` de cada item do robô, sem repetir nome; `publicadoEm` = o mais recente dos itens; `criadoEm` = agora; `docId = "n-" + primeiro id válido`.
`novos_tratados` = antigos ∪ ids dos fatos ∪ descartados, mantendo só os que ainda existem em `ids_atuais`.
`meta/estado` = `{atualizadoEm: agora, coletaEm: robo.atualizadoEm, fontesComFalha, novasNaRodada: nº de fatos}`.

- [ ] **Step 1: Escrever os testes**

```python
def test_seleciona_nao_tratados_recentes():  # 3 itens: 1 tratado, 1 de 30h, 1 novo -> só o novo
def test_limite_e_ordem():  # 100 novos -> 80, o primeiro é o mais recente
def test_trecho_cortado():  # trecho de 1000 chars -> 300
def test_carregar_corpo_aceita_data():  # {"data": {"ids": ["a"]}} e {"ids": ["a"]} -> {"ids": ["a"]}
def test_montar_noticia_fontes_do_robo():  # idsRobo ["a","b"] -> fontes com links do noticias.json, publicadoEm o menor
def test_montar_noticia_id_invalido():  # idsRobo ["zzz"] -> None
def test_categoria_invalida_vira_outros():  # "Futebol" -> "Outros"
def test_novos_tratados():  # antigos ["x","velho"], fato ["a"], descartados ["b"], atuais {"x","a","b"} -> {"x","a","b"}
```

- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar os dois scripts.**
- [ ] **Step 4: Rodar e ver passar** — `python -m unittest discover -s tests -v`.
- [ ] **Step 5: Commit e push.**

### Task 5: Página privada do Claude

**Files:**
- Create: `pagina/noticias-tenis.html`

**Interfaces:**
- Consumes: formato do banco (seção acima).
- Produces: URL do Artifact (vai para o `tarefa/PROMPT.md`).

Antes de escrever: `Artifact` `action: "quickstart"` com `intent: "other"`, e seguir a orientação de design que ele devolver. Publicar com `capabilities: {db: {rules: [{path: "", read: "view", write: "owner"}]}}`, ícone `news`.

Comportamento:
- `const db = await claude.use("db")`; `null` → mensagem "Abra no claude.ai para ver as notícias".
- Uma assinatura em `noticias` (`orderBy("publicadoEm","desc").limit(300)`) e uma em `meta/estado`; timer de 10 s para aviso de "não foi possível carregar ainda".
- Cabeçalho "Notícias de Tênis" + "Atualizado há X min" (de `meta/estado.atualizadoEm`).
- Faixa de aviso se `atualizadoEm` > 2 h: "O Claude não atualiza há X horas. Abra o app do Claude no PC." Se `coletaEm` > 3 h: "O robô de coleta está parado há X horas."
- Filtros: Todas, ATP, WTA, Brasileiros, Grand Slam, Outros (derivados em memória, sem nova assinatura).
- Cartão: etiqueta de categoria, título, resumo, "há X min", fontes (link só se `https://`, `rel="noopener"`, `target="_blank"`).
- Todo texto do banco via `textContent`.
- Estado vazio: "Ainda não há notícias. O Claude publica as primeiras na próxima rodada."
- Horários relativos re-renderizam a cada minuto (sem gravar nada).

- [ ] **Step 1: Quickstart + orientação de design.**
- [ ] **Step 2: Escrever a página e publicar.**
- [ ] **Step 3: Verificar** — `ArtifactData list` de `noticias` (vazio, sem erro); gravar `noticias/teste`, conferir; com `as_level: "view"` a gravação é recusada; apagar o teste.

### Task 6: Instruções da tarefa e primeira rodada manual

**Files:**
- Create: `tarefa/PROMPT.md`

**Interfaces:**
- Consumes: Tasks 3, 4 e 5 (URL do Artifact, scripts, repositório).

`PROMPT.md` é autossuficiente e diz, nesta ordem:
1. `git -C C:/Users/Rafae/Claude/Tomas/Site pull --ff-only` (se falhar: `curl -sL https://raw.githubusercontent.com/gomide83/noticias-tenis/main/noticias.json -o <Site>/noticias.json`).
2. Limpar `tarefa/trabalho/`. `ArtifactData get` de `meta/tratados` e `meta/estado` com `out_dir: tarefa/trabalho/db` (anotar `version`; inexistentes na primeira vez); `ArtifactData query` de `noticias` com `criadoEm >= agora-24h`, mesmo `out_dir`.
3. `python tarefa/preparar.py ...`. Se 0 candidatos: só atualizar `meta/estado` e encerrar.
4. Ler `candidatos.json`. Montar até 15 fatos: juntar itens do mesmo fato; descartar o que não é tênis do esporte e o que repete `jaPublicadas`; priorizar Grand Slams, top 10, brasileiros, mais recentes. Título e resumo (2 a 4 frases) em português do Brasil, traduzindo do inglês/francês, sem fatos que não estejam no título/trecho; abrir a matéria só se o trecho for curto demais e o fato for importante. Categoria: `Brasileiros` se o protagonista é brasileiro; senão `Grand Slam` se é sobre um Slam; senão `ATP`/`WTA`; senão `Outros`. Itens deixados de fora só por causa do limite de 15 NÃO entram em `descartados`.
5. Gravar `decisoes.json`; rodar `montar_lote.py`.
6. `ArtifactData batch` com as entradas de `writes.json`, acrescentando `if_version` em `meta/tratados` e `meta/estado` quando já existirem (no máximo 50 por batch).
7. `ArtifactData query` de `noticias` com `criadoEm < agora-7d`; apagar em batch.
8. Responder em uma linha: quantos fatos publicados, descartados e falhas de fonte.

- [ ] **Step 1: Escrever `PROMPT.md`** com a URL do Artifact da Task 5.
- [ ] **Step 2: Executar o PROMPT.md à mão nesta sessão**, conferindo o formato real dos arquivos do `out_dir` (ajustar `carregar_corpo` e testes se preciso).
- [ ] **Step 3: Verificar** — `ArtifactData list` de `noticias` mostra até 15 docs em português; a página mostra os cartões e os filtros funcionam.
- [ ] **Step 4: Commit e push.**

### Task 7: Agendamento a cada 30 minutos

- [ ] **Step 1: Criar a tarefa** — `create_scheduled_task` com `taskId: "noticias-tenis"`, título "Notícias de Tênis (a cada 30 min)", `cronExpression: "*/30 * * * *"`, `prompt`: conteúdo do `PROMPT.md`.
- [ ] **Step 2: Rodar agora** — `run_scheduled_task`; `list_task_runs` → rodada concluída sem ficar parada pedindo permissão.
- [ ] **Step 3: Verificar** — `meta/estado.atualizadoEm` mudou; nenhuma notícia duplicada em relação à rodada manual.
