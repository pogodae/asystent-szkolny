"""Smoke test asystenta na żywo: wywołuje prawdziwy webhook API w Make i sprawdza stan w Airtable.

Wymaga aktywnych scenariuszy w Make i uzupełnionego .env. Testy tworzą sprawy z tytułem „SMOKE …”
i na końcu je usuwają. Maili nie wysyłają: przekazanie sprawy idzie do tej samej osoby (bez maila),
a przypomnienia wychodzą tylko rano dzień przed terminem.
Koszt: około 25 operacji Make – darmowy plan ma ~1000 miesięcznie, więc uruchamiaj z rozwagą.
Testy offline (bez Make): python -m unittest discover -s tests -t .

Użycie:  python tests/smoke_test.py
"""
import sys
import time
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_api import airtable, os  # noqa: E402

URL = os.environ["S2_WEBHOOK_URL"]
KEY = os.environ["S1W_API_KEY"]
U, S = os.environ["RODZIC1_KLUCZ"], os.environ["RODZIC1_KLUCZ_DOSTEPU"]
TERMIN = "2030-01-01T08:00:00+01:00"
at = airtable()
wyniki = []


def check(opis, warunek, szczegoly=""):
    wyniki.append(bool(warunek))
    print(f"{'OK  ' if warunek else 'BŁĄD'} {opis}" + (f"  [{szczegoly}]" if szczegoly and not warunek else ""))


def s1w(body, klucz=KEY):
    headers = {"X-Api-Key": klucz} if klucz else {}
    return requests.post(URL, params={"cel": "dodaj"}, headers=headers, json=body, timeout=60)


def dashboard(s=S, **kw):
    return requests.post(URL, params={"cel": "api"}, data={"u": U, "s": s, **kw}, timeout=60)


def status(rec_id):
    return at.get_record("Zadania", rec_id)["fields"].get("Status")


def main():
    sid = f"smoke-{uuid.uuid4().hex[:8]}"
    try:
        # --- S1-W: webhook dla zewnętrznych źródeł (np. scraper MobiDziennika)
        r = s1w({"tytul": "SMOKE bez klucza", "termin": TERMIN}, klucz=None)
        check("S1-W bez X-Api-Key → 401", r.status_code == 401, r.status_code)

        r = s1w({"tytul": "SMOKE przeszłość", "termin": "2020-01-01T08:00:00+01:00"})
        check("S1-W: termin w przeszłości → 400, brak rekordu",
              r.status_code == 400 and not at.list_records("Zadania", "{Tytuł}='SMOKE przeszłość'"), r.text)

        r = s1w({"tytul": "SMOKE wstrzyknięcie", "termin": TERMIN, "id_zrodla": "x' OR TRUE() OR '"})
        check("S1-W: id_zrodla z apostrofem → 400 (ochrona formuły Airtable)", r.status_code == 400, r.text)

        r = s1w({"tytul": "SMOKE kategoria", "termin": TERMIN, "kategoria": "Nieznana"})
        check("S1-W: nieznana kategoria → 400", r.status_code == 400, r.text)

        body = {"tytul": "SMOKE webhook", "termin": TERMIN, "id_zrodla": sid, "rodzaj": "Do dnia"}
        r1, r2 = s1w(body), s1w(body)
        check("S1-W: ten sam id_zrodla 2× → utworzono, potem duplikat",
              r1.json().get("status") == "utworzono" and r2.json().get("status") == "duplikat", f"{r1.text} {r2.text}")

        # --- dashboard
        r = dashboard(s="zly-klucz-0000000000", akcja="lista")
        check("dashboard ze złym kluczem → 403 bez danych", r.status_code == 403 and "zadania" not in r.text, r.text)

        r = dashboard(akcja="dodaj", tytul="SMOKE dashboard", termin=TERMIN, rodzaj="W dniu",
                      id_zrodla=f"dash-{uuid.uuid4()}")
        tid = r.json().get("id", "")
        check("dashboard: dodaj → rekord „Przypisane”", r.ok and tid and status(tid) == "Przypisane", r.text)

        j = dashboard(akcja="lista").json()
        check("dashboard: lista zawiera nową sprawę i konfigurację",
              j.get("ok") and any(z["id"] == tid for z in j["zadania"]) and j.get("rodzice") and j.get("kategorie"))

        dashboard(akcja="przypisz", id=tid, dla=U)  # do siebie – bez maila
        check("dashboard: przypisz → nadal „Przypisane”", status(tid) == "Przypisane")

        dashboard(akcja="done", id=tid)
        check("dashboard: zrobione → „Zrobione”", status(tid) == "Zrobione")

        r = dashboard(akcja="nieznana", id=tid)
        check("dashboard: nieznana akcja → 400", r.status_code == 400, r.text)

        tid2 = dashboard(akcja="dodaj", tytul="SMOKE kosz", termin=TERMIN, rodzaj="W dniu",
                         id_zrodla=f"dash-{uuid.uuid4()}").json().get("id", "")
        dashboard(akcja="usun", id=tid2)
        check("dashboard: usuń → „Anulowane” (rekord zostaje)", status(tid2) == "Anulowane")

        # --- stare linki z maili
        r = requests.get(URL, params={"t": "rec00000000000000", "a": "take"}, timeout=60)
        check("stary link z maila → strona z odnośnikiem do listy", r.status_code == 200 and "Sprawy są na liście" in r.text,
              r.status_code)
    finally:
        time.sleep(2)
        for z in at.list_records("Zadania", "FIND('SMOKE', {Tytuł})"):
            at.delete_record("Zadania", z["id"])
    print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
    return 0 if all(wyniki) else 1


if __name__ == "__main__":
    sys.exit(main())
