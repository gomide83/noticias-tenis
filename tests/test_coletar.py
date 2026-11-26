import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "coletor"))

import coletar  # noqa: E402
from coletar import eh_tenis, id_estavel, mesclar, normalizar_titulo, precisa_salvar  # noqa: E402

AGORA = datetime(2026, 11, 25, 22, 0, 0, tzinfo=timezone.utc)


def iso(data):
    return data.strftime("%Y-%m-%dT%H:%M:%SZ")


def item(titulo, link, publicado=AGORA, fonte="Portal", trecho=""):
    return {
        "titulo": titulo,
        "link": link,
        "fonte": fonte,
        "via": "",
        "idioma": "pt",
        "publicadoEm": iso(publicado) if publicado else None,
        "trecho": trecho,
    }


class TestNormalizacao(unittest.TestCase):
    def test_normalizar_titulo(self):
        self.assertEqual(normalizar_titulo("Fonseca  VENCE: João!"), "fonseca vence joao")

    def test_id_estavel_ignora_utm(self):
        self.assertEqual(id_estavel("https://a.com/x?utm_source=y#z"), id_estavel("https://a.com/x"))
        self.assertNotEqual(id_estavel("https://a.com/x?id=1"), id_estavel("https://a.com/x?id=2"))
        self.assertEqual(len(id_estavel("https://a.com/x")), 16)


class TestFiltro(unittest.TestCase):
    def test_eh_tenis_bloqueia(self):
        self.assertFalse(eh_tenis(item("Torneio de tênis de mesa reúne atletas", "https://a"), False))
        self.assertFalse(eh_tenis(item("Palpite Sinner x Alcaraz: odds e onde assistir", "https://a"), False))
        self.assertFalse(eh_tenis(item("Placar ao vivo de Cobolli x Kwon", "https://a"), False))
        self.assertFalse(eh_tenis(item("Brasil é campeão de beach tennis", "https://a"), False))

    def test_eh_tenis_nao_bloqueia_verbo_apostar(self):
        self.assertTrue(eh_tenis(item("Fonseca aposta no saque para vencer", "https://a"), True))

    def test_eh_tenis_exige_termo(self):
        self.assertFalse(eh_tenis(item("Novo tênis da Nike chega às lojas", "https://a"), True))
        self.assertTrue(eh_tenis(item("Fonseca vence e avança", "https://a"), True))
        self.assertTrue(eh_tenis(item("Qualquer manchete", "https://a"), False))

    def test_eh_tenis_nao_bloqueia_odds_e_apostas_comuns(self):
        self.assertTrue(eh_tenis(item("Fonseca defies the odds to reach the final", "https://a"), False))
        self.assertTrue(eh_tenis(item("Fonseca é uma das apostas do Brasil para 2027", "https://a"), False))
        self.assertFalse(eh_tenis(item("Sinner x Alcaraz: betting odds and tips", "https://a"), False))
        self.assertFalse(eh_tenis(item("Melhores casas de apostas para o ATP Finals", "https://a"), False))

    def test_eh_tenis_bloqueia_fonte(self):
        self.assertFalse(eh_tenis(item("Sinner x Alcaraz: quem vence?", "https://a", fonte="SportyTrader Portugal"), True))
        self.assertFalse(eh_tenis(item("Fonseca vence no ATP", "https://a", fonte="Flashscore.pt"), True))
        self.assertFalse(eh_tenis(item("Fonseca vence no ATP", "https://a", fonte="Instagram"), True))
        self.assertTrue(eh_tenis(item("Fonseca vence no ATP", "https://a", fonte="LANCE!"), True))

    def test_eh_tenis_olha_o_trecho(self):
        self.assertTrue(eh_tenis(item("Brasileira avança", "https://a", trecho="Partida válida pela WTA"), True))


class TestMesclar(unittest.TestCase):
    def test_mesclar_dedup_titulo_google(self):
        direto = item("Alcaraz lamenta Sinner longe das quadras", "https://ge.globo.com/1", fonte="ge")
        google = item("Alcaraz lamenta Sinner longe das quadras", "https://news.google.com/abc", fonte="ge")
        resultado = mesclar([], [direto, google], AGORA)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["link"], "https://ge.globo.com/1")

    def test_mesclar_mantem_antiga(self):
        antiga = dict(item("Fato", "https://a.com/1"), id=id_estavel("https://a.com/1"),
                      coletadoEm=iso(AGORA - timedelta(hours=5)))
        resultado = mesclar([antiga], [item("Fato", "https://a.com/1")], AGORA)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["coletadoEm"], iso(AGORA - timedelta(hours=5)))

    def test_mesclar_preenche_id_e_coleta(self):
        resultado = mesclar([], [item("Fato", "https://a.com/1")], AGORA)
        self.assertEqual(resultado[0]["id"], id_estavel("https://a.com/1"))
        self.assertEqual(resultado[0]["coletadoEm"], iso(AGORA))

    def test_mesclar_descarta_velhas(self):
        velha = item("Velha", "https://a.com/v", publicado=AGORA - timedelta(days=4))
        nova = item("Nova", "https://a.com/n")
        resultado = mesclar([], [velha, nova], AGORA)
        self.assertEqual([n["titulo"] for n in resultado], ["Nova"])

    def test_mesclar_sem_data_usa_coleta(self):
        resultado = mesclar([], [item("Sem data", "https://a.com/s", publicado=None)], AGORA)
        self.assertEqual(resultado[0]["publicadoEm"], resultado[0]["coletadoEm"])

    def test_mesclar_data_no_futuro_usa_coleta(self):
        futura = item("Futuro", "https://a.com/f", publicado=AGORA + timedelta(days=2))
        resultado = mesclar([], [futura], AGORA)
        self.assertEqual(resultado[0]["publicadoEm"], iso(AGORA))

    def test_mesclar_limite_600(self):
        novas = [item(f"Notícia {i}", f"https://a.com/{i}", publicado=AGORA - timedelta(minutes=i))
                 for i in range(700)]
        resultado = mesclar([], novas, AGORA)
        self.assertEqual(len(resultado), 600)
        self.assertEqual(resultado[0]["titulo"], "Notícia 0")
        self.assertEqual(resultado[-1]["titulo"], "Notícia 599")


