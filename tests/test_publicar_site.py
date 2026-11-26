import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import publicar_site  # noqa: E402
from publicar_site import (juntar, renderizar_noticia, renderizar_pagina, renderizar_ranking,  # noqa: E402
                           renderizar_sitemap, renderizar_sobre, slug)

AGORA = datetime(2026, 11, 26, 14, 30, 0, tzinfo=timezone.utc)  # 11:30 em Brasília
URL = "https://gomide83.github.io/noticias-tenis/"


def iso(data):
    return data.strftime("%Y-%m-%dT%H:%M:%SZ")


def noticia(doc_id, horas_atras=1, categoria="ATP", titulo=None, link="https://ge.globo.com/x"):
    return {
        "id": doc_id,
        "titulo": titulo or f"Título {doc_id}",
        "resumo": f"Resumo {doc_id}.",
        "categoria": categoria,
        "fontes": [{"nome": "ge", "link": link, "idioma": "pt"}],
        "publicadoEm": iso(AGORA - timedelta(hours=horas_atras)),
        "criadoEm": iso(AGORA - timedelta(hours=horas_atras)),
        "idsRobo": [doc_id[2:]],
    }


RANKING = {
    "atualizadoEm": "2026-11-19T08:00:00Z", "fonte": "ESPN", "buscadoEm": "2026-11-26T14:00:00Z",
    "jogadores": [
        {"posicao": 1, "anterior": 1, "nome": "Alexander Zverev", "pais": "GER", "paisNome": "Germany",
         "pontos": 10350},
        {"posicao": 6, "anterior": 8, "nome": "Arthur Fils", "pais": "FRA", "paisNome": "France", "pontos": 3825},
        {"posicao": 7, "anterior": 6, "nome": "<b>Cobolli</b>", "pais": "ITA", "paisNome": "Italy", "pontos": 3680},
        {"posicao": 46, "anterior": None, "nome": "Joao Fonseca", "pais": "BRA", "paisNome": "Brazil",
         "pontos": 1200},
    ],
}


RANKING_WTA = {
    "atualizadoEm": "2026-11-19T08:00:00Z", "fonte": "ESPN", "buscadoEm": "2026-11-26T14:00:00Z",
    "jogadores": [
        {"posicao": 1, "anterior": 1, "nome": "Elena Rybakina", "pais": "KAZ", "paisNome": "Kazakhstan",
         "pontos": 8099},
        {"posicao": 2, "anterior": 2, "nome": "Mirra Andreeva", "pais": "RUS", "paisNome": "Russia", "pontos": 7806},
    ],
}


def resposta_espn(circuito):
    nome = "Jogador" if circuito == "atp" else "Jogadora"
    ranks = [{"current": i, "previous": i, "points": 5000.0 - i,
              "athlete": {"displayName": f"{nome} {i}", "citizenshipCountry": "ESP", "flagAltText": "Spain"}}
             for i in range(1, 101)]
    return {"rankings": [{"type": circuito, "update": "2026-11-19T08:00Z", "ranks": ranks}]}


class TestJuntar(unittest.TestCase):
    def test_junta_sem_repetir_e_ordena(self):
        antigas = [noticia("n-a", horas_atras=5)]
        novas = [noticia("n-b", horas_atras=1), dict(noticia("n-a", horas_atras=5), titulo="Novo título")]
        resultado = juntar(antigas, novas, AGORA)
        self.assertEqual([n["id"] for n in resultado], ["n-b", "n-a"])
        self.assertEqual(resultado[1]["titulo"], "Novo título")

    def test_guarda_30_dias(self):
        resultado = juntar([noticia("n-31", horas_atras=24 * 31), noticia("n-10", horas_atras=24 * 10)],
                           [noticia("n-nova")], AGORA)
        self.assertEqual([n["id"] for n in resultado], ["n-nova", "n-10"])


class TestSlug(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slug({"id": "n-c74208cd0576e7b0", "titulo": "Itália sofre, decide nas duplas!"}),
                         "italia-sofre-decide-nas-duplas-76e7b0")

    def test_slug_longo_e_estranho(self):
        s = slug({"id": "n-abc123", "titulo": "<b>" + "palavra " * 30})
        self.assertLessEqual(len(s), 80)
        self.assertRegex(s, r"^[a-z0-9-]+$")


