"""Dodaje (lub aktualizuje) dwóch rodziców z .env w tabeli Rodzice.

Gdy RODZICx_KLUCZ_DOSTEPU jest pusty, generuje losowy klucz i zapisuje go w .env.
Na końcu wypisuje osobiste linki do dashboardu (jeśli DASHBOARD_URL jest ustawiony).

Użycie:  python airtable/seed_rodzice.py
"""
import os
import secrets
import sys

from common import Airtable, load_env, require, set_env_value


def main():
    load_env()
    token, base = require("AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")
    at = Airtable(token, base)

    for i in (1, 2):
        imie, klucz, email = require(f"RODZIC{i}_IMIE", f"RODZIC{i}_KLUCZ", f"RODZIC{i}_EMAIL")
        dostep_var = f"RODZIC{i}_KLUCZ_DOSTEPU"
        dostep = os.environ.get(dostep_var) or ""
        if not dostep:
            dostep = secrets.token_urlsafe(24)
            set_env_value(dostep_var, dostep)
            print(f"  wygenerowano {dostep_var} i zapisano w .env")

        powiadomienia = os.environ.get(f"RODZIC{i}_POWIADOMIENIA") or "Wszystkie"
        fields = {"Imię": imie, "Klucz": klucz, "Email": email, "Aktywny": True, "Klucz dostępu": dostep,
                  "Powiadomienia": powiadomienia}
        found = at.list_records("Rodzice", f"{{Klucz}}='{klucz}'")
        if found:
            at.update_record("Rodzice", found[0]["id"], fields)
            print(f"= {imie} ({klucz}) zaktualizowano [{found[0]['id']}]")
        else:
            rec = at.create_record("Rodzice", fields)
            print(f"+ {imie} ({klucz}) dodano [{rec['id']}]")

        url = os.environ.get("DASHBOARD_URL")
        if url:
            print(f"  link do dashboardu: {url.rstrip('/')}/?u={klucz}&s=<{dostep_var} z .env>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