class TestVistos(unittest.TestCase):
    def test_mesclar_marca_data_estimada(self):
        resultado = mesclar([], [item("Sem data", "https://a.com/s", publicado=None),
                                 item("Com data", "https://a.com/c")], AGORA)
        por_titulo = {n["titulo"]: n for n in resultado}
        self.assertTrue(por_titulo["Sem data"].get("dataEstimada"))
        self.assertFalse(por_titulo["Com data"].get("dataEstimada", False))

    def test_mesclar_nao_recicla_item_ja_visto(self):
        vistos = {id_estavel("https://a.com/s"): iso(AGORA - timedelta(days=4))}
        resultado = mesclar([], [item("Sem data", "https://a.com/s", publicado=None)], AGORA, vistos)
        self.assertEqual(resultado, [])

    def test_atualizar_vistos(self):
        noticias = mesclar([], [item("Sem data", "https://a.com/s", publicado=None),
                                item("Com data", "https://a.com/c")], AGORA)
        antigos = {"velho": iso(AGORA - timedelta(days=11)), "recente": iso(AGORA - timedelta(days=9))}
        vistos = coletar.atualizar_vistos(antigos, noticias, AGORA)
        self.assertEqual(set(vistos), {"recente", id_estavel("https://a.com/s")})


class TestPrecisaSalvar(unittest.TestCase):
    def setUp(self):
        self.noticias = [{"id": "a"}, {"id": "b"}]

    def anterior(self, horas):
        return {"atualizadoEm": iso(AGORA - timedelta(hours=horas)), "noticias": [{"id": "a"}, {"id": "b"}]}

    def test_precisa_salvar(self):
        self.assertFalse(precisa_salvar(self.anterior(0.5), self.noticias, AGORA))
        self.assertTrue(precisa_salvar(self.anterior(2), self.noticias, AGORA))
        self.assertTrue(precisa_salvar(self.anterior(0.5), self.noticias + [{"id": "c"}], AGORA))
        self.assertTrue(precisa_salvar(None, self.noticias, AGORA))


RSS_OK = b"""<rss><channel><item><title>Fonseca vence no ATP</title><link>https://ok.com/1</link>
<pubDate>Wed, 25 Nov 2026 20:00:00 +0000</pubDate></item></channel></rss>"""


class TestMain(unittest.TestCase):
    def test_main_fonte_quebrada(self):
        fontes = [
            {"id": "ok", "nome": "Portal OK", "url": "https://ok.com/feed", "idioma": "pt"},
            {"id": "q", "nome": "Portal Quebrado", "url": "https://quebrado.com/feed", "idioma": "pt"},
        ]

        def baixar_falso(url, timeout=15):
            if "quebrado" in url:
                raise OSError("timeout")
            return RSS_OK

        with tempfile.TemporaryDirectory() as pasta:
            saida = os.path.join(pasta, "noticias.json")
            with mock.patch.object(coletar, "baixar", baixar_falso):
                coletar.main(caminho_saida=saida, fontes=fontes, agora=AGORA)
            with open(saida, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        self.assertEqual(dados["fontesComFalha"], ["Portal Quebrado"])
        self.assertEqual([n["titulo"] for n in dados["noticias"]], ["Fonseca vence no ATP"])
        self.assertEqual(dados["atualizadoEm"], iso(AGORA))

    def test_main_grava_total_de_fontes_e_vistos(self):
        fontes = [{"id": "ok", "nome": "Portal OK", "url": "https://ok.com/feed", "idioma": "pt"}]
        with tempfile.TemporaryDirectory() as pasta:
            saida = os.path.join(pasta, "noticias.json")
            with mock.patch.object(coletar, "baixar", lambda url, timeout=15: RSS_OK):
                coletar.main(caminho_saida=saida, fontes=fontes, agora=AGORA)
            with open(saida, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        self.assertEqual(dados["totalFontes"], 1)
        self.assertEqual(dados["vistos"], {})

    def test_main_xml_invalido_vira_falha(self):
        fontes = [{"id": "h", "nome": "Portal HTML", "url": "https://h.com/feed", "idioma": "pt"}]
        with tempfile.TemporaryDirectory() as pasta:
            saida = os.path.join(pasta, "noticias.json")
            with mock.patch.object(coletar, "baixar", lambda url, timeout=15: b"<html>erro"):
                coletar.main(caminho_saida=saida, fontes=fontes, agora=AGORA)
            with open(saida, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
        self.assertEqual(dados["fontesComFalha"], ["Portal HTML"])
        self.assertEqual(dados["noticias"], [])


if __name__ == "__main__":
    unittest.main()
