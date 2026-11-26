import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "divulgacao"))

try:
    import PIL  # noqa: F401
    import imageio_ffmpeg  # noqa: F401
    TEM_FERRAMENTAS = True
except ImportError:  # o robô do GitHub não tem Pillow: o kit é gerado no PC
    TEM_FERRAMENTAS = False

RANKING = {"atualizadoEm": "2026-11-19T08:00:00Z",
           "jogadores": [{"posicao": i, "nome": f"Jogador {i}", "pontos": 9000 - i} for i in range(1, 6)]}


@unittest.skipUnless(TEM_FERRAMENTAS, "Pillow ou imageio-ffmpeg não instalados")
class TestKitYoutube(unittest.TestCase):
    def setUp(self):
        import gerar_youtube
        self.g = gerar_youtube
        self.pasta = tempfile.mkdtemp()

    def test_foto_de_perfil(self):
        from PIL import Image
        caminho = os.path.join(self.pasta, "perfil.png")
        self.g.gerar_perfil(caminho)
        with Image.open(caminho) as imagem:
            self.assertEqual(imagem.size, (800, 800))

    def test_capa_do_canal(self):
        from PIL import Image
        caminho = os.path.join(self.pasta, "capa.png")
        self.g.gerar_capa(caminho)
        with Image.open(caminho) as imagem:
            self.assertEqual(imagem.size, (2560, 1440))
        self.assertLess(os.path.getsize(caminho), 6_000_000)

    def test_top3(self):
        self.assertEqual(self.g.top3(RANKING), [(1, "Jogador 1", "8.999"), (2, "Jogador 2", "8.998"),
                                                (3, "Jogador 3", "8.997")])

    def test_video_em_pe(self):
        import imageio_ffmpeg
        caminho = os.path.join(self.pasta, "short.mp4")
        self.g.gerar_video(caminho, RANKING, RANKING, fps=4)
        leitor = imageio_ffmpeg.read_frames(caminho)
        meta = next(leitor)
        leitor.close()
        self.assertEqual(tuple(meta["size"]), (1080, 1920))
        self.assertGreater(meta["duration"], 15)
        self.assertLess(meta["duration"], 60)


if __name__ == "__main__":
    unittest.main()
