import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import inicio  # noqa: E402
from inicio import horarios  # noqa: E402

AGORA = datetime(2026, 11, 26, 0, 40, 21, tzinfo=timezone.utc)


class TestHorarios(unittest.TestCase):
    def test_horarios(self):
        self.assertEqual(horarios(AGORA), {"H24": "2026-11-25T00:40:21Z", "D7": "2026-11-19T00:40:21Z"})


class TestPreparaPasta(unittest.TestCase):
    def test_limpa_pasta_de_trabalho(self):
        with tempfile.TemporaryDirectory() as raiz:
            trabalho = os.path.join(raiz, "tarefa", "trabalho")
            os.makedirs(os.path.join(trabalho, "db"))
            open(os.path.join(trabalho, "velho.json"), "w").close()
            with mock.patch.object(inicio, "atualizar_repositorio", lambda raiz: True):
                resultado = inicio.main(raiz=raiz, agora=AGORA)
            self.assertEqual(os.listdir(trabalho), [])
        self.assertEqual(resultado["NOTICIAS"], os.path.join(raiz, "noticias.json"))

    def test_usa_copia_baixada_se_pull_falhar(self):
        with tempfile.TemporaryDirectory() as raiz:
            with mock.patch.object(inicio, "atualizar_repositorio", lambda raiz: False), \
                 mock.patch.object(inicio, "baixar_copia", lambda destino: True):
                resultado = inicio.main(raiz=raiz, agora=AGORA)
        self.assertEqual(resultado["NOTICIAS"], os.path.join(raiz, "tarefa", "trabalho", "noticias.json"))

    def test_sem_acesso(self):
        with tempfile.TemporaryDirectory() as raiz:
            with mock.patch.object(inicio, "atualizar_repositorio", lambda raiz: False), \
                 mock.patch.object(inicio, "baixar_copia", lambda destino: False):
                resultado = inicio.main(raiz=raiz, agora=AGORA)
        self.assertIsNone(resultado["NOTICIAS"])


if __name__ == "__main__":
    unittest.main()
