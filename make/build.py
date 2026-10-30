"""Generator blueprintów Make dla asystenta szkolnego.

Scenariusze są opisane tutaj w Pythonie, a skrypt zapisuje dwie wersje każdego blueprintu:
  make/<nazwa>.json          – do repo: sekrety (URL-e webhooków, klucz API) zastąpione znacznikami __NAZWA__
  make/_deploy/<nazwa>.json  – do wgrania do Make (gitignored), z prawdziwymi wartościami z .env

Pola Airtable są adresowane po ID (make/schema_ids.json), bo nazwy z polskimi znakami
i spacjami są niewygodne w ścieżkach Make, a ID nie zmieniają się przy zmianie nazwy pola.

Użycie:  python make/build.py [nazwa ...]
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "airtable"))
from common import load_env  # noqa: E402

MAKE = ROOT / "make"
DEPLOY = MAKE / "_deploy"
TEMPLATES = ROOT / "templates"
SCHEMA = json.loads((MAKE / "schema_ids.json").read_text(encoding="utf-8"))

# wartości wstawiane tylko do wersji _deploy
SECRETS = ("S2_WEBHOOK_URL", "S5_WEBHOOK_URL", "S1W_API_KEY")


def env(name, default=""):
    return os.environ.get(name, default)


def F(table, field):
    """ID pola Airtable."""
    return SCHEMA[table]["fields"][field]


def T(table):
    return SCHEMA[table]["id"]


# ---------------------------------------------------------------- moduły

def mod(mid, module, version, parameters=None, mapper=None, flt=None, onerror=None, routes=None):
    m = {"id": mid, "module": module, "version": version,
         "parameters": parameters or {}, "mapper": mapper or {}, "metadata": {"designer": {"x": 0, "y": 0}}}
    if flt:
        m["filter"] = flt
    if onerror:
        m["onerror"] = onerror
    if routes is not None:
        m["routes"] = [{"flow": r} for r in routes]
        m["mapper"] = None
    return m


def conn_at():
    return {"__IMTCONN__": int(env("MAKE_CONN_AIRTABLE"))}


def conn_gmail():
    return {"__IMTCONN__": int(env("MAKE_CONN_GMAIL"))}


def api(mid, method, path, qs=None, body=None, flt=None):
    """Airtable – Make an API call. path względem https://api.airtable.com/."""
    m = {"url": path, "method": method, "headers": [],
         "qs": [{"key": k, "value": v} for k, v in (qs or {}).items()]}
    if body is not None:
        m["headers"] = [{"key": "Content-Type", "value": "application/json"}]
        m["body"] = body
    return mod(mid, "airtable:makeApiCall", 3, conn_at(), m, flt)


def at_get(mid, table, rec_expr, flt=None):
    return api(mid, "GET", f"v0/{env('AIRTABLE_BASE_ID')}/{T(table)}/{rec_expr}",
               {"returnFieldsByFieldId": "true"}, flt=flt)


def at_find(mid, table, formula, flt=None, extra_qs=None):
    qs = {"filterByFormula": formula, "returnFieldsByFieldId": "true"}
    qs.update(extra_qs or {})
    return api(mid, "GET", f"v0/{env('AIRTABLE_BASE_ID')}/{T(table)}", qs, flt=flt)


def at_create(mid, table, record, flt=None):
    return mod(mid, "airtable:ActionCreateRecord", 3, conn_at(),
               {"base": env("AIRTABLE_BASE_ID"), "table": T(table), "typecast": False,
                "useColumnId": False, "record": record}, flt)


def at_update(mid, table, rec_expr, record, flt=None):
    return mod(mid, "airtable:ActionUpdateRecords", 3, conn_at(),
               {"base": env("AIRTABLE_BASE_ID"), "table": T(table), "id": rec_expr, "typecast": False,
                "useColumnId": False, "record": record}, flt)


def zdarzenie(mid, typ, opis, zadanie_expr=None, kto_expr=None, flt=None):
    rec = {F("Zdarzenia", "Opis"): opis, F("Zdarzenia", "Typ"): typ}
    if zadanie_expr:
        rec[F("Zdarzenia", "Zadanie")] = [zadanie_expr]
    if kto_expr:
        rec[F("Zdarzenia", "Kto")] = [kto_expr]
    return at_create(mid, "Zdarzenia", rec, flt)


def gmail(mid, to_expr, subject, html, flt=None):
    return mod(mid, "google-email:sendAnEmail", 4, conn_gmail(),
               {"to": [to_expr], "subject": subject, "bodyType": "rawHtml", "content": html}, flt)


def respond(mid, status, body, ctype="text/html; charset=utf-8", extra_headers=None, flt=None):
    headers = [{"key": "Content-Type", "value": ctype}] + (extra_headers or [])
    return mod(mid, "gateway:WebhookRespond", 1, {}, {"status": status, "body": body, "headers": headers}, flt)


def webhook(mid, hook_env):
    return mod(mid, "gateway:CustomWebHook", 1, {"hook": int(env(hook_env)), "maxResults": 1})


def start(mid):
    return mod(mid, "scenario-service:StartSubscenario", 2)


def ret(mid, outputs, flt=None):
    return mod(mid, "scenario-service:ReturnData", 2, {}, {"data": outputs}, flt)


