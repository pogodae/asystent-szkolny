# Kto to ogarnia – domowe sprawy z właścicielem

Sprawy dzieci i domu (zgody, wpłaty, zebrania w szkole i przedszkolu, rachunki, wizyty) giną między dwojgiem rodziców, bo każde zakłada, że drugie się tym zajmie. Asystent zamienia każdą sprawę w **zadanie z właścicielem**: mail trafia do obojga, jedno klika **Biorę to**, a system przypomina, dopóki sprawa nie jest przypisana i zrobiona. To ten sam mechanizm co w procesie rekrutacyjnym: zgłoszenie, przypisanie osoby, przypomnienie, status.

## Jak to działa

1. Zadanie dodajesz przyciskiem **+ Dodaj** na dashboardzie, zdaniem „dodaj: wycieczka do Krakowa 14.11, 40 zł i zgoda” w Claude (konektor Make) albo webhookiem (pod przyszły scraper MobiDziennika).
2. Rodzice z pełnymi powiadomieniami dostają mail z przyciskami **Biorę to** i **Zrobione** (osoba z ustawieniem „Tylko przypisane” dostaje maile tylko o sprawach przypisanych do niej). Link najpierw pokazuje stronę potwierdzenia (GET), a zmiana następuje dopiero po kliknięciu na tej stronie (POST), więc skaner linków w poczcie niczego nie przypisze.
3. Nieprzypisane zadanie wraca co 4 h (z dopiskiem PILNE), osoba przypisana dostaje przypomnienie wieczór przed terminem, a po terminie przychodzi eskalacja.
4. Dashboard **„Kto to ogarnia”** pokazuje wolne i przypisane sprawy oraz liczniki, a tabela `Zdarzenia` pozwala policzyć czas do przypisania.

Szczegóły: [docs/architektura.md](docs/architektura.md) · decyzje: [docs/decyzje.md](docs/decyzje.md) · specyfikacja: [SPEC.md](SPEC.md)

## Stos

- **Airtable** – jedyne źródło stanu (`Zadania`, `Rodzice`, `Zdarzenia`) z formułami pomocniczymi.
- **Make** – 2 scenariusze: *Silnik* (zmiany stanu, kolejka) i *API* (jeden webhook dla maili, S1-W, dashboardu i przypomnień).
- **Gmail** – maile HTML z przyciskami ([templates/](templates/)).
- **GitHub Pages** – dashboard w jednym pliku HTML ([dashboard/index.html](dashboard/index.html)).
- **GitHub Actions** – harmonogram przypomnień ([.github/workflows/przypomnienia.yml](.github/workflows/przypomnienia.yml)).

## Struktura

| Ścieżka | Zawartość |
| --- | --- |
| `airtable/setup_base.py` | tworzy tabele, pola, formuły (idempotentnie) |
| `airtable/seed_rodzice.py` | rodzice z `.env`, klucze dostępu do dashboardu |
| `make/build.py` | scenariusze Make opisane w Pythonie, generator blueprintów |
| `make/deploy.py` | wgrywa blueprinty przez API Make i eksportuje stan do `make/*.json` |
| `make/silnik.json`, `make/api.json` | aktualne blueprinty (sekrety zastąpione znacznikami `__NAZWA__`) |
| `templates/` | maile i strony odpowiedzi S2 |
| `tests/smoke_test.py` | automatyczne testy z planu testów |

## Uruchomienie od zera

```bash
pip install -r requirements.txt
cp .env.example .env          # uzupełnij Airtable, rodziców, MAKE_API_TOKEN, połączenia Make
python airtable/setup_base.py
python airtable/seed_rodzice.py
python make/deploy.py silnik api --activate
python tests/smoke_test.py
```

## Dodawanie zadań

- **Dashboard:** przycisk **+ Dodaj** (tytuł, kategoria, rodzaj, dzień, godzina tylko dla wydarzeń, kwota, szczegóły). Dla osób, które nie używają Claude. Przycisk **→ Dawid** na karcie przypisuje sprawę drugiej osobie (dostaje maila).

