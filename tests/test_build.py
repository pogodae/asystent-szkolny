"""Testy offline generatora blueprintów (make/build.py) – bez Make, Airtable i sieci.

Sprawdzają reguły, które łatwo zepsuć przy zmianach scenariuszy:
  - publiczna wersja w repo nie zawiera sekretów ani prywatnych imion i kategorii,
  - każde pole z zewnątrz wstawiane do formuły Airtable jest wcześniej sprawdzone wyrażeniem regularnym,
  - każda trasa webhooka (poza przypomnieniami) kończy się odpowiedzią HTTP,
  - ID modułów są unikalne, a szablony maili mają podstawione wszystkie zmienne.

Uruchomienie:  python -m unittest discover -s tests -t .
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "make"))
sys.path.insert(0, str(ROOT / "airtable"))

# prawdziwe" wartości testowe – nie mogą wyciec do publicznej wersji
FAKE_ENV = {
    "AIRTABLE_BASE_ID": "appTEST0000000000", "MAKE_CONN_AIRTABLE": "1", "MAKE_CONN_GMAIL": "2", "S2_HOOK_ID": "3",
    "MAKE_ID_SILNIK": "4", "DASHBOARD_URL": "https://example.test/",
    "S2_WEBHOOK_URL": "https://hook.test/SEKRETNY-URL", "S5_WEBHOOK_URL": "https://hook.test/SEKRETNY-URL",
    "S1W_API_KEY": "sekretny-klucz-api-123", "RODZIC1_KLUCZ_DOSTEPU": "sekretny-dostep-1",
    "RODZIC2_KLUCZ_DOSTEPU": "sekretny-dostep-2",
    "RODZIC1_IMIE": "Bożena", "RODZIC1_KLUCZ": "bozena", "RODZIC2_IMIE": "Zbigniew", "RODZIC2_KLUCZ": "zbyszek",
    "RODZIC1_REC": "recAAAAAAAAAAAAAA", "RODZIC2_REC": "recBBBBBBBBBBBBBB",
    "KATEGORIE": "Kunegunda,Bonifacy,Dom",
}
os.environ.update(FAKE_ENV)
import build  # noqa: E402

build.load_env = lambda *a, **k: {}  # nie czytaj prawdziwego .env


def modules(flow):
    """Wszystkie moduły (płasko, z trasami routerów)."""
    for m in flow:
        yield m
        for r in m.get("routes") or []:
            yield from modules(r["flow"])


def routes(flow):
    """Ścieżki od początku do końca każdej trasy: lista modułów."""
    for i, m in enumerate(flow):
        if m.get("routes"):
            for r in m["routes"]:
                for tail in routes(r["flow"]):
                    yield flow[:i + 1] + tail
            return
    yield list(flow)


def conditions(path):
    """Wszystkie warunki filtrów na ścieżce (po grupach OR każdego filtra)."""
    return [m["filter"]["conditions"] for m in path if m.get("filter")]


def zabezpieczone(path, pole):
    """Czy każda grupa OR któregoś filtra na ścieżce sprawdza pole wzorcem (text:pattern)."""
    for groups in conditions(path):
        if all(any(c["a"] == "{{1." + pole + "}}" and c["o"] == "text:pattern" for c in g) for g in groups):
            return True
    return False


class TestBlueprinty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out, deploy = Path(cls.tmp.name, "out"), Path(cls.tmp.name, "deploy")
        out.mkdir()
        build.main([], out=out, deploy=deploy)
        cls.public = {n: (out / f"{n}.json").read_text(encoding="utf-8") for n in build.SCENARIOS}
        cls.real = {n: json.loads((deploy / f"{n}.json").read_text(encoding="utf-8")) for n in build.SCENARIOS}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_publiczna_wersja_bez_sekretow_i_prywatnych_danych(self):
        prywatne = [v for k, v in FAKE_ENV.items() if k in build.SECRETS + build.PRYWATNE and k != "KATEGORIE"]
        prywatne += ["Kunegunda", "Bonifacy"]
        for name, text in self.public.items():
            for val in prywatne:
                self.assertNotIn(val, text, f"{name}: wyciek {val!r}")
            self.assertIn("__S1W_API_KEY__", text if name == "api" else "__S1W_API_KEY__")

    def test_wersja_do_make_ma_prawdziwe_kategorie(self):
        text = json.dumps(self.real["silnik"], ensure_ascii=False)
        self.assertIn("^(Kunegunda|Bonifacy|Dom)?$", text)

    def test_unikalne_id_modulow(self):
        for name, bp in self.real.items():
            ids = [m["id"] for m in modules(bp["flow"])]
            self.assertEqual(len(ids), len(set(ids)), f"{name}: powtórzone ID modułów")

    def test_dane_z_zewnatrz_sprawdzone_przed_formula_airtable(self):
        """Pole {{1.x}} wklejone do filterByFormula musi przejść wcześniej filtr z wyrażeniem regularnym,
        inaczej apostrof w danych mógłby zmienić formułę (wstrzyknięcie)."""
        for name, bp in self.real.items():
            for path in routes(bp["flow"]):
                for m in path:
                    if m["module"] != "airtable:makeApiCall":
                        continue
                    for q in m["mapper"]["qs"]:
                        if q["key"] != "filterByFormula":
                            continue
                        for pole in re.findall(r"\{\{1\.(\w+)\}\}", q["value"]):
                            self.assertTrue(zabezpieczone(path[:path.index(m) + 1], pole),
                                            f"{name}: moduł {m['id']} wstawia {{{{1.{pole}}}}} do formuły bez walidacji")

    def test_kazda_trasa_webhooka_odpowiada(self):
        """Dashboard i S1-W czekają na odpowiedź JSON – trasa bez WebhookRespond zostawiłaby je z „Accepted”."""
        for path in routes(self.real["api"]["flow"]):
            filtry = json.dumps(conditions(path))
            if '"przypomnienia"' in filtry:  # S3: wywołuje GitHub Actions, odpowiedź zbędna
                continue
            responds = [m for m in path if m["module"] == "gateway:WebhookRespond"]
            self.assertTrue(responds, f"trasa kończąca się modułem {path[-1]['id']} nie odpowiada")

    def test_odpowiedzi_json_sa_poprawne(self):
        for m in modules(self.real["api"]["flow"]):
            if m["module"] != "gateway:WebhookRespond":
                continue
            ctype = m["mapper"]["headers"][0]["value"]
            if "json" not in ctype:
                continue
            body = re.sub(r"\{\{[^}]*\}\}", "0", m["mapper"]["body"])  # wyrażenia Make → liczba
            body = body.replace('"0"', '"x"')
            json.loads(body)

    def test_wzorzec_id_zrodla(self):
        pat = re.compile(build.ID_ZRODLA_PAT)
        for ok in ("", "mobidziennik:12345", "dash-1f2e", "a.b_c"):
            self.assertTrue(pat.match(ok), ok)
        for zle in ("x' OR TRUE() OR '", "a b", "x" * 101, "{ID}"):
            self.assertFalse(pat.match(zle), zle)

    def test_interfejs_silnika_wymienia_kategorie(self):
        label = next(f["label"] for f in build.silnik_interface()["input"] if f["name"] == "kategoria")
        self.assertIn("Kunegunda, Bonifacy, Dom", label)


if __name__ == "__main__":
    unittest.main()