def call(mid, scenario_env, inputs, flt=None):
    return mod(mid, "scenario-service:CallSubscenario", 2,
               {"scenario": "SCN_" + env(scenario_env), "shouldWaitForExecutionEnd": True}, {"data": inputs}, flt)


def router(mid, *routes):
    return mod(mid, "builtin:BasicRouter", 1, routes=list(routes))


def feeder(mid, array_expr, flt=None):
    """Iterator po tablicy."""
    return mod(mid, "builtin:BasicFeeder", 1, {}, {"array": array_expr}, flt)


def tojson(mid, obj_expr):
    return mod(mid, "json:TransformToJSON", 1, {}, {"object": obj_expr})


# ---------------------------------------------------------------- filtry

def flt(name, *groups):
    """groups: OR z grup, każda grupa to lista warunków AND."""
    return {"name": name, "conditions": [list(g) for g in groups]}


def eq(a, b):
    return {"a": a, "o": "text:equal", "b": b}


def ne(a, b):
    return {"a": a, "o": "text:notequal", "b": b}


def exists(a):
    return {"a": a, "o": "exist"}


def missing(a):
    return {"a": a, "o": "notexist"}


def match(a, pattern):
    return {"a": a, "o": "text:pattern", "b": pattern}


def nomatch(a, pattern):
    return {"a": a, "o": "text:notpattern", "b": pattern}


# ---------------------------------------------------------------- szablony

def template(name, **vars_):
    """Wczytuje szablon HTML i podstawia {{nazwa}} wyrażeniami Make."""
    html = (TEMPLATES / name).read_text(encoding="utf-8")
    if html.startswith("<!--"):
        html = html.split("-->", 1)[1].lstrip()
    vars_.setdefault("DASHBOARD_URL", env("DASHBOARD_URL"))
    for k, v in vars_.items():
        html = html.replace("{{" + k + "}}", str(v))
    left = [p for p in ("{{tytul}}", "{{opis}}", "{{link_take}}", "{{link_done}}", "{{stopka_kto}}") if p in html]
    if left:
        raise ValueError(f"{name}: niepodstawione {left}")
    return html


def link(base_url, rec, akcja, klucz, token):
    return f"{base_url}?t={rec}&amp;a={akcja}&amp;p={klucz}&amp;k={token}"


class Zadanie:
    """Wyrażenia Make dla zadania pobranego przez at_get (fields po ID)."""

    def __init__(self, mid, prefix="body.fields"):
        self.mid, self.p = mid, prefix

    def __getitem__(self, field):
        return "{{" + f"{self.mid}.{self.p}.{F('Zadania', field)}" + "}}"

    @property
    def id(self):
        return "{{" + f"{self.mid}.body.id" + "}}"

    @property
    def osoba(self):
        return "{{" + f"{self.mid}.{self.p}.{F('Zadania', 'Osoba')}[1]" + "}}"

    def mail_vars(self):
        return dict(tytul=self["Tytuł"], termin_dlugi=self["Termin tekst"], termin_krotko=self["Termin krótko"],
                    opis=self["Opis"],
                    kwota_html=f'<p style="margin:0 0 8px;font-size:16px;">{self["Kwota linia"]}</p>')


class Rodzic:
    """Wyrażenia Make dla rodzica: pierwszy rekord z listy (at_find) albo pojedynczy rekord (at_get)."""

    def __init__(self, mid, single=False):
        self.base = f"{mid}.body" if single else f"{mid}.body.records[1]"

    def __getitem__(self, field):
        return "{{" + f"{self.base}.fields.{F('Rodzice', field)}" + "}}"

    @property
    def id(self):
        return "{{" + f"{self.base}.id" + "}}"


# ---------------------------------------------------------------- scenariusze

def metadata(sequential=False, interface=None):
    md = {"version": 1, "scenario": {
        "roundtrips": 1, "maxErrors": 3, "autoCommit": True, "autoCommitTriggerLast": True,
        "sequential": sequential, "confidential": False, "dataloss": False, "dlq": True,
        "freshVariables": False}, "designer": {"orphans": []}}
    return md


STATUS_AKCJE = ("take", "done", "release", "przejmij")


