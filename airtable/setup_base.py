"""Tworzy tabele Rodzice, Zadania i Zdarzenia w pustej bazie Airtable.

Skrypt jest idempotentny: istniejące tabele i pola pomija, brakujące dopisuje.
Na końcu odczytuje schemat i wypisuje, czego API nie potrafi zrobić
(widoki, limit jednej osoby w polu Osoba) – to klikasz ręcznie.

Użycie:  python airtable/setup_base.py
"""
import sys

from common import Airtable, load_env, require

TZ = "Europe/Warsaw"
DATETIME = {
    "type": "dateTime",
    "options": {"dateFormat": {"name": "european"}, "timeFormat": {"name": "24hour"}, "timeZone": TZ},
}
CHECKBOX = {"type": "checkbox", "options": {"icon": "check", "color": "greenBright"}}


def select(*names):
    return {"type": "singleSelect", "options": {"choices": [{"name": n} for n in names]}}


def link(table_id):
    return {"type": "multipleRecordLinks", "options": {"linkedTableId": table_id}}


STATUSY = ("Nowe", "Przypisane", "Zrobione", "Anulowane")
ZRODLA = ("Claude", "Webhook", "Scraper", "Dashboard")
TYPY_ZDARZEN = ("Utworzono", "Przypisano", "Zrobione", "Przypomnienie", "Eskalacja",
                "Odrzucone kliknięcie", "Błąd", "Oddano")


def rodzice_fields():
    return [
        {"name": "Imię", "type": "singleLineText"},
        {"name": "Klucz", "type": "singleLineText", "description": "krótki, unikalny, trafia do linków w mailach"},
        {"name": "Email", "type": "email"},
        {"name": "Aktywny", **CHECKBOX},
        {"name": "Klucz dostępu", "type": "singleLineText", "description": "sekret do dashboardu (?u=&s=)"},
    ]


def zadania_fields(rodzice_id):
    return [
        {"name": "Tytuł", "type": "singleLineText"},
        {"name": "Opis", "type": "multilineText"},
        {"name": "Termin", **DATETIME},
        {"name": "Kwota", "type": "currency", "options": {"precision": 2, "symbol": "zł"}},
        {"name": "Status", **select(*STATUSY)},
        {"name": "Osoba", **link(rodzice_id), "description": "max 1 osoba"},
        {"name": "Przypisano", **DATETIME},
        {"name": "Zrobiono", **DATETIME},
        {"name": "Token", "type": "singleLineText", "description": "losowy UUID, zabezpiecza linki w mailach"},
        {"name": "Źródło", **select(*ZRODLA)},
        {"name": "ID źródła", "type": "singleLineText"},
        {"name": "Liczba przypomnień", "type": "number", "options": {"precision": 0}},
        {"name": "Ostatnie przypomnienie", **DATETIME},
        {"name": "Przypomnienie przed terminem", **CHECKBOX},
        {"name": "Po terminie", **CHECKBOX},
    ]


def zdarzenia_fields(zadania_id, rodzice_id):
    return [
        {"name": "Opis", "type": "singleLineText"},
        {"name": "Zadanie", **link(zadania_id)},
        {"name": "Typ", **select(*TYPY_ZDARZEN)},
        {"name": "Kto", **link(rodzice_id)},
    ]


# Pola wyliczane: API przyjmuje je tylko przez endpoint pól, już po utworzeniu tabeli.
# createdTime musi iść bez opcji – format wyświetlania można zmienić ręcznie.
CREATED = {"type": "createdTime"}


def formula(expr):
    return {"type": "formula", "options": {"formula": expr}}


