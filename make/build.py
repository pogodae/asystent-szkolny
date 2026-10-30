"""Generator blueprintów Make dla asystenta „Kto to ogarnia” (sprawy dzieci i domu).

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
SECRETS = ("S2_WEBHOOK_URL", "S5_WEBHOOK_URL", "S1W_API_KEY", "RODZIC1_KLUCZ_DOSTEPU", "RODZIC2_KLUCZ_DOSTEPU")


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
    left = [p for p in ("{{tytul}}", "{{opis}}", "{{stopka_kto}}", "{{DASHBOARD_URL}}") if p in html]
    if left:
        raise ValueError(f"{name}: niepodstawione {left}")
    return html


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


STATUS_AKCJE = ("take", "done", "release", "przejmij", "przypisz")
# kategoria: czego dotyczy sprawa (pusta = bez kategorii)
KATEGORIA_PAT = "^(Dominik|Mateusz|Dom)?$"
# rodzice z powiadomieniami „Tylko przypisane” nie dostają maili o sprawach, które ich nie dotyczą
DO_WSZYSTKICH = "{Powiadomienia}!='Tylko przypisane'"
# rodzaj terminu; pusty = Wydarzenie (data z godziną)
RODZAJ_PAT = "^(Do dnia|W dniu|Wydarzenie)?$"
RODZAJ = '{{ifempty(1.rodzaj; "Wydarzenie")}}'


def rekord_zadania(i, zrodlo):
    """Pola nowego zadania (wspólne dla Silnika i dodawania z dashboardu)."""
    return {
        F("Zadania", "Tytuł"): i["tytul"], F("Zadania", "Opis"): i["opis"],
        F("Zadania", "Termin"): i["termin"], F("Zadania", "Kwota"): i["kwota"],
        F("Zadania", "Status"): "Nowe", F("Zadania", "Źródło"): zrodlo, F("Zadania", "ID źródła"): i["id_zrodla"],
        F("Zadania", "Liczba przypomnień"): 0, F("Zadania", "Rodzaj"): RODZAJ,
        F("Zadania", "Kategoria"): i["kategoria"]}


def status_routes():
    """Zmiany statusu (take/done/release/przejmij/przypisz). Każda trasa to odczyt + zapis – 2 operacje.

    Kto klika, przekazuje wywołujący (kto = ID rekordu w Rodzice, kto_imie), więc Silnik nie szuka
    rodzica w Airtable. Odmowy (np. zadanie już przejęte) po prostu nic nie zmieniają – dashboard
    pokaże prawdziwy stan przy następnym pobraniu listy. Bez wpisów do tabeli Zdarzenia (oszczędność
    operacji) – statystyki liczą się z pól Przypisano / Zrobiono / Utworzono.
    """
    z = Zadanie(2)
    akcja = "{{1.akcja}}"
    kto = "{{1.kto}}"
    now = "{{now}}"
    st = z["Status"]
    t = Rodzic(110)        # komu przypisujemy (akcja przypisz)
    mail_przypisane = template("przypisane.html", imie="{{1.kto_imie}}", stopka_kto="Sprawa jest teraz Twoja.",
                               **z.mail_vars())

    def ok(mid, status):
        return ret(mid, {"ok": True, "powod": "", "kto": "{{1.kto_imie}}", "status": status, "tytul": z["Tytuł"],
                         "naglowek": "", "tresc": ""})

    return [
        at_get(2, "Zadania", "{{1.id}}",
               flt("Zmiana statusu", *[[eq(akcja, x), match("{{1.id}}", "^rec[A-Za-z0-9]{14}$"),
                                        match(kto, "^rec[A-Za-z0-9]{14}$")] for x in STATUS_AKCJE])),
        router(
            5,
            [at_update(20, "Zadania", z.id, {F("Zadania", "Status"): "Przypisane", F("Zadania", "Osoba"): [kto],
                                            F("Zadania", "Przypisano"): now},
                       flt("Biorę: wolne", [eq(akcja, "take"), eq(st, "Nowe")])),
             ok(22, "Przypisane")],
            [at_update(70, "Zadania", z.id,
                       {F("Zadania", "Status"): "Zrobione", F("Zadania", "Zrobiono"): now,
                        F("Zadania", "Osoba"): ["{{ifempty(" + f"2.body.fields.{F('Zadania', 'Osoba')}[1]; 1.kto" + ")}}"]},
                       flt("Zrobione: otwarte", [eq(akcja, "done"), eq(st, "Nowe")],
                           [eq(akcja, "done"), eq(st, "Przypisane")])),
             ok(72, "Zrobione")],
            [at_update(80, "Zadania", z.id,
                       {F("Zadania", "Status"): "Nowe", F("Zadania", "Osoba"): [],
                        F("Zadania", "Liczba przypomnień"): 0, F("Zadania", "Ostatnie przypomnienie"): now,
                        F("Zadania", "Przypomnienie przed terminem"): False},
                       flt("Oddaj: moje", [eq(akcja, "release"), eq(st, "Przypisane"), eq(z.osoba, kto)])),
             ok(82, "Nowe")],
            [at_update(91, "Zadania", z.id, {F("Zadania", "Osoba"): [kto], F("Zadania", "Przypisano"): now},
                       flt("Przejmij: cudze", [eq(akcja, "przejmij"), eq(st, "Przypisane"), ne(z.osoba, kto)])),
             ok(93, "Przypisane")],
            # --- przypisz: wolne albo własne zadanie dostaje wskazana osoba (dla = jej klucz)
            [at_find(110, "Rodzice", f"AND({{Aktywny}}, {{Klucz}}='{{{{1.dla}}}}')",
                     flt("Przypisz: można", [eq(akcja, "przypisz"), eq(st, "Nowe")],
                         [eq(akcja, "przypisz"), eq(st, "Przypisane"), eq(z.osoba, kto)])),
             at_update(111, "Zadania", z.id, {F("Zadania", "Status"): "Przypisane", F("Zadania", "Osoba"): [t.id],
                                             F("Zadania", "Przypisano"): now},
                       flt("Jest taka osoba", [exists(t.id)])),
             # mail od razu tylko do osób z „Tylko przypisane” (nie zaglądają na dashboard)
             gmail(113, t["Email"], f"{{{{1.kto_imie}}}} przypisuje Ci: {z['Tytuł']}{z['Kategoria dopisek']}",
                   mail_przypisane, flt("Nie sobie, chce maila", [ne(t.id, kto), eq(t["Powiadomienia"], "Tylko przypisane")])),
             ok(114, "Przypisane")],
        ),
    ]


def dodaj_routes():
    """S1 – Dodaj zadanie (Claude, S1-W): walidacja, deduplikacja (tylko gdy jest id_zrodla), rekord.
    Bez maili – przypomni S3 dzień przed."""
    i = {k: "{{1." + k + "}}" for k in ("tytul", "termin", "opis", "kwota", "zrodlo", "id_zrodla", "rodzaj", "kategoria")}
    jest = eq("{{1.akcja}}", "dodaj")
    dane_ok = [jest, exists(i["tytul"]), {"a": i["termin"], "o": "date:greater", "b": "{{now}}"},
               match(i["rodzaj"], RODZAJ_PAT), match(i["kategoria"], KATEGORIA_PAT)]
    zrodlo = '{{ifempty(1.zrodlo; "Claude")}}'
    dup = "{{210.body.records[1].id}}"
    return [
        [ret(201, {"ok": False, "powod": "blad", "status": "blad", "tytul": i["tytul"],
                   "naglowek": "Nie dodano", "tresc": "Brak tytułu albo termin nie jest w przyszłości."},
             flt("Dodaj: błąd danych", [jest, missing(i["tytul"])], [jest, missing(i["termin"])],
                 [jest, {"a": i["termin"], "o": "date:lessorequal", "b": "{{now}}"}],
                 [jest, nomatch(i["rodzaj"], RODZAJ_PAT)], [jest, nomatch(i["kategoria"], KATEGORIA_PAT)]))],
        # bez id_zrodla (Claude) – od razu zapis, bez zapytania o duplikat
        [at_create(230, "Zadania", rekord_zadania(i, zrodlo), flt("Dodaj: bez id_zrodla", [*dane_ok, missing(i["id_zrodla"])]))],
        [at_find(210, "Zadania", f"{{ID źródła}} = '{i['id_zrodla']}'",
                 flt("Dodaj: z id_zrodla", [*dane_ok, exists(i["id_zrodla"])])),
         at_create(220, "Zadania", rekord_zadania(i, zrodlo), flt("Nie duplikat", [missing(dup)]))],
    ]


def silnik():
    """Silnik (na żądanie, kolejka): jedyne miejsce, które zmienia stan zadań.

    Wołają go: Claude (konektor Make, akcja=dodaj), webhook S1-W i dashboard (zmiany statusu).
    Kolejka (przetwarzanie sekwencyjne) chroni przed dwoma jednoczesnymi „Biorę to”.
    """
    return {"name": "Asystent – Silnik (dodaj i zmień status)",
            "flow": [start(1), router(100, status_routes(), *dodaj_routes())],
            "metadata": metadata(sequential=True)}


SILNIK_INTERFACE = {
    "input": [
        {"name": "akcja", "type": "text", "required": True,
         "label": "dodaj – nowa sprawa (dzieci albo dom); take / done / release / przejmij / przypisz – zmiana statusu"},
        {"name": "tytul", "type": "text", "required": False, "label": "Krótka nazwa sprawy, maks. 100 znaków"},
        {"name": "termin", "type": "text", "required": False,
         "label": "Data i godzina w Europe/Warsaw (ISO 8601), np. 2026-11-14T08:00:00+01:00"},
        {"name": "opis", "type": "text", "required": False, "label": "Co przynieść, ile zapłacić, szczegóły"},
        {"name": "kwota", "type": "number", "required": False, "label": "Kwota w PLN"},
        {"name": "zrodlo", "type": "text", "required": False, "label": "Claude, Webhook, Scraper lub Dashboard; domyślnie Claude"},
        {"name": "rodzaj", "type": "text", "required": False,
         "label": "Do dnia (zrobić najpóźniej tego dnia, termin T20:00), W dniu (tego dnia, np. przynieść coś, termin T07:30) albo Wydarzenie (o konkretnej godzinie); domyślnie Wydarzenie"},
        {"name": "kategoria", "type": "text", "required": False,
         "label": "Czego dotyczy sprawa: Dominik, Mateusz albo Dom (puste = bez kategorii)"},
        {"name": "id_zrodla", "type": "text", "required": False, "label": "Identyfikator do deduplikacji"},
        {"name": "id", "type": "text", "required": False, "label": "ID zadania (dla zmiany statusu)"},
        {"name": "kto", "type": "text", "required": False, "label": "ID rekordu rodzica, który zmienia status (Rodzice)"},
        {"name": "kto_imie", "type": "text", "required": False, "label": "Imię rodzica, który zmienia status"},
        {"name": "dla", "type": "text", "required": False, "label": "Klucz osoby, której przypisujemy (akcja przypisz)"},
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


def stare_linki_routes(bez_celu):
    """Maile nie mają już przycisków akcji (wszystko robi się na dashboardzie).
    Link z dawnego maila pokazuje tylko stronę z odnośnikiem do listy spraw."""
    strona = template("strony/wynik.html", naglowek="Sprawy są na liście",
                      tresc="Przyciski w mailach już nie działają – wszystko zrobisz na liście spraw.")
    return [[respond(3, 200, strona, flt=flt("Stary link z maila", [bez_celu]))]]


def json_headers():
    return [{"key": "Access-Control-Allow-Origin", "value": env("DASHBOARD_ORIGIN", "https://pogodae.github.io")}]


def jresp(mid, status, body, flt_=None):
    return respond(mid, status, body, ctype="application/json; charset=utf-8", extra_headers=json_headers(), flt=flt_)


# klucz API z nagłówka X-Api-Key (webhook przekazuje nagłówki w __IMTHEADERS__)
API_KEY = '{{first(map(1.__IMTHEADERS__; "value"; "name"; "x-api-key"))}}'


def s1w_routes(cel_eq):
    """S1-W – dodawanie zadań webhookiem (POST JSON, nagłówek X-Api-Key)."""
    i = {k: "{{1." + k + "}}" for k in ("tytul", "termin", "opis", "kwota", "zrodlo", "id_zrodla", "rodzaj", "kategoria")}
    cel = cel_eq("dodaj")
    klucz_ok = eq(API_KEY, env("S1W_API_KEY"))
    dane_ok = [exists(i["tytul"]), {"a": i["termin"], "o": "date:greater", "b": "{{now}}"}, match(i["rodzaj"], RODZAJ_PAT),
               match(i["kategoria"], KATEGORIA_PAT)]
    dup = "{{310.body.records[1].id}}"
    return [
        [jresp(300, 401, '{"status":"blad","komunikat":"Brak lub zły nagłówek X-Api-Key"}',
               flt("S1-W: zły klucz", [cel, ne(API_KEY, env("S1W_API_KEY"))]))],
        [jresp(301, 400, '{"status":"blad","komunikat":"Brak tytułu albo termin nie jest datą w przyszłości."}',
               flt("S1-W: błąd danych", [cel, klucz_ok, missing(i["tytul"])], [cel, klucz_ok, missing(i["termin"])],
                   [cel, klucz_ok, {"a": i["termin"], "o": "date:lessorequal", "b": "{{now}}"}],
                   [cel, klucz_ok, nomatch(i["rodzaj"], RODZAJ_PAT)], [cel, klucz_ok, nomatch(i["kategoria"], KATEGORIA_PAT)]))],
        [at_find(310, "Zadania", f"AND('{i['id_zrodla']}' != '', {{ID źródła}} = '{i['id_zrodla']}')",
                 flt("S1-W: dane OK", [cel, klucz_ok, *dane_ok])),
         router(
             311,
             [jresp(312, 200, '{"status":"duplikat","id":"' + dup + '"}', flt("Duplikat", [exists(dup)]))],
             [call(320, "MAKE_ID_SILNIK", {"akcja": "dodaj", "tytul": i["tytul"], "termin": i["termin"],
                                           "opis": i["opis"], "kwota": i["kwota"],
                                           "zrodlo": '{{ifempty(1.zrodlo; "Webhook")}}', "id_zrodla": i["id_zrodla"],
                                           "rodzaj": i["rodzaj"], "kategoria": i["kategoria"]},
                   flt("Nowe", [missing(dup)])),
              at_find(321, "Zadania", f"AND('{i['id_zrodla']}' != '', {{ID źródła}} = '{i['id_zrodla']}')"),
              jresp(322, 200, '{"status":"utworzono","id":"{{321.body.records[1].id}}","termin":"' + i["termin"] + '"}')],
         )],
    ]


def s5_routes(cel_eq):
    """S5 – API dashboardu: proste POST-y (form-urlencoded), odpowiedź JSON z CORS.

    Dostęp sprawdzają filtry (pary klucz rodzica + klucz dostępu z .env, w repo zastąpione znacznikami),
    a nie zapytanie do Airtable – to jedna operacja Make mniej przy każdym żądaniu.
    """
    cel = cel_eq("api")
    q = {k: "{{1." + k + "}}" for k in ("u", "s", "akcja", "id", "dla")}
    rodzice = [(env(f"RODZIC{i}_KLUCZ"), env(f"RODZIC{i}_KLUCZ_DOSTEPU"), env(f"RODZIC{i}_IMIE")) for i in (1, 2)]
    ja = "{{switch(1.u; " + "; ".join(f'"{k}"; "{imie}"' for k, _, imie in rodzice) + ")}}"
    ja_rec = "{{switch(1.u; " + "; ".join(f'"{env(f"RODZIC{i}_KLUCZ")}"; "{env(f"RODZIC{i}_REC")}"' for i in (1, 2)) + ")}}"

    def zalogowany(*grupy):
        """Iloczyn: (dowolna poprawna para u + s) AND (dowolna z grup warunków)."""
        grupy = grupy or ([],)
        return [[cel, eq(q["u"], k), eq(q["s"], key), *g] for k, key, _ in rodzice for g in grupy]

    def find_names(mid, formula, flt_=None):
        """Zadania z nazwami pól (czytelny JSON dla dashboardu). Make przy powtórzonym parametrze
        fields[] zostawia tylko ostatni, więc nie zawężamy pól."""
        m = at_find(mid, "Zadania", formula, flt=flt_)
        m["mapper"]["qs"] = [{"key": "filterByFormula", "value": formula}]
        return m

    otwarte = ("OR({Status}='Nowe', {Status}='Przypisane', "
               "AND({Status}='Zrobione', DATETIME_DIFF(NOW(), {Zrobiono}, 'days') < 7))")
    zmiana = [[eq(q["akcja"], a), match(q["id"], "^rec[A-Za-z0-9]{14}$"), match(q["dla"], "^[a-z0-9_-]{0,30}$")]
              for a in STATUS_AKCJE]
    dodaj = eq(q["akcja"], "dodaj")
    n = {k: "{{1." + k + "}}" for k in ("tytul", "termin", "opis", "kwota", "id_zrodla", "rodzaj", "kategoria")}
    PD = "^dash-[a-f0-9-]{8,40}$"
    bez_dostepu = ([[cel, *[ne(q["u"], k) for k, _, _ in rodzice]]] +
                   [[cel, eq(q["u"], k), ne(q["s"], key)] for k, key, _ in rodzice])
    return [
        [jresp(400, 403, '{"ok":false,"powod":"brak_dostepu"}', flt("API: brak dostępu", *bez_dostepu))],
        [find_names(410, otwarte, flt("Lista", *zalogowany([eq(q["akcja"], "lista")]))),
         tojson(411, "{{410.body.records}}"),
         jresp(412, 200, '{"ok":true,"ja":"' + ja + '","zadania":{{411.json}}}')],
        # zmiana statusu: Silnik w kolejce; bez ponownego odczytu zadania (dashboard zmienia kartę sam)
        [call(420, "MAKE_ID_SILNIK", {"akcja": q["akcja"], "id": q["id"], "kto": ja_rec, "kto_imie": ja, "dla": q["dla"]},
              flt("Zmiana statusu", *zalogowany(*zmiana))),
         jresp(423, 200, '{"ok":true}')],
        # --- dodaj z formularza: id_zrodla generuje strona (dash-…), żeby odczytać nowy rekord
        [jresp(440, 400, '{"ok":false,"powod":"blad_danych"}',
               flt("Dodaj: błąd danych", *zalogowany(
                   [dodaj, missing(n["tytul"])], [dodaj, nomatch(n["id_zrodla"], PD)],
                   [dodaj, nomatch(n["rodzaj"], RODZAJ_PAT)], [dodaj, nomatch(n["kategoria"], KATEGORIA_PAT)],
                   [dodaj, {"a": n["termin"], "o": "date:lessorequal", "b": "{{now}}"}])))],
        # dodaj z formularza: zapis od razu (identyfikator dash-… jest unikalny, nie trzeba sprawdzać duplikatu)
        [at_create(441, "Zadania", rekord_zadania(n, "Dashboard"),
                   flt("Dodaj: dane OK", *zalogowany([dodaj, exists(n["tytul"]), match(n["id_zrodla"], PD),
                                                      match(n["rodzaj"], RODZAJ_PAT), match(n["kategoria"], KATEGORIA_PAT),
                                                      {"a": n["termin"], "o": "date:greater", "b": "{{now}}"}]))),
         jresp(444, 200, '{"ok":true,"id":"{{441.id}}"}')],
        [jresp(430, 400, '{"ok":false,"powod":"nieznana_akcja"}',
               flt("Nieznana akcja", *zalogowany([ne(q["akcja"], "lista"), ne(q["akcja"], "dodaj"),
                                                  *[ne(q["akcja"], a) for a in STATUS_AKCJE]])))],
    ]


def s3_routes(cel_eq):
    """S3 – przypomnienie dzień przed terminem. GitHub Actions wywołuje je raz dziennie rano
    (POST ?cel=przypomnienia z X-Api-Key), bo darmowy plan Make pozwala tylko na 2 aktywne scenariusze.

    Sprawa przypisana → mail do przypisanej osoby; sprawa wolna → mail do rodziców z powiadomieniami
    „Wszystkie”. W mailu jest tylko przycisk do listy spraw – akcje robi się na dashboardzie.
    """
    cel = cel_eq("przypomnienia")
    z = Zadanie(521, prefix="fields")
    z_id = "{{521.id}}"
    osoba = "{{521.fields." + F("Zadania", "Osoba") + "[1]}}"
    rp = Rodzic(524, single=True)          # przypisana osoba
    mail_jutro = template("jutro.html", stopka_kto=f"Sprawę masz Ty – {rp['Imię']}", **z.mail_vars())
    rw = Rodzic(527, single=True)          # rodzic z pełnymi powiadomieniami (sprawa wolna)
    rw.base = "527"
    mail_wolne = template("przypomnienie.html", stopka_kto="Nikt jeszcze nie wziął tej sprawy.", dopisek_pilne="",
                          **z.mail_vars())
    formula = ("AND(OR({Status}='Nowe', {Status}='Przypisane'), {Termin jutro}, "
               "NOT({Przypomnienie przed terminem}))")
    klucz_ok = eq(API_KEY, env("S1W_API_KEY"))
    return [
        [jresp(500, 401, '{"ok":false}', flt("S3: zły klucz", [cel, ne(API_KEY, env("S1W_API_KEY"))]))],
        # bez modułu odpowiedzi – Make sam odpowie GitHub Actions „Accepted” (o 1 operację mniej)
        [at_find(520, "Zadania", formula, flt("S3: start", [cel, klucz_ok])),
         feeder(521, "{{520.body.records}}"),
         at_update(522, "Zadania", z_id, {
             F("Zadania", "Przypomnienie przed terminem"): True,
             F("Zadania", "Liczba przypomnień"): "{{ifempty(521.fields." + F("Zadania", "Liczba przypomnień") + "; 0) + 1}}",
             F("Zadania", "Ostatnie przypomnienie"): "{{now}}"}),
         router(
             523,
             [at_get(524, "Rodzice", osoba, flt("Przypisana", [exists(osoba)])),
              gmail(525, rp["Email"], f"Jutro: {z['Tytuł']}{z['Kategoria dopisek']}", mail_jutro)],
             [at_find(526, "Rodzice", f"AND({{Aktywny}}, {DO_WSZYSTKICH})", flt("Wolna", [missing(osoba)])),
              feeder(527, "{{526.body.records}}"),
              gmail(528, rw["Email"], f"Jutro: {z['Tytuł']}{z['Kategoria dopisek']} – nikt jeszcze nie wziął", mail_wolne)],
         )],
    ]


def scenariusz_api():
    """Jeden webhook dla wszystkiego, co przychodzi z zewnątrz (?cel=…):
    brak celu – stary link z maila (strona z odnośnikiem), dodaj – S1-W, api – dashboard (S5),
    przypomnienia – S3."""
    def cel_eq(c):
        return eq("{{1.cel}}", c)

    return {"name": "Asystent – API (maile, webhook, dashboard, przypomnienia)",
            "flow": [webhook(1, "S2_HOOK_ID"),
                     router(2, *stare_linki_routes(missing("{{1.cel}}")), *s1w_routes(cel_eq),
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