def status_routes():
    """Trasy zmian statusu (take/done/release/przejmij). „Return output” kończy trasę, więc maile idą przed nim."""
    s2 = env("S2_WEBHOOK_URL")
    z = Zadanie(2)
    a = Rodzic(3)          # kto klika
    o = Rodzic(4)          # drugi rodzic (aktywny, inny klucz)
    akcja = "{{1.akcja}}"
    now = "{{now}}"
    ok_a = exists(a.id)
    st = z["Status"]

    def wynik(mid, ok, powod, naglowek, tresc, kto="", status=None, flt_=None):
        return ret(mid, {"ok": ok, "powod": powod, "kto": kto, "status": status or st,
                         "tytul": z["Tytuł"], "naglowek": naglowek, "tresc": tresc}, flt_)

    mail_przejete = template("przejete.html", imie=a["Imię"], stopka_kto=f"Sprawę bierze: {a['Imię']}",
                             **z.mail_vars())
    mail_wolne = template("wolne.html", imie=a["Imię"], stopka_kto="Nikt jeszcze nie wziął tej sprawy.",
                          link_take=link(s2, z.id, "take", o["Klucz"], z["Token"]),
                          link_done=link(s2, z.id, "done", o["Klucz"], z["Token"]), **z.mail_vars())
    prev = Rodzic(90, single=True)
    mail_przejeta = template("przejeta_od_ciebie.html", imie=a["Imię"], stopka_kto=f"Sprawę bierze: {a['Imię']}",
                             **z.mail_vars())

    return [
        at_get(2, "Zadania", "{{1.id}}",
               flt("Zmiana statusu", *[[eq(akcja, x), match("{{1.id}}", "^rec[A-Za-z0-9]{14}$")] for x in STATUS_AKCJE])),
        at_find(3, "Rodzice", f"AND({{Aktywny}}, {{Klucz}}='{{{{1.klucz}}}}')"),
        at_find(4, "Rodzice", f"AND({{Aktywny}}, {{Klucz}}!='{{{{1.klucz}}}}')"),
        router(
            5,
            [wynik(10, False, "brak_dostepu", "Brak dostępu", "Nie rozpoznaję tego rodzica.", status="",
                   flt_=flt("Nieznany rodzic", [missing(a.id)]))],
            # --- take
            [at_update(20, "Zadania", z.id, {F("Zadania", "Status"): "Przypisane",
                                            F("Zadania", "Osoba"): [a.id], F("Zadania", "Przypisano"): now},
                       flt("Biorę: wolne", [ok_a, eq(akcja, "take"), eq(st, "Nowe")])),
             zdarzenie(21, "Przypisano", f"{a['Imię']} bierze: {z['Tytuł']}", z.id, a.id),
             gmail(23, o["Email"], f"[Szkoła] {a['Imię']} bierze: {z['Tytuł']}", mail_przejete),
             wynik(22, True, "", "Gotowe, to Twoje",
                   f"{z['Tytuł']} – termin {z['Termin tekst']}. Przypomnę wieczór przed terminem.",
                   kto=a["Imię"], status="Przypisane")],
            [wynik(30, True, "juz_masz", "Już to masz", f"{z['Tytuł']} jest przypisane do Ciebie.",
                   kto=a["Imię"],
                   flt_=flt("Biorę: już moje", [ok_a, eq(akcja, "take"), eq(st, "Przypisane"), eq(z.osoba, a.id)]))],
            [zdarzenie(40, "Odrzucone kliknięcie",
                       f"{a['Imię']} chciał(a) wziąć: {z['Tytuł']} (ma {z['Osoba imię']})", z.id, a.id,
                       flt("Biorę: już cudze", [ok_a, eq(akcja, "take"), eq(st, "Przypisane"), ne(z.osoba, a.id)])),
             wynik(41, False, "przejete", f"Już przejęte przez {z['Osoba imię']}",
                   "Nic nie musisz robić.", kto=z["Osoba imię"])],
            [wynik(50, False, "zamkniete", "Zadanie zamknięte", "Ta sprawa jest już zamknięta.",
                   flt_=flt("Zamknięte (take/release/przejmij)",
                            [ok_a, ne(akcja, "done"), eq(st, "Zrobione")],
                            [ok_a, ne(akcja, "done"), eq(st, "Anulowane")]))],
            # --- done
            [wynik(60, True, "juz_oznaczone", "Już oznaczone", "Ta sprawa jest już oznaczona jako zrobiona.",
                   kto=z["Osoba imię"], flt_=flt("Zrobione: już", [ok_a, eq(akcja, "done"), eq(st, "Zrobione")]))],
            [wynik(65, False, "zamkniete", "Zadanie zamknięte", "Ta sprawa została anulowana.",
                   flt_=flt("Zrobione: anulowane", [ok_a, eq(akcja, "done"), eq(st, "Anulowane")]))],
            [at_update(70, "Zadania", z.id,
                       {F("Zadania", "Status"): "Zrobione", F("Zadania", "Zrobiono"): now,
                        F("Zadania", "Osoba"): ["{{ifempty(" + f"2.body.fields.{F('Zadania', 'Osoba')}[1]; 3.body.records[1].id" + ")}}"]},
                       flt("Zrobione: otwarte", [ok_a, eq(akcja, "done"), eq(st, "Nowe")],
                           [ok_a, eq(akcja, "done"), eq(st, "Przypisane")])),
             zdarzenie(71, "Zrobione", f"{a['Imię']} – zrobione: {z['Tytuł']}", z.id, a.id),
             wynik(72, True, "", "Zrobione, dzięki", f"{z['Tytuł']} – zamknięte.", kto=a["Imię"], status="Zrobione")],
            # --- release (Oddaj)
            [at_update(80, "Zadania", z.id,
                       {F("Zadania", "Status"): "Nowe", F("Zadania", "Osoba"): [],
                        F("Zadania", "Liczba przypomnień"): 0, F("Zadania", "Ostatnie przypomnienie"): now},
                       flt("Oddaj: moje", [ok_a, eq(akcja, "release"), eq(st, "Przypisane"), eq(z.osoba, a.id)])),
             zdarzenie(81, "Oddano", f"{a['Imię']} oddaje: {z['Tytuł']}", z.id, a.id),
             gmail(83, o["Email"], f"[Szkoła] Wolne: {z['Tytuł']}", mail_wolne),
             wynik(82, True, "", "Oddane", f"{z['Tytuł']} jest znowu wolne.", status="Nowe")],
            [wynik(85, False, "nie_twoje", "To nie Twoje zadanie", "Oddać może tylko osoba przypisana.",
                   kto=z["Osoba imię"],
                   flt_=flt("Oddaj: nie moje", [ok_a, eq(akcja, "release"), eq(st, "Nowe")],
                            [ok_a, eq(akcja, "release"), eq(st, "Przypisane"), ne(z.osoba, a.id)]))],
            # --- przejmij
            [at_get(90, "Rodzice", z.osoba,
                    flt("Przejmij: cudze", [ok_a, eq(akcja, "przejmij"), eq(st, "Przypisane"), ne(z.osoba, a.id)])),
             at_update(91, "Zadania", z.id, {F("Zadania", "Osoba"): [a.id], F("Zadania", "Przypisano"): now}),
             zdarzenie(92, "Przypisano", f"{a['Imię']} przejmuje od {z['Osoba imię']}: {z['Tytuł']}", z.id, a.id),
             gmail(94, prev["Email"], f"[Szkoła] {a['Imię']} przejmuje: {z['Tytuł']}", mail_przejeta),
             wynik(93, True, "", "Przejęte", f"{z['Tytuł']} jest teraz Twoje.", kto=a["Imię"], status="Przypisane")],
            [wynik(95, False, "stan_zmieniony", "Nie da się przejąć", "To zadanie nie jest przypisane do drugiej osoby.",
                   kto=z["Osoba imię"],
                   flt_=flt("Przejmij: nie da się", [ok_a, eq(akcja, "przejmij"), eq(st, "Nowe")],
                            [ok_a, eq(akcja, "przejmij"), eq(st, "Przypisane"), eq(z.osoba, a.id)]))],
        ),
    ]


