import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import ranking  # noqa: E402
from ranking import atualizar_ranking, interpretar_ranking, nome_do_pais  # noqa: E402

AGORA = datetime(2026, 11, 26, 14, 30, 0, tzinfo=timezone.utc)


def jogador(posicao, nome, pais="GER", alt="Germany", anterior=None, pontos=1000.0):
    return {"current": posicao, "previous": posicao if anterior is None else anterior,
            "points": pontos, "trend": "-",
            "athlete": {"displayName": nome, "citizenshipCountry": pais, "flagAltText": alt}}


def resposta_espn(qtd=120, update="2026-11-19T08:00Z", circuito="atp"):
    ranks = [jogador(i, f"Jogador {i}", pontos=10000.0 - i) for i in range(1, qtd + 1)]
    ranks[0] = jogador(1, "Alexander Zverev", pontos=10350.0)
    if qtd > 45:
        ranks[45] = jogador(46, "Joao Fonseca", "BRA", "Brazil", anterior=48, pontos=1200.0)
    return {"rankings": [{"name": circuito.upper(), "type": circuito, "update": update, "ranks": ranks}]}


class TestInterpretar(unittest.TestCase):
    def test_pega_os_100_primeiros_em_ordem(self):
        dados = resposta_espn()
        dados["rankings"][0]["ranks"].reverse()
        resultado = interpretar_ranking(dados)
        self.assertEqual(resultado["atualizadoEm"], "2026-11-19T08:00:00Z")
        self.assertEqual(len(resultado["jogadores"]), 100)
        self.assertEqual(resultado["jogadores"][0],
                         {"posicao": 1, "anterior": 1, "nome": "Alexander Zverev", "pais": "GER",
                          "paisNome": "Germany", "pontos": 10350})
        self.assertEqual(resultado["jogadores"][45]["nome"], "Joao Fonseca")
        self.assertEqual(resultado["jogadores"][45]["anterior"], 48)
        self.assertEqual(resultado["jogadores"][-1]["posicao"], 100)

    def test_ignora_linhas_quebradas(self):
        dados = resposta_espn()
        dados["rankings"][0]["ranks"][1] = {"current": "x", "athlete": None}
        resultado = interpretar_ranking(dados)
        self.assertNotIn(2, [j["posicao"] for j in resultado["jogadores"]])

    def test_ranking_da_wta(self):
        resultado = interpretar_ranking(resposta_espn(circuito="wta"), circuito="wta")
        self.assertEqual(len(resultado["jogadores"]), 100)
        with self.assertRaises(ValueError):
            interpretar_ranking(resposta_espn(circuito="wta"), circuito="atp")

    def test_endereco_de_cada_circuito(self):
        self.assertTrue(ranking.URLS["atp"].endswith("/tennis/atp/rankings"))
        self.assertTrue(ranking.URLS["wta"].endswith("/tennis/wta/rankings"))

    def test_formato_estranho_da_erro(self):
        for dados in ({}, {"rankings": []}, {"rankings": [{"type": "wta", "ranks": []}]},
                      resposta_espn(qtd=5), "texto"):
            with self.assertRaises(ValueError):
                interpretar_ranking(dados)


class TestPais(unittest.TestCase):
    def test_nomes_em_portugues(self):
        self.assertEqual(nome_do_pais("BRA"), "Brasil")
        self.assertEqual(nome_do_pais("GER"), "Alemanha")
        self.assertEqual(nome_do_pais("SER"), "Sérvia")
        self.assertEqual(nome_do_pais("ROM"), "Romênia")
        self.assertEqual(nome_do_pais("PHI"), "Filipinas")
        self.assertEqual(nome_do_pais("XYZ", "Atlantis"), "Atlantis")
        self.assertEqual(nome_do_pais(None), "")


class TestAtualizar(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.pasta, True)
        self.caminho = os.path.join(self.pasta, "dados", "ranking.json")
        self.chamadas = 0

    def baixar(self):
        self.chamadas += 1
        return resposta_espn()

    def falhar(self):
        self.chamadas += 1
        raise OSError("sem internet")

    def test_baixa_e_guarda(self):
        resultado = atualizar_ranking(self.caminho, AGORA, self.baixar)
        self.assertEqual(resultado["buscadoEm"], "2026-11-26T14:30:00Z")
        with open(self.caminho, encoding="utf-8") as arquivo:
            self.assertEqual(json.load(arquivo)["jogadores"][0]["nome"], "Alexander Zverev")

    def test_usa_o_guardado_se_tem_menos_de_6_horas(self):
        atualizar_ranking(self.caminho, AGORA, self.baixar)
        atualizar_ranking(self.caminho, AGORA + timedelta(hours=5), self.baixar)
        self.assertEqual(self.chamadas, 1)
        atualizar_ranking(self.caminho, AGORA + timedelta(hours=7), self.baixar)
        self.assertEqual(self.chamadas, 2)

    def test_se_a_fonte_falha_fica_o_ultimo(self):
        atualizar_ranking(self.caminho, AGORA, self.baixar)
        resultado = atualizar_ranking(self.caminho, AGORA + timedelta(hours=7), self.falhar)
        self.assertEqual(resultado["jogadores"][0]["nome"], "Alexander Zverev")
        self.assertEqual(resultado["buscadoEm"], "2026-11-26T14:30:00Z")

    def test_se_a_fonte_muda_o_formato_fica_o_ultimo(self):
        atualizar_ranking(self.caminho, AGORA, self.baixar)
        resultado = atualizar_ranking(self.caminho, AGORA + timedelta(hours=7), lambda: {"novo": True})
        self.assertEqual(resultado["jogadores"][0]["nome"], "Alexander Zverev")

    def test_sem_nada_guardado_e_fonte_fora_do_ar(self):
        self.assertIsNone(atualizar_ranking(self.caminho, AGORA, self.falhar))

    def test_arquivo_guardado_corrompido(self):
        os.makedirs(os.path.dirname(self.caminho))
        with open(self.caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write("{quebrado")
        resultado = atualizar_ranking(self.caminho, AGORA, self.baixar)
        self.assertEqual(len(resultado["jogadores"]), 100)


if __name__ == "__main__":
    unittest.main()