class TestPaginaInicial(unittest.TestCase):
    def test_escapa_texto_e_so_aceita_https(self):
        perigosa = noticia("n-x", titulo='<script>alert("x")</script>', link="javascript:alert(1)")
        html = renderizar_pagina([perigosa], AGORA)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("javascript:alert", html)

    def test_agrupa_por_dia_no_horario_de_brasilia(self):
        madrugada = dict(noticia("n-m"), publicadoEm="2026-11-26T01:30:00Z")
        html = renderizar_pagina([noticia("n-d", horas_atras=1), madrugada], AGORA)
        self.assertIn("quinta-feira, 26 de novembro", html)
        self.assertIn("quarta-feira, 25 de novembro", html)
        self.assertIn("22:30", html)

    def test_tem_dados_para_o_google(self):
        html = renderizar_pagina([noticia("n-a", categoria="WTA")], AGORA)
        self.assertIn("<title>Tênis Notícias</title>", html)
        self.assertIn('<html lang="pt-BR">', html)
        self.assertIn('name="description"', html)
        self.assertIn(f'rel="canonical" href="{URL}"', html)
        self.assertIn(f'property="og:image" content="{URL}previa.png"', html)
        self.assertIn('data-categoria="WTA"', html)
        self.assertIn("Atualizado em 26/11/2026 às 11:30", html)

    def test_titulos_levam_a_pagina_da_noticia(self):
        n = noticia("n-abcdef123456", titulo="Fonseca vence")
        html = renderizar_pagina([n], AGORA)
        self.assertIn('href="noticias/fonseca-vence-123456.html"', html)
        self.assertIn('href="sobre.html"', html)

    def test_pagina_inicial_mostra_so_7_dias(self):
        html = renderizar_pagina([noticia("n-nova", titulo="Nova"), noticia("n-velha", horas_atras=24 * 10,
                                                                            titulo="Velha")], AGORA)
        self.assertIn("Nova", html)
        self.assertNotIn("Velha", html)

    def test_pagina_vazia(self):
        self.assertIn("Ainda não há notícias", renderizar_pagina([], AGORA))


class TestPaginaDaNoticia(unittest.TestCase):
    def test_pagina_da_noticia(self):
        n = noticia("n-abcdef123456", titulo='Fonseca vence & "avança"', categoria="Brasileiros")
        html = renderizar_noticia(n, AGORA)
        self.assertIn("<title>Fonseca vence &amp; &quot;avança&quot; | Tênis Notícias</title>", html)
        self.assertIn(f'rel="canonical" href="{URL}noticias/fonseca-vence-avanca-123456.html"', html)
        self.assertIn('name="description" content="Resumo n-abcdef123456."', html)
        self.assertIn(f'property="og:image" content="{URL}previa.png"', html)
        self.assertIn('href="../"', html)
        self.assertIn('href="https://ge.globo.com/x"', html)
        self.assertIn("quinta-feira, 26 de novembro de 2026, às 10:30", html)

    def test_pagina_da_noticia_sem_fontes(self):
        n = dict(noticia("n-resumo"), fontes=[])
        self.assertIn("Resumo n-resumo.", renderizar_noticia(n, AGORA))


class TestRanking(unittest.TestCase):
    def test_pagina_do_ranking(self):
        html = renderizar_ranking(RANKING, AGORA)
        self.assertIn("<title>Ranking ATP | Tênis Notícias</title>", html)
        self.assertIn(f'rel="canonical" href="{URL}ranking.html"', html)
        self.assertIn("Alexander Zverev", html)
        self.assertIn("10.350", html)
        self.assertIn("Alemanha", html)
        self.assertIn("19/11/2026", html)
        self.assertIn("ESPN", html)

    def test_mostra_quem_subiu_e_quem_caiu(self):
        html = renderizar_ranking(RANKING, AGORA)
        self.assertIn("Subiu 2 posições", html)
        self.assertIn("Caiu 1 posição", html)
        self.assertIn("Manteve a posição", html)

    def test_destaca_brasileiros_e_escapa_nomes(self):
        html = renderizar_ranking(RANKING, AGORA)
        self.assertIn('<tr class="br">', html)
        self.assertIn("Brasil", html)
        self.assertNotIn("<b>Cobolli</b>", html)
        self.assertIn("&lt;b&gt;Cobolli&lt;/b&gt;", html)

    def test_pagina_do_ranking_da_wta(self):
        html = renderizar_ranking(RANKING_WTA, AGORA, "wta")
        self.assertIn("<title>Ranking WTA | Tênis Notícias</title>", html)
        self.assertIn(f'rel="canonical" href="{URL}ranking-wta.html"', html)
        self.assertIn("feminino", html)
        self.assertIn("Elena Rybakina", html)
        self.assertIn("Cazaquistão", html)
        self.assertIn("Nenhuma brasileira está entre as 100 primeiras", html)
        self.assertIn('<th scope="col">Jogadora</th>', html)

    def test_aviso_quando_nao_ha_brasileiro(self):
        so_estrangeiros = dict(RANKING, jogadores=RANKING["jogadores"][:3])
        self.assertIn("Nenhum brasileiro está entre os 100 primeiros", renderizar_ranking(so_estrangeiros, AGORA))

    def test_sem_ranking(self):
        self.assertIn("O ranking não está disponível agora", renderizar_ranking(None, AGORA))

    def test_todas_as_paginas_levam_ao_ranking(self):
        self.assertIn('href="ranking.html"', renderizar_pagina([noticia("n-a")], AGORA))
        self.assertIn('href="../ranking.html"', renderizar_noticia(noticia("n-a"), AGORA))
        self.assertIn('href="ranking.html"', renderizar_sobre(AGORA))
        self.assertIn('href="ranking-wta.html"', renderizar_pagina([noticia("n-a")], AGORA))
        self.assertIn('href="../ranking-wta.html"', renderizar_noticia(noticia("n-a"), AGORA))