def dodaj_routes():
    """S1 – Dodaj zadanie: walidacja, deduplikacja, rekord, zdarzenie, maile do aktywnych rodziców."""
    s2 = env("S2_WEBHOOK_URL")
    i = {k: "{{1." + k + "}}" for k in ("tytul", "termin", "opis", "kwota", "zrodlo", "id_zrodla")}
    jest = eq("{{1.akcja}}", "dodaj")
    w_przyszlosci = {"a": i["termin"], "o": "date:greater", "b": "{{now}}"}
    z = Zadanie(222)
    r = Rodzic(225, single=True)
    r.base = "225"
    mail = template("nowe.html", stopka_kto="Nikt jeszcze nie wziął tej sprawy.",
                    link_take=link(s2, z.id, "take", r["Klucz"], z["Token"]),
                    link_done=link(s2, z.id, "done", r["Klucz"], z["Token"]), **z.mail_vars())
    return [
        [ret(201, {"ok": False, "powod": "blad", "status": "blad", "tytul": i["tytul"],
                   "naglowek": "Nie dodano", "tresc": "Brak tytułu albo termin nie jest w przyszłości."},
             flt("Dodaj: błąd danych", [jest, missing(i["tytul"])], [jest, missing(i["termin"])],
                 [jest, {"a": i["termin"], "o": "date:lessorequal", "b": "{{now}}"}]))],
        [at_find(210, "Zadania", f"AND('{i['id_zrodla']}' != '', {{ID źródła}} = '{i['id_zrodla']}')",
                 flt("Dodaj: dane OK", [jest, exists(i["tytul"]), w_przyszlosci])),
         router(
             211,
             [ret(212, {"ok": False, "powod": "duplikat", "status": "duplikat", "tytul": i["tytul"],
                        "naglowek": "Duplikat", "tresc": "{{210.body.records[1].id}}"},
                  flt("Duplikat", [exists("{{210.body.records[1].id}}")]))],
             [at_create(220, "Zadania", {
                 F("Zadania", "Tytuł"): i["tytul"], F("Zadania", "Opis"): i["opis"],
                 F("Zadania", "Termin"): i["termin"], F("Zadania", "Kwota"): i["kwota"],
                 F("Zadania", "Status"): "Nowe", F("Zadania", "Token"): "{{uuid}}",
                 F("Zadania", "Źródło"): '{{ifempty(1.zrodlo; "Claude")}}', F("Zadania", "ID źródła"): i["id_zrodla"],
                 F("Zadania", "Liczba przypomnień"): 0},
                 flt("Nowe zadanie", [missing("{{210.body.records[1].id}}")])),
              zdarzenie(221, "Utworzono", f"Nowe: {i['tytul']}", "{{220.id}}"),
              at_get(222, "Zadania", "{{220.id}}"),
              at_find(223, "Rodzice", "{Aktywny}"),
              feeder(225, "{{223.body.records}}"),
              gmail(226, r["Email"], f"[Szkoła] Nowe: {z['Tytuł']} – do {z['Termin krótko']}", mail)],
         )],
    ]


def silnik():
    """Silnik (na żądanie, kolejka): jedyne miejsce, które zmienia stan zadań.

    Wołają go: Claude (konektor Make, akcja=dodaj), webhook S1-W, kliknięcia z maili i dashboard.
    Kolejka (przetwarzanie sekwencyjne) chroni przed dwoma jednoczesnymi „Biorę to”.
    """
    return {"name": "Asystent – Silnik (dodaj i zmień status)",
            "flow": [start(1), router(100, status_routes(), *dodaj_routes())],
            "metadata": metadata(sequential=True)}


