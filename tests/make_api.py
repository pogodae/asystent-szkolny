"""Pomocnicze wywołania Make API dla testów: uruchomienie scenariusza i odczyt wyjść."""
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "airtable"))
from common import Airtable, load_env, require  # noqa: E402

load_env()


def make():
    s = requests.Session()
    s.headers["Authorization"] = "Token " + os.environ["MAKE_API_TOKEN"]
    return s, f"https://{os.environ['MAKE_ZONE']}/api/v2"


def run_scenario(sid, data):
    """Uruchamia scenariusz na żądanie i zwraca jego wyjścia (lub błąd)."""
    s, base = make()
    r = s.post(f"{base}/scenarios/{sid}/run", json={"data": data, "responsive": True}, timeout=120)
    body = r.json()
    if not r.ok:
        raise RuntimeError(f"run {sid}: {r.status_code} {body}")
    return body


def airtable():
    return Airtable(*require("AIRTABLE_TOKEN", "AIRTABLE_BASE_ID"))


def rodzic(at, klucz):
    return at.list_records("Rodzice", f"{{Klucz}}='{klucz}'")[0]