WYLICZANE = {
    "Zadania": [
        {"name": "Utworzono", **CREATED},
        {"name": "Godzin do terminu", **formula("DATETIME_DIFF({Termin}, NOW(), 'hours')")},
        {"name": "Czas do przypisania (h)",
         **formula("IF({Przypisano}, DATETIME_DIFF({Przypisano}, {Utworzono}, 'minutes')/60)")},
        # pomocnicze dla Make: gotowe teksty do maili i stron
        {"name": "Osoba imię", **formula("{Osoba} & ''")},
        {"name": "Termin tekst", **formula(
            "DATETIME_FORMAT(SET_LOCALE(SET_TIMEZONE({Termin}, 'Europe/Warsaw'), 'pl'), 'D MMMM YYYY, HH:mm')")},
        {"name": "Termin krótko", **formula(
            "DATETIME_FORMAT(SET_LOCALE(SET_TIMEZONE({Termin}, 'Europe/Warsaw'), 'pl'), 'D.MM HH:mm')")},
        {"name": "Kwota tekst", **formula("IF({Kwota}, {Kwota} & ' zł', '')")},
        {"name": "Kwota linia", **formula("IF({Kwota}, 'Kwota: ' & {Kwota} & ' zł', '')")},
        {"name": "Dopisek pilne", **formula(
            "IF(OR({Liczba przypomnień} >= 2, {Godzin do terminu} < 24), ' – PILNE', '')")},    ],
    "Zdarzenia": [
        {"name": "Kiedy", **CREATED},
    ],
}

WIDOKI = [
    "Zadania › Otwarte: filtr Status nie jest Zrobione ani Anulowane; sortuj Termin rosnąco",
    "Zadania › Nieprzypisane: filtr Status = Nowe; sortuj Termin rosnąco",
    "Zadania › Po terminie: filtr Status = Nowe lub Przypisane, Termin przed teraz",
    "Zadania › Zrobione w tym tygodniu: filtr Status = Zrobione, Zrobiono w tym tygodniu",
]


def ensure_table(at, existing, name, fields):
    """Zwraca id tabeli; tworzy ją lub dopisuje brakujące pola (także wyliczane)."""
    if name in existing:
        table = existing[name]
        print(f"= tabela {name} istnieje ({table['id']})")
    else:
        table = at.create_table(name, fields)
        print(f"+ tabela {name} ({table['id']})")
    have = {f["name"] for f in table["fields"]}
    for f in fields + WYLICZANE.get(name, []):
        if f["name"] not in have:
            at.create_field(table["id"], f)
            print(f"  + pole {name}.{f['name']}")
    return table["id"]


def main():
    load_env()
    token, base = require("AIRTABLE_TOKEN", "AIRTABLE_BASE_ID")
    at = Airtable(token, base)

    existing = {t["name"]: t for t in at.tables()}
    rodzice_id = ensure_table(at, existing, "Rodzice", rodzice_fields())
    zadania_id = ensure_table(at, existing, "Zadania", zadania_fields(rodzice_id))
    ensure_table(at, existing, "Zdarzenia", zdarzenia_fields(zadania_id, rodzice_id))

    # weryfikacja odczytem
    tables = {t["name"]: t for t in at.tables()}
    print("\nSchemat po zmianach:")
    ok = True
    for name in ("Rodzice", "Zadania", "Zdarzenia"):
        t = tables[name]
        names = [f["name"] for f in t["fields"]]
        print(f"  {name} [{t['id']}]: {', '.join(names)}")
        expected = {
            "Rodzice": rodzice_fields(),
            "Zadania": zadania_fields(rodzice_id),
            "Zdarzenia": zdarzenia_fields(zadania_id, rodzice_id),
        }[name] + WYLICZANE.get(name, [])
        missing = [f["name"] for f in expected if f["name"] not in names]
        if missing:
            ok = False
            print(f"    BRAK: {missing}")

    print("\nKroki ręczne (API Airtable tego nie robi):")
    print("  - Zadania.Osoba: w ustawieniach pola wyłącz 'Allow linking to multiple records'")
    print("  - Widoki:")
    for w in WIDOKI:
        print(f"      {w}")
    print("  - Pole Opis w Zdarzenia to nazwa primary; reverse-linki w Rodzice/Zadania możesz ukryć")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