SILNIK_INTERFACE = {
    "input": [
        {"name": "akcja", "type": "text", "required": True,
         "label": "dodaj – nowa sprawa szkolna; take / done / release / przejmij – zmiana statusu"},
        {"name": "tytul", "type": "text", "required": False, "label": "Krótka nazwa sprawy, maks. 100 znaków"},
        {"name": "termin", "type": "text", "required": False,
         "label": "Data i godzina w Europe/Warsaw (ISO 8601), np. 2026-11-14T08:00:00+01:00"},
        {"name": "opis", "type": "text", "required": False, "label": "Co przynieść, ile zapłacić, szczegóły"},
        {"name": "kwota", "type": "number", "required": False, "label": "Kwota w PLN"},
        {"name": "zrodlo", "type": "text", "required": False, "label": "Claude, Webhook lub Scraper; domyślnie Claude"},
        {"name": "id_zrodla", "type": "text", "required": False, "label": "Identyfikator do deduplikacji"},
        {"name": "id", "type": "text", "required": False, "label": "ID zadania (dla zmiany statusu)"},
        {"name": "klucz", "type": "text", "required": False, "label": "Klucz rodzica (dla zmiany statusu)"},
    ],
    "output": [
        {"name": "ok", "type": "boolean", "label": "Czy się udało"},
        {"name": "powod", "type": "text", "label": "Powód odmowy"},
        {"name": "kto", "type": "text", "label": "Kto ma zadanie"},
        {"name": "status", "type": "text", "label": "Status po zmianie"},
        {"name": "tytul", "type": "text", "label": "Tytuł"},
        {"name": "naglowek", "type": "text", "label": "Nagłówek strony"},
        {"name": "tresc", "type": "text", "label": "Treść strony"},
    ],
}


def po_zmianie(z, kto_id, akcja, mid=30):
    """Trasy strony wyniku S2 dobrane do stanu zadania po wywołaniu Silnika.

    Scenariusz utworzony przez API nie zwraca wyjść do modułu „Call a scenario”
    (Make synchronizuje je tylko w edytorze), więc wynik czytamy z Airtable.
    """
    st = z["Status"]

    def page(i, naglowek, tresc, *groups):
        return [respond(mid + i, 200, template("strony/wynik.html", naglowek=naglowek, tresc=tresc),
                        flt=flt(naglowek[:40], *groups))]

    return [
        page(0, "Gotowe, to Twoje", f"{z['Tytuł']} – termin {z['Termin tekst']}. Przypomnę wieczór przed terminem.",
             [eq(akcja, "take"), eq(st, "Przypisane"), eq(z.osoba, kto_id)]),
        page(1, f"Już przejęte przez {z['Osoba imię']}", "Nic nie musisz robić.",
             [eq(akcja, "take"), eq(st, "Przypisane"), ne(z.osoba, kto_id)]),
        page(2, "Zadanie zamknięte", "Ta sprawa jest już zamknięta.",
             [eq(akcja, "take"), eq(st, "Zrobione")], [eq(akcja, "take"), eq(st, "Anulowane")],
             [eq(akcja, "done"), eq(st, "Anulowane")]),
        page(3, "Zrobione, dzięki", f"{z['Tytuł']} – zamknięte.", [eq(akcja, "done"), eq(st, "Zrobione")]),
        page(4, "Coś poszło nie tak", "Spróbuj jeszcze raz za chwilę albo otwórz listę spraw.",
             [eq(akcja, "take"), eq(st, "Nowe")], [eq(akcja, "done"), eq(st, "Nowe")],
             [eq(akcja, "done"), eq(st, "Przypisane")]),
    ]


