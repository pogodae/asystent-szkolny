"""Wspólne narzędzia: wczytanie .env i klient Airtable Web API."""
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
API = "https://api.airtable.com/v0"


def load_env(path: Path = ENV_PATH) -> dict:
    """Wczytuje .env do os.environ (bez nadpisywania istniejących zmiennych)."""
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip().strip('"').strip("'")
    for k, v in values.items():
        os.environ.setdefault(k, v)
    return values


def set_env_value(key: str, value: str, path: Path = ENV_PATH) -> None:
    """Ustawia lub dopisuje zmienną w .env."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def require(*names: str) -> list:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        sys.exit(f"Brak w .env: {', '.join(missing)}")
    return [os.environ[n] for n in names]


class Airtable:
    def __init__(self, token: str, base_id: str):
        self.base_id = base_id
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})

    def _req(self, method: str, url: str, **kw):
        for attempt in range(5):
            r = self.s.request(method, url, timeout=30, **kw)
            if r.status_code == 429:  # limit 5 req/s na bazę
                time.sleep(30 if attempt else 1)
                continue
            if not r.ok:
                raise RuntimeError(f"{method} {url} -> {r.status_code}: {r.text}")
            return r.json() if r.text else {}
        raise RuntimeError(f"{method} {url}: przekroczony limit zapytań")

    # --- schemat ---
    def tables(self) -> list:
        return self._req("GET", f"{API}/meta/bases/{self.base_id}/tables")["tables"]

    def create_table(self, name: str, fields: list, description: str = "") -> dict:
        body = {"name": name, "fields": fields}
        if description:
            body["description"] = description
        return self._req("POST", f"{API}/meta/bases/{self.base_id}/tables", json=body)

    def create_field(self, table_id: str, field: dict) -> dict:
        return self._req("POST", f"{API}/meta/bases/{self.base_id}/tables/{table_id}/fields", json=field)

    def update_field(self, table_id: str, field_id: str, patch: dict) -> dict:
        return self._req("PATCH", f"{API}/meta/bases/{self.base_id}/tables/{table_id}/fields/{field_id}", json=patch)

    # --- rekordy ---
    def list_records(self, table: str, formula: str | None = None) -> list:
        out, params = [], {}
        if formula:
            params["filterByFormula"] = formula
        while True:
            data = self._req("GET", f"{API}/{self.base_id}/{requests.utils.quote(table)}", params=params)
            out += data["records"]
            if "offset" not in data:
                return out
            params["offset"] = data["offset"]

    def create_record(self, table: str, fields: dict) -> dict:
        return self._req("POST", f"{API}/{self.base_id}/{requests.utils.quote(table)}",
                         json={"fields": fields, "typecast": True})

    def update_record(self, table: str, rec_id: str, fields: dict) -> dict:
        return self._req("PATCH", f"{API}/{self.base_id}/{requests.utils.quote(table)}/{rec_id}",
                         json={"fields": fields, "typecast": True})

    def get_record(self, table: str, rec_id: str) -> dict:
        return self._req("GET", f"{API}/{self.base_id}/{requests.utils.quote(table)}/{rec_id}")

    def delete_record(self, table: str, rec_id: str) -> dict:
        return self._req("DELETE", f"{API}/{self.base_id}/{requests.utils.quote(table)}/{rec_id}")