class TestOutrasPaginas(unittest.TestCase):
    def test_sobre(self):
        html = renderizar_sobre(AGORA)
        self.assertIn("<title>Sobre | Tênis Notícias</title>", html)
        self.assertIn("Claude", html)
        self.assertIn(f'rel="canonical" href="{URL}sobre.html"', html)

    def test_sitemap(self):
        n = noticia("n-abcdef123456", titulo="Fonseca vence")
        xml = renderizar_sitemap([n], AGORA)
        self.assertIn(f"<loc>{URL}</loc>", xml)
        self.assertIn(f"<loc>{URL}sobre.html</loc>", xml)
        self.assertIn(f"<loc>{URL}ranking.html</loc>", xml)
        self.assertIn(f"<loc>{URL}ranking-wta.html</loc>", xml)
        self.assertIn(f"<loc>{URL}noticias/fonseca-vence-123456.html</loc>", xml)
        self.assertIn("<lastmod>2026-11-26T14:30:00+00:00</lastmod>", xml)
        self.assertIn("<lastmod>2026-11-26T13:30:00+00:00</lastmod>", xml)


class TestMain(unittest.TestCase):
    def test_main_le_lote_e_grava_site(self):
        raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, raiz, True)
        lote = os.path.join(raiz, "tarefa", "trabalho", "lote", "noticias")
        os.makedirs(lote)
        dados = noticia("n-novo000001", titulo="Notícia nova")
        dados.pop("id")
        with open(os.path.join(lote, "n-novo000001.json"), "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False)
        os.makedirs(os.path.join(raiz, "dados"))
        with open(os.path.join(raiz, "dados", "publicadas.json"), "w", encoding="utf-8") as arquivo:
            json.dump([noticia("n-antigo000002", horas_atras=3, titulo="Notícia antiga")], arquivo)
        pagina_velha = os.path.join(raiz, "site", "noticias", "sumiu-000000.html")
        os.makedirs(os.path.dirname(pagina_velha))
        open(pagina_velha, "w").close()

        publicar_site.main(["--raiz", raiz, "--lote", os.path.join(raiz, "tarefa", "trabalho", "lote"),
                            "--sem-git"], agora=AGORA, baixar_ranking=resposta_espn)

        with open(os.path.join(raiz, "dados", "publicadas.json"), encoding="utf-8") as arquivo:
            publicadas = json.load(arquivo)
        self.assertEqual([n["id"] for n in publicadas], ["n-novo000001", "n-antigo000002"])
        for nome in ("index.html", "sobre.html", "ranking.html", "ranking-wta.html", "sitemap.xml", "robots.txt",
                     "noticias/noticia-nova-000001.html", "noticias/noticia-antiga-000002.html"):
            self.assertTrue(os.path.exists(os.path.join(raiz, "site", nome)), nome)
        self.assertFalse(os.path.exists(pagina_velha))
        with open(os.path.join(raiz, "site", "robots.txt"), encoding="utf-8") as arquivo:
            self.assertIn(f"Sitemap: {URL}sitemap.xml", arquivo.read())
        with open(os.path.join(raiz, "dados", "ranking.json"), encoding="utf-8") as arquivo:
            self.assertEqual(len(json.load(arquivo)["jogadores"]), 100)
        with open(os.path.join(raiz, "site", "ranking.html"), encoding="utf-8") as arquivo:
            self.assertIn("Jogador 100", arquivo.read())
        with open(os.path.join(raiz, "dados", "ranking-wta.json"), encoding="utf-8") as arquivo:
            self.assertEqual(json.load(arquivo)["jogadores"][0]["nome"], "Jogadora 1")
        with open(os.path.join(raiz, "site", "ranking-wta.html"), encoding="utf-8") as arquivo:
            self.assertIn("Jogadora 100", arquivo.read())


if __name__ == "__main__":
    unittest.main()