def klikniecia_routes(bez_celu):
    """S2 – kliknięcia z maili: GET pokazuje potwierdzenie, POST (ok=1) zmienia stan przez Silnik."""
    s2 = env("S2_WEBHOOK_URL")
    z = Zadanie(4, prefix="body.records[1].fields")
    z_id = "{{4.body.records[1].id}}"
    r = Rodzic(5)
    q = {k: "{{1." + k + "}}" for k in ("t", "a", "p", "k", "ok")}
    PAT = {"t": "^rec[A-Za-z0-9]{14}$", "a": "^(take|done)$", "p": "^[a-z0-9_-]{1,30}$",
           "k": "^[A-Za-z0-9-]{8,64}$"}
    valid = [match(q[k], p) for k, p in PAT.items()]
    found = [exists(z_id), exists(r.id)]
    get = missing(q["ok"])
    st = z["Status"]

    page_bad = template("strony/wynik.html", naglowek="Link nieważny",
                        tresc="Ten link jest nieprawidłowy albo wygasł. Otwórz najnowszy mail ze szkoły.")

    def potwierdzenie(przycisk):
        return template("strony/potwierdzenie.html", tytul=z["Tytuł"], termin_dlugi=z["Termin tekst"],
                        opis=z["Opis"], kwota_html=f"<p>{z['Kwota linia']}</p>", przycisk_html=przycisk)

    def form(akcja, etykieta, klasa):
        return template("strony/formularz.html", S2_WEBHOOK_URL=s2, t=q["t"], a=akcja, p=q["p"], k=q["k"],
                        klasa=klasa, etykieta=etykieta)

    info = '<p style="font-size:18px;font-weight:600">{}</p>'
    return [
        [respond(3, 403, page_bad,
                 flt=flt("Kliknięcie: złe parametry", *[[bez_celu, nomatch(q[k], p)] for k, p in PAT.items()]))],
        [at_find(4, "Zadania", f"AND(RECORD_ID()='{q['t']}', {{Token}}='{q['k']}')",
                 flt=flt("Kliknięcie: parametry OK", [bez_celu, *valid])),
         at_find(5, "Rodzice", f"AND({{Aktywny}}, {{Klucz}}='{q['p']}')"),
         router(
             6,
             [zdarzenie(7, "Odrzucone kliknięcie", f"Nieważny link: t={q['t']} p={q['p']}",
                        flt=flt("Nie znaleziono", [missing(z_id)], [missing(r.id)])),
              respond(8, 403, page_bad)],
             [respond(10, 200, potwierdzenie(info.format("Zadanie zamknięte")),
                      flt=flt("GET: zamknięte", [*found, get, eq(st, "Zrobione")],
                              [*found, get, eq(st, "Anulowane")]))],
             [respond(11, 200, potwierdzenie(info.format(f"Już przejęte przez {z['Osoba imię']}")),
                      flt=flt("GET: take, ma ktoś inny", [*found, get, eq(q["a"], "take"), eq(st, "Przypisane"),
                                                          ne(z.osoba, r.id)]))],
             [respond(14, 200, potwierdzenie(info.format("To już Twoje")),
                      flt=flt("GET: take, już moje", [*found, get, eq(q["a"], "take"), eq(st, "Przypisane"),
                                                      eq(z.osoba, r.id)]))],
             [respond(12, 200, potwierdzenie(form("take", "Biorę to", "")),
                      flt=flt("GET: take, wolne", [*found, get, eq(q["a"], "take"), eq(st, "Nowe")]))],
             [respond(13, 200, potwierdzenie(form("done", "Zrobione", "done")),
                      flt=flt("GET: done, otwarte", [*found, get, eq(q["a"], "done"), eq(st, "Nowe")],
                              [*found, get, eq(q["a"], "done"), eq(st, "Przypisane")]))],
             [call(20, "MAKE_ID_SILNIK", {"akcja": q["a"], "id": z_id, "klucz": q["p"]},
                   flt=flt("POST: potwierdzone", [*found, eq(q["ok"], "1")])),
              # stan po zmianie: strona wyniku wynika z tego, co jest teraz w Airtable
              at_find(22, "Zadania", f"RECORD_ID()='{q['t']}'"),
              router(23, *po_zmianie(Zadanie(22, prefix="body.records[1].fields"), r.id, q["a"]))],
         )],
    ]


def json_headers():
    return [{"key": "Access-Control-Allow-Origin", "value": env("DASHBOARD_ORIGIN", "https://pogodae.github.io")}]


def jresp(mid, status, body, flt_=None):
    return respond(mid, status, body, ctype="application/json; charset=utf-8", extra_headers=json_headers(), flt=flt_)


# klucz API z nagłówka X-Api-Key (webhook przekazuje nagłówki w __IMTHEADERS__)
API_KEY = '{{first(map(1.__IMTHEADERS__; "value"; "name"; "x-api-key"))}}'


def s1w_routes(cel_eq):
    """S1-W – dodawanie zadań webhookiem (POST JSON, nagłówek X-Api-Key)."""
    i = {k: "{{1." + k + "}}" for k in ("tytul", "termin", "opis", "kwota", "zrodlo", "id_zrodla")}
    cel = cel_eq("dodaj")
    klucz_ok = eq(API_KEY, env("S1W_API_KEY"))
    dane_ok = [exists(i["tytul"]), {"a": i["termin"], "o": "date:greater", "b": "{{now}}"}]
    dup = "{{310.body.records[1].id}}"
    return [
        [jresp(300, 401, '{"status":"blad","komunikat":"Brak lub zły nagłówek X-Api-Key"}',
               flt("S1-W: zły klucz", [cel, ne(API_KEY, env("S1W_API_KEY"))]))],
        [jresp(301, 400, '{"status":"blad","komunikat":"Brak tytułu albo termin nie jest datą w przyszłości."}',
               flt("S1-W: błąd danych", [cel, klucz_ok, missing(i["tytul"])], [cel, klucz_ok, missing(i["termin"])],
                   [cel, klucz_ok, {"a": i["termin"], "o": "date:lessorequal", "b": "{{now}}"}]))],
        [at_find(310, "Zadania", f"AND('{i['id_zrodla']}' != '', {{ID źródła}} = '{i['id_zrodla']}')",
                 flt("S1-W: dane OK", [cel, klucz_ok, *dane_ok])),
         router(
             311,
             [jresp(312, 200, '{"status":"duplikat","id":"' + dup + '"}', flt("Duplikat", [exists(dup)]))],
             [call(320, "MAKE_ID_SILNIK", {"akcja": "dodaj", "tytul": i["tytul"], "termin": i["termin"],
                                           "opis": i["opis"], "kwota": i["kwota"],
                                           "zrodlo": '{{ifempty(1.zrodlo; "Webhook")}}', "id_zrodla": i["id_zrodla"]},
                   flt("Nowe", [missing(dup)])),
              at_find(321, "Zadania", f"AND('{i['id_zrodla']}' != '', {{ID źródła}} = '{i['id_zrodla']}')"),
              jresp(322, 200, '{"status":"utworzono","id":"{{321.body.records[1].id}}","termin":"' + i["termin"] + '"}')],
         )],
    ]


