import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import montar_lote  # noqa: E402
from montar_lote import montar_noticia, novos_tratados  # noqa: E402

AGORA = datetime(2026, 11, 25, 22, 0, 0, tzinfo=timezone.utc)


def iso(data):
    return data.strftime("%Y-%m-%dT%H:%M:%SZ")


def noticia(id_, fonte, horas_atras):
    return {"id": id_, "titulo": f"T {id_}", "link": f"https://{fonte.lower()}.com/{id_}", "fonte": fonte,
            "via": "", "idioma": "pt", "publicadoEm": iso(AGORA - timedelta(hours=horas_atras)),
            "coletadoEm": iso(AGORA), "trecho": ""}


POR_ID = {
    "a": noticia("a", "ge", 1),
    "b": dict(noticia("b", "BBC", 3), idioma="en"),
    "c": noticia("c", "ge", 2),
    "x": noticia("x", "Terra", 1),
}


def fato(ids, categoria="ATP"):
    return {"titulo": "Fonseca vence", "resumo": "João Fonseca venceu.", "categoria": categoria, "idsRobo": ids}


class TestMontarNoticia(unittest.TestCase):
    def test_montar_noticia_fontes_do_robo(self):
        doc_id, dados = montar_noticia(fato(["a", "b", "c"]), POR_ID, AGORA)
        self.assertEqual(doc_id, "n-a")
        self.assertEqual(dados["fontes"], [{"nome": "ge", "link": "https://ge.com/a", "idioma": "pt"},
                                           {"nome": "BBC", "link": "https://bbc.com/b", "idioma": "en"}])
        self.assertEqual(dados["publicadoEm"], iso(AGORA - timedelta(hours=3)))
        self.assertEqual(dados["criadoEm"], iso(AGORA))
        self.assertEqual(dados["idsRobo"], ["a", "b", "c"])
        self.assertEqual(dados["titulo"], "Fonseca vence")
        self.assertEqual(dados["resumo"], "João Fonseca venceu.")

    def test_montar_noticia_id_invalido(self):
        self.assertIsNone(montar_noticia(fato(["zzz"]), POR_ID, AGORA))

    def test_ignora_ids_desconhecidos(self):
        doc_id, dados = montar_noticia(fato(["zzz", "b"]), POR_ID, AGORA)
        self.assertEqual(doc_id, "n-b")
        self.assertEqual(dados["idsRobo"], ["b"])

    def test_categoria_invalida_vira_outros(self):
        _, dados = montar_noticia(fato(["a"], categoria="Futebol"), POR_ID, AGORA)
        self.assertEqual(dados["categoria"], "Outros")

    def test_sem_titulo_ou_resumo_descarta(self):
        self.assertIsNone(montar_noticia(dict(fato(["a"]), titulo="  "), POR_ID, AGORA))
        self.assertIsNone(montar_noticia(dict(fato(["a"]), resumo=""), POR_ID, AGORA))


class TestNovosTratados(unittest.TestCase):
    def test_novos_tratados(self):
        decisoes = {"fatos": [fato(["a"])], "descartados": ["b"]}
        resultado = novos_tratados(["x", "velho"], decisoes, {"x", "a", "b"})
        self.assertEqual(set(resultado), {"x", "a", "b"})


def escrever(caminho, conteudo):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(conteudo, arquivo, ensure_ascii=False)


def ler(caminho):
    with open(caminho, encoding="utf-8") as arquivo:
        return json.load(arquivo)


class TestMain(unittest.TestCase):
    def rodar(self, decisoes, tratados=None, extras=()):
        pasta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, pasta, True)
        escrever(os.path.join(pasta, "noticias.json"),
                 {"atualizadoEm": "2026-11-25T21:30:00Z", "fontesComFalha": ["Terra"], "noticias": list(POR_ID.values())})
        if tratados is not None:
            escrever(os.path.join(pasta, "db", "meta", "tratados.json"), tratados)
        escrever(os.path.join(pasta, "decisoes.json"), decisoes)
        saida = os.path.join(pasta, "lote")
        montar_lote.main(["--noticias", os.path.join(pasta, "noticias.json"), "--db", os.path.join(pasta, "db"),
                          "--decisoes", os.path.join(pasta, "decisoes.json"), "--saida", saida, *extras], agora=AGORA)
        return saida, ler(os.path.join(saida, "writes.json"))

    def test_main_gera_gravacoes(self):
        saida, writes = self.rodar({"fatos": [fato(["a", "b"]), fato(["zzz"])], "descartados": ["c"]})
        self.assertEqual([(w["op"], w["collection"], w["doc_id"]) for w in writes],
                         [("set", "noticias", "n-a"), ("set", "meta", "tratados"), ("set", "meta", "estado")])
        for w in writes:
            self.assertTrue(os.path.isabs(w["file_path"]))
            self.assertNotIn("if_version", w)
        self.assertEqual(set(ler(writes[1]["file_path"])["ids"]), {"a", "b", "c"})
        self.assertEqual(ler(writes[2]["file_path"]), {"atualizadoEm": iso(AGORA), "coletaEm": "2026-11-25T21:30:00Z",
                                                        "fontesComFalha": ["Terra"], "novasNaRodada": 1})

    def test_main_usa_versao_e_nao_republica_tratado(self):
        _, writes = self.rodar({"fatos": [fato(["x", "a"])], "descartados": []},
                               tratados={"ids": ["x"]},
                               extras=["--versao-tratados", "7", "--versao-estado", "3"])
        self.assertEqual(writes[0]["doc_id"], "n-a")
        self.assertEqual(writes[1]["if_version"], 7)
        self.assertEqual(writes[2]["if_version"], 3)

    def test_main_sem_fatos_so_atualiza_meta(self):
        _, writes = self.rodar({"fatos": [], "descartados": []})
        self.assertEqual([w["doc_id"] for w in writes], ["tratados", "estado"])


if __name__ == "__main__":
    unittest.main()
