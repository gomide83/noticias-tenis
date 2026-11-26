import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "coletor"))

from feeds import interpretar_feed, limpar_texto, para_iso  # noqa: E402

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>X</title>
<item>
  <title><![CDATA[Fonseca vence &amp; avança]]></title>
  <link>https://a.com/1</link>
  <pubDate>Wed, 25 Nov 2026 20:11:09 -0000</pubDate>
  <description><![CDATA[<p>João <b>venceu</b></p>]]></description>
</item>
<item>
  <title>Sem data</title>
  <link>https://a.com/2</link>
</item>
</channel></rss>""".encode("utf-8")

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Sinner wins</title>
    <link href="https://b.com/x"/>
    <updated>2026-11-25T10:00:00Z</updated>
    <summary>Text</summary>
  </entry>
</feed>"""

GOOGLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Google</title>
<item>
  <title>Alcaraz lamenta - ge</title>
  <link>https://news.google.com/rss/articles/abc</link>
  <pubDate>Wed, 25 Nov 2026 16:31:10 GMT</pubDate>
  <source url="https://ge.globo.com">ge</source>
</item>
</channel></rss>"""

FONTE_PT = {"id": "a", "nome": "Portal A", "url": "https://a.com/feed", "idioma": "pt"}
FONTE_EN = {"id": "b", "nome": "Portal B", "url": "https://b.com/feed", "idioma": "en"}
FONTE_GOOGLE = {"id": "g", "nome": "Google", "url": "https://news.google.com/rss", "idioma": "pt", "google": True}


class TestInterpretarFeed(unittest.TestCase):
    def test_rss_basico(self):
        itens = interpretar_feed(RSS, FONTE_PT)
        self.assertEqual(len(itens), 2)
        item = itens[0]
        self.assertEqual(item["titulo"], "Fonseca vence & avança")
        self.assertEqual(item["link"], "https://a.com/1")
        self.assertEqual(item["fonte"], "Portal A")
        self.assertEqual(item["via"], "")
        self.assertEqual(item["idioma"], "pt")
        self.assertEqual(item["publicadoEm"], "2026-11-25T20:11:09Z")
        self.assertEqual(item["trecho"], "João venceu")

    def test_rss_sem_data(self):
        item = interpretar_feed(RSS, FONTE_PT)[1]
        self.assertIsNone(item["publicadoEm"])
        self.assertEqual(item["trecho"], "")

    def test_atom(self):
        itens = interpretar_feed(ATOM, FONTE_EN)
        self.assertEqual(len(itens), 1)
        item = itens[0]
        self.assertEqual(item["titulo"], "Sinner wins")
        self.assertEqual(item["link"], "https://b.com/x")
        self.assertEqual(item["publicadoEm"], "2026-11-25T10:00:00Z")
        self.assertEqual(item["idioma"], "en")
        self.assertEqual(item["trecho"], "Text")

    def test_google_tira_sufixo(self):
        item = interpretar_feed(GOOGLE, FONTE_GOOGLE)[0]
        self.assertEqual(item["titulo"], "Alcaraz lamenta")
        self.assertEqual(item["fonte"], "ge")
        self.assertEqual(item["via"], "Google Notícias")
        self.assertEqual(item["publicadoEm"], "2026-11-25T16:31:10Z")

    def test_xml_invalido(self):
        with self.assertRaises(ValueError):
            interpretar_feed(b"<html>oops", FONTE_PT)

    def test_trecho_cortado_em_500(self):
        longo = ("<rss><channel><item><title>T</title><link>https://a.com/3</link>"
                 "<description>" + "x" * 900 + "</description></item></channel></rss>").encode()
        self.assertEqual(len(interpretar_feed(longo, FONTE_PT)[0]["trecho"]), 500)


class TestAuxiliares(unittest.TestCase):
    def test_para_iso_formatos(self):
        self.assertEqual(para_iso("2026-11-26T00:22:58+01:00"), "2026-11-25T23:22:58Z")
        self.assertEqual(para_iso("Wed, 25 Nov 2026 23:00:00 +0000"), "2026-11-25T23:00:00Z")
        self.assertEqual(para_iso("2026-11-25T10:00:00Z"), "2026-11-25T10:00:00Z")
        self.assertIsNone(para_iso("lixo"))
        self.assertIsNone(para_iso(None))
        self.assertIsNone(para_iso(""))

    def test_para_iso_ano_absurdo(self):
        self.assertIsNone(para_iso("0001-01-01T00:30:00+01:00"))
        self.assertIsNone(para_iso("Mon, 01 Jan 1990 00:00:00 +0000"))

    def test_limpar_texto(self):
        self.assertEqual(limpar_texto("<p>A&nbsp;&amp;  B</p>"), "A & B")
        self.assertEqual(limpar_texto(None), "")


if __name__ == "__main__":
    unittest.main()
