"""Wgrywa blueprinty z make/_deploy/ do Make przez API i eksportuje aktualny stan do make/.

Pierwsze uruchomienie tworzy scenariusz i zapisuje jego ID w .env (MAKE_ID_<NAZWA>),
kolejne aktualizują blueprint w miejscu. Po zapisie blueprint jest pobierany z Make
i zapisywany do make/<nazwa>.json (z sekretami zastąpionymi znacznikami).

Użycie:  python make/deploy.py <nazwa> [--activate]
"""
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "airtable"))
sys.path.insert(0, str(ROOT / "make"))
from common import load_env, require, set_env_value  # noqa: E402
import build  # noqa: E402

# harmonogram i interfejs (wejścia/wyjścia) dla każdego scenariusza
SCHEDULING = {
    "silnik": {"type": "on-demand"},
    "api": {"type": "immediately"},
}
INTERFACES = {
    "silnik": build.SILNIK_INTERFACE,
}


class Make:
    def __init__(self, token, zone):
        self.base = f"https://{zone}/api/v2"
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Token {token}", "Content-Type": "application/json"})

    def _req(self, method, path, **kw):
        r = self.s.request(method, self.base + path, timeout=60, **kw)
        if not r.ok:
            raise RuntimeError(f"{method} {path} -> {r.status_code}: {r.text[:800]}")
        return r.json() if r.text else {}

    def create(self, team_id, blueprint, scheduling):
        return self._req("POST", "/scenarios", params={"confirmed": "true"}, json={
            "teamId": int(team_id), "blueprint": json.dumps(blueprint, ensure_ascii=False),
            "scheduling": json.dumps(scheduling)})["scenario"]

    def update(self, sid, blueprint, scheduling):
        return self._req("PATCH", f"/scenarios/{sid}", params={"confirmed": "true"}, json={
            "blueprint": json.dumps(blueprint, ensure_ascii=False), "scheduling": json.dumps(scheduling)})["scenario"]

    def set_interface(self, sid, interface):
        return self._req("PATCH", f"/scenarios/{sid}/interface", json={"interface": interface})

    def blueprint(self, sid):
        return self._req("GET", f"/scenarios/{sid}/blueprint")["response"]["blueprint"]

    def activate(self, sid):
        return self._req("POST", f"/scenarios/{sid}/start")


def main(argv):
    load_env()
    token, zone, team = require("MAKE_API_TOKEN", "MAKE_ZONE", "MAKE_TEAM_ID")
    mk = Make(token, zone)
    activate = "--activate" in argv
    names = [a for a in argv if not a.startswith("--")]
    for name in names:
        build.main([name])
        bp = json.loads((build.DEPLOY / f"{name}.json").read_text(encoding="utf-8"))
        id_var = f"MAKE_ID_{name.upper()}"
        sid = os.environ.get(id_var)
        sched = SCHEDULING[name]
        if sid:
            mk.update(sid, bp, sched)
            print(f"= {name}: zaktualizowano scenariusz {sid}")
        else:
            sid = str(mk.create(team, bp, sched)["id"])
            set_env_value(id_var, sid)
            print(f"+ {name}: utworzono scenariusz {sid} ({id_var} w .env)")
        if name in INTERFACES:
            mk.set_interface(sid, INTERFACES[name])
            print("  interfejs wejść/wyjść ustawiony")
        if activate:
            mk.activate(sid)
            print("  aktywowano")
        # eksport stanu z Make do repo
        exported = json.dumps(mk.blueprint(sid), ensure_ascii=False, indent=1)
        (build.MAKE / f"{name}.json").write_text(build.redact(exported), encoding="utf-8")
        print(f"  eksport: make/{name}.json")


if __name__ == "__main__":
    main(sys.argv[1:])