def s5_routes(cel_eq):
    """S5 – API dashboardu: proste POST-y (form-urlencoded), odpowiedź JSON z CORS."""
    cel = cel_eq("api")
    q = {k: "{{1." + k + "}}" for k in ("u", "s", "akcja", "id")}
    PU, PS = "^[a-z0-9_-]{1,30}$", "^[A-Za-z0-9_-]{16,64}$"
    ja = "{{401.body.records[1].id}}"

    def find_names(mid, formula, flt_=None):
        """Zadania z nazwami pól (czytelny JSON dla dashboardu). Make przy powtórzonym parametrze
        fields[] zostawia tylko ostatni, więc nie zawężamy pól."""
        m = at_find(mid, "Zadania", formula, flt=flt_)
        m["mapper"]["qs"] = [{"key": "filterByFormula", "value": formula}]
        return m

    otwarte = ("OR({Status}='Nowe', {Status}='Przypisane', "
               "AND({Status}='Zrobione', DATETIME_DIFF(NOW(), {Zrobiono}, 'days') < 7))")
    zmiana = [[exists(ja), eq(q["akcja"], a), match(q["id"], "^rec[A-Za-z0-9]{14}$")] for a in STATUS_AKCJE]
    return [
        [jresp(400, 403, '{"ok":false,"powod":"brak_dostepu"}',
               flt("API: złe dane logowania", [cel, nomatch(q["u"], PU)], [cel, nomatch(q["s"], PS)]))],
        [at_find(401, "Rodzice", f"AND({{Aktywny}}, {{Klucz}}='{q['u']}', {{Klucz dostępu}}='{q['s']}')",
                 flt("API: dane logowania OK", [cel, match(q["u"], PU), match(q["s"], PS)])),
         router(
             402,
             [jresp(403, 403, '{"ok":false,"powod":"brak_dostepu"}', flt("Brak dostępu", [missing(ja)]))],
             [find_names(410, otwarte, flt("Lista", [exists(ja), eq(q["akcja"], "lista")])),
              tojson(411, "{{410.body.records}}"),
              jresp(412, 200, '{"ok":true,"ja":"{{401.body.records[1].fields.' + F("Rodzice", "Imię") +
                    '}}","zadania":{{411.json}}}')],
             [call(420, "MAKE_ID_SILNIK", {"akcja": q["akcja"], "id": q["id"], "klucz": q["u"]},
                   flt("Zmiana statusu", *zmiana)),
              find_names(421, f"RECORD_ID()='{q['id']}'"),
              tojson(422, "{{421.body.records[1]}}"),
              jresp(423, 200, '{"ok":true,"zadanie":{{422.json}}}')],
             [jresp(430, 400, '{"ok":false,"powod":"nieznana_akcja"}',
                    flt("Nieznana akcja", [exists(ja), ne(q["akcja"], "lista"),
                                           *[ne(q["akcja"], a) for a in STATUS_AKCJE]]))],
         )],
    ]


