"""Smoke test asystenta: automatyczne testy z sekcji „Plan testów” w SPEC.

Testy tworzą zadania z tytułem „SMOKE …” i na końcu je usuwają (razem ze zdarzeniami).
Uwaga: test 2 dodaje zadanie przez S1-W, więc oboje aktywni rodzice dostaną mail „Nowe”.
Ręcznie zostają: 1 („dodaj” w Claude), 6–7 (prawdziwe maile u obojga), 9–11 na prawdziwym
harmonogramie, 15 (telefon).

Użycie:  python tests/smoke_test.py
"""
import re
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
at = airtable()
wyniki = []


def check(nr, opis, warunek, szczegoly=""):
    wyniki.append(bool(warunek))
    print(f"{'OK ' if warunek else 'BŁĄD'} #{nr:<3} {opis}" + (f"  [{szczegoly}]" if szczegoly and not warunek else ""))


def h1(r):
    return " ".join(re.findall(r"<h1>(.*?)</h1>", r.text))


def dashboard(**kw):
    return requests.post(URL, params={"cel": "api"}, data={"u": U, "s": S, **kw}, timeout=60)


def nowe_zadanie(tytul):
    tok = str(uuid.uuid4())
    rec = at.create_record("Zadania", {"Tytuł": tytul, "Termin": "2030-01-01T07:30:00+01:00", "Status": "Nowe",
                                       "Token": tok, "Źródło": "Webhook", "Liczba przypomnień": 0})
    return rec["id"], tok


def main():
    sid = f"smoke-{uuid.uuid4().hex[:8]}"
    try:
        r = requests.post(URL, params={"cel": "dodaj"}, json={"tytul": "SMOKE bez klucza", "termin": "2030-01-01T08:00:00+01:00"})
        check(4, "S1-W bez X-Api-Key → 401", r.status_code == 401, r.status_code)

        r = requests.post(URL, params={"cel": "dodaj"}, headers={"X-Api-Key": KEY},
                          json={"tytul": "SMOKE przeszłość", "termin": "2020-01-01T08:00:00+01:00"})
        check(3, "termin w przeszłości → blad, brak rekordu",
              r.status_code == 400 and r.json()["status"] == "blad"
              and not at.list_records("Zadania", "{Tytuł}='SMOKE przeszłość'"), r.text)

        body = {"tytul": "SMOKE webhook", "termin": "2030-01-01T08:00:00+01:00", "id_zrodla": sid}
        r1 = requests.post(URL, params={"cel": "dodaj"}, headers={"X-Api-Key": KEY}, json=body)
        r2 = requests.post(URL, params={"cel": "dodaj"}, headers={"X-Api-Key": KEY}, json=body)
        check(2, "ten sam id_zrodla 2× → utworzono, potem duplikat",
              r1.json().get("status") == "utworzono" and r2.json().get("status") == "duplikat", f"{r1.text} {r2.text}")

        tid, tok = nowe_zadanie("SMOKE kliknięcia")
        r = requests.get(URL, params={"t": tid, "a": "take", "p": U, "k": tok})
        st = at.get_record("Zadania", tid)["fields"].get("Status")
        check(5, "GET „Biorę to” → potwierdzenie, rekord bez zmian", "Biorę to" in r.text and st == "Nowe", st)

        r = requests.get(URL, params={"t": tid, "a": "take", "p": U, "k": "zly-token-0000"})
        check(8, "zmieniony token → „Link nieważny”, 403", r.status_code == 403 and "Link nieważny" in r.text, r.status_code)

        r = requests.post(URL, data={"t": tid, "a": "take", "p": U, "k": tok, "ok": "1"})
        f = at.get_record("Zadania", tid)["fields"]
        check(6, "POST potwierdzenia → Przypisane", f.get("Status") == "Przypisane" and "Gotowe" in h1(r), h1(r))

        tid2, _ = nowe_zadanie("SMOKE dashboard")
        j = dashboard(akcja="lista").json()
        check(14.1, "dashboard: lista", j.get("ok") and any(z["id"] == tid2 for z in j["zadania"]))
        z = dashboard(akcja="take", id=tid2).json()["zadanie"]["fields"]
        check(12, "dashboard: „Biorę to” → moje", z.get("Status") == "Przypisane", z.get("Status"))
        at.update_record("Zadania", tid2, {"Liczba przypomnień": 3})
        z = dashboard(akcja="release", id=tid2).json()["zadanie"]["fields"]
        check(13, "dashboard: „Oddaj” → Wolne, licznik 0",
              z.get("Status") == "Nowe" and not z.get("Liczba przypomnień"), z)
        r = requests.post(URL, params={"cel": "api"}, data={"u": U, "s": "zly-klucz-0000000000", "akcja": "lista"})
        check(14, "dashboard ze złym kluczem → brak danych", r.status_code == 403 and "zadania" not in r.text, r.text)
    finally:
        time.sleep(2)
        for z in at.list_records("Zadania", "FIND('SMOKE', {Tytuł})"):
            for e in z["fields"].get("Zdarzenia", []):
                at.delete_record("Zdarzenia", e)
            at.delete_record("Zadania", z["id"])
    print(f"\n{sum(wyniki)}/{len(wyniki)} OK")
    return 0 if all(wyniki) else 1


if __name__ == "__main__":
    sys.exit(main())
