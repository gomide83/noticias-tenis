import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import preparar  # noqa: E402
from preparar import carregar_corpo, selecionar_candidatos  # noqa: E402

AGORA = datetime(2026, 11, 25, 22, 0, 0, tzinfo=timezone.utc)


def iso(data):
    return data.strftime("%Y-%m-%dT%H:%M:%SZ")


def noticia(id_, horas_atras=1, trecho="texto"):
    return {
        "id": id_, "titulo": f"Título {id_}", "link": f"https://a.com/{id_}", "fonte": "Portal",
        "via": "", "idioma": "pt", "publicadoEm": iso(AGORA - timedelta(hours=horas_atras)),
        "coletadoEm": iso(AGORA), "trecho": trecho,
    }


class TestSelecionar(unittest.TestCase):
    def test_seleciona_nao_tratados_recentes(self):
        noticias = [noticia("tratado"), noticia("velho", horas_atras=30), noticia("novo")]
        candidatos = selecionar_candidatos(noticias, {"tratado"}, AGORA)
        self.assertEqual([c["id"] for c in candidatos], ["novo"])

    def test_limite_e_ordem(self):
        noticias = [noticia(f"n{i}", horas_atras=i / 10) for i in range(100)]
        candidatos = selecionar_candidatos(noticias, set(), AGORA)
        self.assertEqual(len(candidatos), 80)
        self.assertEqual(candidatos[0]["id"], "n0")

    def test_campos_e_trecho_cortado(self):
        candidato = selecionar_candidatos([noticia("a", trecho="x" * 1000)], set(), AGORA)[0]
        self.assertEqual(len(candidato["trecho"]), 300)
        self.assertEqual(set(candidato), {"id", "titulo", "fonte", "via", "idioma", "publicadoEm", "trecho"})


class TestCarregarCorpo(unittest.TestCase):
    def test_carregar_corpo_aceita_data(self):
        with tempfile.TemporaryDirectory() as pasta:
            for nome, conteudo in (("a.json", {"data": {"ids": ["a"]}, "version": 3}), ("b.json", {"ids": ["a"]})):
                caminho = os.path.join(pasta, nome)
                with open(caminho, "w", encoding="utf-8") as arquivo:
                    json.dump(conteudo, arquivo)
                self.assertEqual(carregar_corpo(caminho), {"ids": ["a"]})


class TestMain(unittest.TestCase):
    def test_main_monta_arquivo_de_candidatos(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho_noticias = os.path.join(pasta, "noticias.json")
            with open(caminho_noticias, "w", encoding="utf-8") as arquivo:
                json.dump({"atualizadoEm": iso(AGORA), "fontesComFalha": ["X"],
                           "noticias": [noticia("a"), noticia("b")]}, arquivo)
            db = os.path.join(pasta, "db")
            os.makedirs(os.path.join(db, "meta"))
            os.makedirs(os.path.join(db, "noticias"))
            with open(os.path.join(db, "meta", "tratados.json"), "w", encoding="utf-8") as arquivo:
                json.dump({"ids": ["a"]}, arquivo)
            with open(os.path.join(db, "noticias", "n-z.json"), "w", encoding="utf-8") as arquivo:
                json.dump({"titulo": "Já publicada"}, arquivo)
            saida = os.path.join(pasta, "candidatos.json")

            preparar.main(["--noticias", caminho_noticias, "--db", db, "--saida", saida], agora=AGORA)

            with open(saida, encoding="utf-8") as arquivo:
                resultado = json.load(arquivo)
        self.assertEqual([c["id"] for c in resultado["candidatos"]], ["b"])
        self.assertEqual(resultado["jaPublicadas"], ["Já publicada"])
        self.assertEqual(resultado["robo"], {"atualizadoEm": iso(AGORA), "fontesComFalha": ["X"]})

    def test_main_sem_banco_ainda(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho_noticias = os.path.join(pasta, "noticias.json")
            with open(caminho_noticias, "w", encoding="utf-8") as arquivo:
                json.dump({"atualizadoEm": iso(AGORA), "fontesComFalha": [], "noticias": [noticia("a")]}, arquivo)
            saida = os.path.join(pasta, "candidatos.json")
            preparar.main(["--noticias", caminho_noticias, "--db", os.path.join(pasta, "nao-existe"),
                           "--saida", saida], agora=AGORA)
            with open(saida, encoding="utf-8") as arquivo:
                resultado = json.load(arquivo)
        self.assertEqual([c["id"] for c in resultado["candidatos"]], ["a"])
        self.assertEqual(resultado["jaPublicadas"], [])


if __name__ == "__main__":
    unittest.main()