Każda sprawa ma **kategorię**: *Dominik*, *Mateusz* albo *Dom* (kolorowy znacznik i filtr na dashboardzie, dopisek w temacie maila) oraz **rodzaj**: *Do dnia* (np. zgoda – „do 14 listopada”), *W dniu* (np. przynieść 20 zł – „sobota, 14 listopada”) albo *Wydarzenie* (np. zebranie – „sobota, 14 listopada, 17:00”). Godzina jest ustalana i wyświetlana tylko dla wydarzeń; dla pozostałych system używa stałej godziny wyłącznie do przypomnień (W dniu: 7:30, Do dnia: 20:00).

**Powiadomienia** (pole w tabeli `Rodzice`): *Wszystkie* – każdy mail; *Tylko przypisane* – tylko maile o sprawach przypisanych do tej osoby (przypisanie, „jutro”, po terminie).
- **Claude:** zdanie „dodaj …” w projekcie „Kto to ogarnia” z włączonym konektorem Make.
- **Webhook S1-W:** `POST ?cel=dodaj` z nagłówkiem `X-Api-Key` (np. przyszły scraper MobiDziennika).

Nie dodawaj zadań ręcznie w Airtable: taki rekord nie ma tokenu ani maili.

### Instrukcje dla projektu Claude „Kto to ogarnia”

Wklej do instrukcji projektu w claude.ai (konektor Make musi być włączony):

```markdown
Gdy piszę „dodaj …”, dodajesz sprawę domową w Make: uruchom scenariusz
„Asystent – Silnik (dodaj i zmień status)” (ID 10071371) narzędziem do uruchamiania scenariuszy,
z danymi: akcja = "dodaj", tytul, kategoria, rodzaj, termin, opis, kwota, zrodlo = "Claude".

Kategoria – czego dotyczy sprawa:
- "Dominik" lub "Mateusz" – sprawy synów (szkoła, przedszkole, lekarz, zajęcia).
- "Dom" – sprawy domowe (rachunki, naprawy, urzędy, zakupy).
Jeśli nie wiadomo, którego syna dotyczy sprawa, zapytaj.

Rodzaj i termin (strefa Europe/Warsaw, ISO 8601 z przesunięciem: zimą +01:00, latem +02:00):
- "Do dnia" – trzeba zrobić najpóźniej tego dnia (oddać zgodę, zapłacić, „do piątku”). Godziny nie ustalasz,
  termin = ten dzień o 20:00, np. 2026-11-14T20:00:00+01:00.
- "W dniu" – dotyczy konkretnego dnia (przynieść 20 zł, strój na WF, wycieczka). Godziny nie ustalasz,
  termin = ten dzień o 07:30.
- "Wydarzenie" – coś o konkretnej godzinie (zebranie, występ, wizyta). Godzina jest wymagana –
  jeśli jej nie podałam, zapytaj.
Daty względne („w czwartek”, „jutro”) liczysz od dzisiejszej daty. Gdy nie wiesz, który to rodzaj
albo data jest niejednoznaczna, zapytaj jednym krótkim pytaniem, zanim uruchomisz scenariusz.

- tytul krótki (do 60 znaków), szczegóły i rzeczy do przyniesienia w opis, kwotę w PLN w kwota (liczba).
- Kilka spraw w jednej wiadomości = osobne uruchomienia.
- Po uruchomieniu odpowiedz jedną linią: co dodałeś, dla kogo i na kiedy – godzinę podawaj tylko dla wydarzeń.
  Gdy uruchomienie się nie powiedzie, powiedz to wprost.
```

## Status

- [x] Airtable: schemat, rodzice, formuły
- [x] Make: Silnik + API, testy 2–5, 8–14 automatycznie, 6–7 i 9–11 sprawdzone na żywo
- [x] Dashboard (tryb demo: `?demo=1`)
- [x] Publikacja na GitHub Pages i sekrety dla GitHub Actions
- [x] Kategorie (Dominik, Mateusz, Dom), przypisywanie drugiej osobie, powiadomienia „Tylko przypisane”
- [ ] Test 1 („dodaj” w Claude), zrzuty ekranu, nagranie demo
