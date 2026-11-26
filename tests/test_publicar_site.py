import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import publicar_site  # noqa: E402
from publicar_site import juntar, renderizar_pagina, renderizar_sitemap  # noqa: E402

AGORA = datetime(2026, 11, 26, 14, 30, 0, tzinfo=timezone.utc)  # 11:30 em Brasília


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


class TestJuntar(unittest.TestCase):
    def test_junta_sem_repetir_e_ordena(self):
        antigas = [noticia("n-a", horas_atras=5)]
        novas = [noticia("n-b", horas_atras=1), dict(noticia("n-a", horas_atras=5), titulo="Novo título")]
        resultado = juntar(antigas, novas, AGORA)
        self.assertEqual([n["id"] for n in resultado], ["n-b", "n-a"])
        self.assertEqual(resultado[1]["titulo"], "Novo título")

    def test_descarta_mais_de_7_dias(self):
        resultado = juntar([noticia("n-velha", horas_atras=24 * 8)], [noticia("n-nova")], AGORA)
        self.assertEqual([n["id"] for n in resultado], ["n-nova"])


class TestPagina(unittest.TestCase):
    def test_escapa_texto_e_so_aceita_https(self):
        perigosa = noticia("n-x", titulo='<script>alert("x")</script>', link="javascript:alert(1)")
        html = renderizar_pagina([perigosa], AGORA)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("javascript:alert", html)

    def test_agrupa_por_dia_no_horario_de_brasilia(self):
        # 01:30 UTC do dia 26 ainda é dia 25 em Brasília (22:30)
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
        self.assertIn('rel="canonical" href="https://gomide83.github.io/noticias-tenis/"', html)
        self.assertIn('data-categoria="WTA"', html)
        self.assertIn("Atualizado em 26/11/2026 às 11:30", html)

    def test_pagina_vazia(self):
        html = renderizar_pagina([], AGORA)
        self.assertIn("Ainda não há notícias", html)

    def test_sitemap(self):
        xml = renderizar_sitemap(AGORA)
        self.assertIn("<loc>https://gomide83.github.io/noticias-tenis/</loc>", xml)
        self.assertIn("<lastmod>2026-11-26T14:30:00+00:00</lastmod>", xml)


class TestMain(unittest.TestCase):
    def test_main_le_lote_e_grava_site(self):
        raiz = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, raiz, True)
        lote = os.path.join(raiz, "tarefa", "trabalho", "lote", "noticias")
        os.makedirs(lote)
        dados = noticia("n-novo")
        dados.pop("id")
        with open(os.path.join(lote, "n-novo.json"), "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False)
        os.makedirs(os.path.join(raiz, "dados"))
        with open(os.path.join(raiz, "dados", "publicadas.json"), "w", encoding="utf-8") as arquivo:
            json.dump([noticia("n-antigo", horas_atras=3)], arquivo)

        publicar_site.main(["--raiz", raiz, "--lote", os.path.join(raiz, "tarefa", "trabalho", "lote"),
                            "--sem-git"], agora=AGORA)

        with open(os.path.join(raiz, "dados", "publicadas.json"), encoding="utf-8") as arquivo:
            publicadas = json.load(arquivo)
        self.assertEqual([n["id"] for n in publicadas], ["n-novo", "n-antigo"])
        for nome in ("index.html", "sitemap.xml", "robots.txt"):
            self.assertTrue(os.path.exists(os.path.join(raiz, "site", nome)), nome)
        with open(os.path.join(raiz, "site", "robots.txt"), encoding="utf-8") as arquivo:
            self.assertIn("Sitemap: https://gomide83.github.io/noticias-tenis/sitemap.xml", arquivo.read())


if __name__ == "__main__":
    unittest.main()
