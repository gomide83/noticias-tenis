import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tarefa"))

import gerar_previa  # noqa: E402

try:
    import PIL  # noqa: F401
    TEM_PILLOW = True
except ImportError:  # o robô do GitHub não tem Pillow; a imagem é gerada no PC
    TEM_PILLOW = False


@unittest.skipUnless(TEM_PILLOW, "Pillow não instalado")
class TestPrevia(unittest.TestCase):
    def test_gera_png_no_tamanho_das_redes(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "previa.png")
            gerar_previa.gerar(caminho)
            with Image.open(caminho) as imagem:
                self.assertEqual(imagem.format, "PNG")
                self.assertEqual(imagem.size, (1200, 630))
            self.assertLess(os.path.getsize(caminho), 1_000_000)


if __name__ == "__main__":
    unittest.main()