def s3_routes(cel_eq):
    """S3 – przypomnienia. Uruchamia je harmonogram GitHub Actions (POST ?cel=przypomnienia z X-Api-Key),
    bo darmowy plan Make pozwala tylko na 2 aktywne scenariusze.

    Parametry z query (do testów): odstep (ODSTEP_H, domyślnie 4), wieczor=1 (wymusza gałąź B).
    """
    s2 = env("S2_WEBHOOK_URL")
    cel = cel_eq("przypomnienia")
    odstep = "{{ifempty(1.odstep; 4)}}"
    now = "{{now}}"

    # --- A: nikt nie wziął
    za = Zadanie(511, prefix="fields")
    za_id = "{{511.id}}"
    ra = Rodzic(513, single=True)
    ra.base = "513"
    mail_a = template("przypomnienie.html", stopka_kto="Nikt jeszcze nie wziął tej sprawy.",
                      dopisek_pilne=za["Dopisek pilne"],
                      link_take=link(s2, za_id, "take", ra["Klucz"], za["Token"]),
                      link_done=link(s2, za_id, "done", ra["Klucz"], za["Token"]), **za.mail_vars())
    formula_a = ("AND({Status}='Nowe', DATETIME_DIFF(NOW(),{Utworzono},'hours')>=" + odstep +
                 ", OR({Ostatnie przypomnienie}=BLANK(), DATETIME_DIFF(NOW(),{Ostatnie przypomnienie},'hours')>=" +
                 odstep + "))")
    # --- B: wieczór przed terminem
    zb = Zadanie(521, prefix="fields")
    zb_id = "{{521.id}}"
    rb = Rodzic(524, single=True)
    mail_b = template("jutro.html", stopka_kto=f"Sprawę masz Ty – {rb['Imię']}",
                      link_done=link(s2, zb_id, "done", rb["Klucz"], zb["Token"]), **zb.mail_vars())
    formula_b = ("AND({Status}='Przypisane', NOT({Przypomnienie przed terminem}), {Godzin do terminu}>0, "
                 "{Godzin do terminu}<=28, OR('{{1.wieczor}}'='1', "
                 "VALUE(DATETIME_FORMAT(SET_TIMEZONE(NOW(), 'Europe/Warsaw'), 'H'))>=18, {Godzin do terminu}<=6))")
    # --- C: po terminie
    zc = Zadanie(531, prefix="fields")
    zc_id = "{{531.id}}"
    rc = Rodzic(535, single=True)
    rc.base = "535"
    mail_c = template("po_terminie.html", stopka_kto=f"Przypisane do: {zc['Osoba imię']}",
                      link_done=link(s2, zc_id, "done", rc["Klucz"], zc["Token"]), **zc.mail_vars())
    formula_c = ("AND(OR({Status}='Nowe', {Status}='Przypisane'), IS_BEFORE({Termin}, NOW()), NOT({Po terminie}))")

    klucz_ok = eq(API_KEY, env("S1W_API_KEY"))
    return [
        [jresp(500, 401, '{"ok":false}', flt("S3: zły klucz", [cel, ne(API_KEY, env("S1W_API_KEY"))]))],
        [jresp(501, 200, '{"ok":true}', flt("S3: start", [cel, klucz_ok])),
         router(
             502,
             [at_find(510, "Zadania", formula_a),
              feeder(511, "{{510.body.records}}"),
              at_update(514, "Zadania", za_id, {
                  F("Zadania", "Liczba przypomnień"): "{{ifempty(511.fields." + F("Zadania", "Liczba przypomnień") +
                                                      "; 0) + 1}}",
                  F("Zadania", "Ostatnie przypomnienie"): now}),
              zdarzenie(515, "Przypomnienie", f"Nikt jeszcze nie wziął: {za['Tytuł']}", za_id),
              at_find(512, "Rodzice", "{Aktywny}"),
              feeder(513, "{{512.body.records}}"),
              gmail(516, ra["Email"], f"[Szkoła] Nikt jeszcze nie wziął: {za['Tytuł']}{za['Dopisek pilne']}", mail_a)],
             [at_find(520, "Zadania", formula_b),
              feeder(521, "{{520.body.records}}"),
              at_update(522, "Zadania", zb_id, {F("Zadania", "Przypomnienie przed terminem"): True}),
              zdarzenie(523, "Przypomnienie", f"Jutro: {zb['Tytuł']}", zb_id),
              at_get(524, "Rodzice", "{{521.fields." + F("Zadania", "Osoba") + "[1]}}"),
              gmail(525, rb["Email"], f"[Szkoła] Jutro: {zb['Tytuł']}", mail_b)],
             [at_find(530, "Zadania", formula_c),
              feeder(531, "{{530.body.records}}"),
              at_update(532, "Zadania", zc_id, {F("Zadania", "Po terminie"): True}),
              zdarzenie(533, "Eskalacja", f"Po terminie: {zc['Tytuł']}", zc_id),
              at_find(534, "Rodzice", "{Aktywny}"),
              feeder(535, "{{534.body.records}}"),
              gmail(536, rc["Email"], f"[Szkoła] Po terminie: {zc['Tytuł']} – zrobione?", mail_c)],
         )],
    ]


def scenariusz_api():
    """Jeden webhook dla wszystkiego, co przychodzi z zewnątrz (?cel=…):
    brak celu – kliknięcia z maili (S2), dodaj – S1-W, api – dashboard (S5), przypomnienia – S3."""
    def cel_eq(c):
        return eq("{{1.cel}}", c)

    return {"name": "Asystent – API (maile, webhook, dashboard, przypomnienia)",
            "flow": [webhook(1, "S2_HOOK_ID"),
                     router(2, *klikniecia_routes(missing("{{1.cel}}")), *s1w_routes(cel_eq),
                            *s5_routes(cel_eq), *s3_routes(cel_eq))],
            "metadata": metadata(sequential=False)}


SCENARIOS = {
    "silnik": silnik,
    "api": scenariusz_api,
}


# ---------------------------------------------------------------- zapis

def layout(flow, x=0, y=0):
    """Rozmieszcza moduły na płótnie Make: kolejne w prawo, trasy routera w dół."""
    for m in flow:
        m["metadata"]["designer"] = {"x": x, "y": y}
        x += 300
        if m.get("routes"):
            for i, r in enumerate(m["routes"]):
                layout(r["flow"], x, y + i * 250)
    return flow


def redact(text):
    for name in SECRETS:
        val = env(name)
        if val:
            text = text.replace(val, f"__{name}__")
    return text


def main(names):
    load_env()
    DEPLOY.mkdir(exist_ok=True)
    for name in names or SCENARIOS:
        bp = SCENARIOS[name]()
        layout(bp["flow"])
        real = json.dumps(bp, ensure_ascii=False, indent=1)
        (DEPLOY / f"{name}.json").write_text(real, encoding="utf-8")
        (MAKE / f"{name}.json").write_text(redact(real), encoding="utf-8")
        print(f"{name}: {len(real)} B")


if __name__ == "__main__":
    main(sys.argv[1:])
