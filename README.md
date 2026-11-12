# Kto to ogarnia – domowe sprawy z właścicielem

[![Testy](https://github.com/pogodae/asystent-szkolny/actions/workflows/testy.yml/badge.svg)](https://github.com/pogodae/asystent-szkolny/actions/workflows/testy.yml)

**Demo:** [pogodae.github.io/asystent-szkolny/?demo=1](https://pogodae.github.io/asystent-szkolny/?demo=1) – przykładowe dane, bez logowania.

Sprawy dzieci i domu (zgody, wpłaty, zebrania w szkole i przedszkolu, rachunki, wizyty) giną między dwojgiem rodziców, bo każde zakłada, że drugie się tym zajmie. Asystent zamienia każdą sprawę w **zadanie z właścicielem**: nowa sprawa należy do jednej osoby, która może ją oznaczyć jako zrobioną albo przekazać drugiej (ta dostaje wtedy maila), a dzień przed terminem właściciel dostaje przypomnienie.

To ten sam mechanizm, który działa w obsłudze zgłoszeń, rekrutacji czy sprzedaży:

| W domu | W firmie |
| --- | --- |
| sprawa ze szkoły lub domu | zgłoszenie, kandydat, lead |
| wiadomość z dziennika, zdanie do Claude, formularz | formularz na stronie, portal z ogłoszeniami, mail, CRM |
| przekazanie drugiemu rodzicowi z mailem | przypisanie rekrutera lub handlowca z powiadomieniem |
| przypomnienie dzień przed terminem | follow-up, przypomnienie o rozmowie lub ofercie |
| deduplikacja po `id_zrodla` | ten sam kandydat lub lead z dwóch źródeł |

## Dla rekrutera

**Jaki problem rozwiązuje?** Sprawy dzieci i domu nie mają właściciela, więc umykają terminy i nikt nie wie, kto się czymś zajmuje. Każda sprawa ma tu jedną osobę odpowiedzialną, termin i status. Sprawę można dodać na trzy sposoby: zdaniem w Claude, formularzem albo webhookiem z innego systemu.

**Za co odpowiadałam?** Za całość: analizę potrzeb i specyfikację ([SPEC.md](SPEC.md)), model danych w Airtable, oba scenariusze Make, API dla dashboardu, maile, dashboard, Apps Script, testy i wdrożenie (GitHub Pages, GitHub Actions). Projekt działa w moim domu na prawdziwych danych.

**Technologie:** Make (webhook, router, podscenariusz, kolejka), Airtable (REST API, formuły), Python (generator blueprintów, wdrażanie przez API Make, testy), JavaScript (dashboard bez frameworka), Google Apps Script, Gmail, GitHub Pages i Actions. W integracjach: webhooki, JSON, uwierzytelnianie kluczem API (`X-Api-Key`) i parą klucz + hasło, CORS, deduplikacja, walidacja danych wejściowych.

**Jak korzystałam z AI?**
- *W produkcie:* Claude przez konektor Make zamienia zdanie „dodaj: zebranie w czwartek 17:00” na wywołanie Silnika z polami `tytul`, `termin` (ISO 8601), `rodzaj` i `kategoria`. Opisy pól w interfejsie scenariusza są jednocześnie instrukcją dla modelu. Dane od modelu przechodzą tę samą walidację co z każdego innego źródła.
- *Przy budowie:* Claude Code był moim asystentem programowania. Najpierw napisałam specyfikację z planem testów, a potem budowałam małymi krokami: scenariusz, test, poprawka. Scenariusze Make są opisane w Pythonie ([make/build.py](make/build.py)), więc każdą zmianę od AI widzę jako diff w kodzie, a nie jako klikanie w edytorze.
- *Weryfikacja:* kodu od AI nie przyjmowałam na słowo. Kilka założeń z pierwszej wersji okazało się błędnych dopiero w testach na żywo. Na przykład sekwencyjny webhook w Make odpowiada od razu `Accepted`, a podscenariusz utworzony przez API nie zwraca wyjść. Opisałam to w [docs/decyzje.md](docs/decyzje.md).

**Jak testowałam i jaki był efekt?**
- [tests/test_build.py](tests/test_build.py) – testy offline w GitHub Actions. Sprawdzają m.in., że do publicznej wersji nie wyciekają sekrety ani imiona, że każde pole z zewnątrz jest sprawdzone wyrażeniem regularnym, zanim trafi do formuły Airtable, i że każda trasa webhooka zwraca odpowiedź. Test na wstrzyknięcie formuły znalazł prawdziwą lukę: brak walidacji pola `dla` w Silniku.
- [tests/smoke_test.py](tests/smoke_test.py) – test na żywo prawdziwego webhooka i Airtable: brak klucza API, dane z przeszłości, próba wstrzyknięcia, duplikaty, dodaj, przekaż, zrobione, usuń.
- Ręcznie: dwa jednoczesne kliknięcia (kolejka Silnika dała jedną zmianę zamiast dwóch), maile w Gmailu, dashboard na telefonie.
- Efekt: dwa scenariusze zamiast siedmiu z pierwszej specyfikacji, bo darmowy plan Make pozwala na 2 aktywne scenariusze. Odczyt listy na dashboardzie nie zużywa operacji Make (Apps Script), a akcja kosztuje 3–6 operacji, więc system mieści się w ok. 1000 operacji miesięcznie darmowego planu ([budżet operacji](docs/architektura.md#budżet-operacji)).

## Jak to działa

1. Sprawę dodajesz przyciskiem **+ Dodaj** na dashboardzie, zdaniem „dodaj: wycieczka do Krakowa 14.11, 40 zł i zgoda” w Claude (konektor Make) albo webhookiem S1-W (np. z przyszłego scrapera dziennika szkolnego).
2. Rano dzień przed terminem przychodzi jeden mail z przypomnieniem do właściciela sprawy. Druga osoba dostaje też maila od razu, gdy ktoś przekaże jej sprawę. W mailu jest tylko przycisk **Otwórz listę spraw** – akcje (Zrobione, przekazanie) robi się na dashboardzie.
3. Innych maili nie ma – to oszczędza limit operacji darmowego planu Make (szczegóły: [docs/architektura.md](docs/architektura.md#budżet-operacji)).
4. Dashboard **„Kto to ogarnia”** pokazuje moje sprawy (osobno wydarzenia z godziną i zadania), sprawy drugiej osoby i ostatnio zrobione, z filtrem kategorii. Strona główna to wizytówka z opisem, **wersją demo** (`?demo=1`) i logowaniem dla domowników.

Szczegóły: [docs/architektura.md](docs/architektura.md) · decyzje: [docs/decyzje.md](docs/decyzje.md) · specyfikacja: [SPEC.md](SPEC.md)

## Stos

- **Airtable** – jedyne źródło stanu (`Zadania`, `Rodzice`, `Zdarzenia`) z formułami pomocniczymi.
- **Make** – 2 scenariusze: *Silnik* (zmiany stanu, kolejka) i *API* (jeden webhook dla S1-W, dashboardu i przypomnień).
- **Python** – generator blueprintów Make, wdrażanie przez API Make, konfiguracja Airtable, testy.
- **Gmail** – maile HTML ([templates/](templates/)).
- **GitHub Pages** – dashboard w jednym pliku HTML ([dashboard/index.html](dashboard/index.html)).
- **Google Apps Script** – odczyt listy dla dashboardu bez operacji Make ([apps-script/](apps-script/README.md)).
- **GitHub Actions** – harmonogram przypomnień ([przypomnienia.yml](.github/workflows/przypomnienia.yml)) i testy ([testy.yml](.github/workflows/testy.yml)).

## Struktura

| Ścieżka | Zawartość |
| --- | --- |
| `airtable/setup_base.py` | tworzy tabele, pola, formuły (idempotentnie) |
| `airtable/seed_rodzice.py` | rodzice z `.env`, klucze dostępu do dashboardu |
| `make/build.py` | scenariusze Make opisane w Pythonie, generator blueprintów |
| `make/deploy.py` | wgrywa blueprinty przez API Make |
| `make/silnik.json`, `make/api.json` | publiczne blueprinty: sekrety jako znaczniki `__NAZWA__`, przykładowe imiona i kategorie |
| `templates/` | maile (przypomnienie, „jutro”, przypisanie) i strona dla starych linków |
| `tests/test_build.py` | testy offline generatora (uruchamiane w GitHub Actions) |
| `tests/smoke_test.py` | testy na żywo: webhook Make + Airtable |

Prawdziwe imiona domowników i kategorie są tylko w `.env`, w Airtable i w Apps Script. Repozytorium i kod strony zawierają przykładowe dane ([dlaczego i jak](docs/decyzje.md#prywatne-dane-poza-repozytorium)).

## Uruchomienie od zera

```bash
pip install -r requirements.txt
cp .env.example .env          # uzupełnij Airtable, rodziców, kategorie, MAKE_API_TOKEN, połączenia Make
python airtable/setup_base.py
python airtable/seed_rodzice.py
python make/deploy.py silnik api --activate
python -m unittest discover -s tests -t .   # testy offline
python tests/smoke_test.py                  # testy na żywo (~25 operacji Make)
```

## Dodawanie zadań

- **Dashboard:** przycisk **+ Dodaj** (tytuł, kategoria, rodzaj, dzień, godzina tylko dla wydarzeń, kwota, szczegóły) – dla osób, które nie używają Claude. Każda nowa sprawa należy do pierwszej osoby z `.env` (RODZIC1). Przycisk **→ imię** przekazuje ją drugiej osobie (dostaje maila), a **kosz** usuwa ją po potwierdzeniu: status „Anulowane”, sprawa znika z listy, ale zostaje w Airtable i można ją przywrócić, zmieniając status.
- **Claude:** zdanie „dodaj …” w projekcie Claude z włączonym konektorem Make (instrukcje niżej).
- **Webhook S1-W:** `POST ?cel=dodaj` z nagłówkiem `X-Api-Key` i JSON-em (`tytul`, `termin`, `rodzaj`, `kategoria`, `opis`, `kwota`, `id_zrodla`). Ten sam `id_zrodla` drugi raz zwraca `duplikat`, więc źródło może wysyłać sprawy wielokrotnie.

Każda sprawa ma **kategorię** (z `KATEGORIE` w `.env`, np. dzieci i *Dom*: kolorowy znacznik i filtr na dashboardzie, dopisek w temacie maila) oraz **rodzaj**: *Do dnia* (np. zgoda – „do 14 listopada”), *W dniu* (np. przynieść 20 zł – „sobota, 14 listopada”) albo *Wydarzenie* (np. zebranie – „sobota, 14 listopada, 17:00”). Godzina jest ustalana i wyświetlana tylko dla wydarzeń. Dla pozostałych system używa stałej godziny wyłącznie do przypomnień (W dniu: 7:30, Do dnia: 20:00).

**Powiadomienia** (pole w tabeli `Rodzice`): *Wszystkie* – przypomnienia dzień przed o swoich i wolnych sprawach; *Tylko przypisane* – przypomnienia o swoich sprawach i mail od razu, gdy ktoś przypisze sprawę.

Nie dodawaj zadań ręcznie w Airtable: taki rekord nie przejdzie walidacji ani nie dostanie właściciela.

### Instrukcje dla projektu Claude „Kto to ogarnia”

Wklej do instrukcji projektu w claude.ai (konektor Make musi być włączony). Kategorie wpisz takie jak w `KATEGORIE`:

```markdown
Gdy piszę „dodaj …”, dodajesz sprawę domową w Make: uruchom scenariusz
„Asystent – Silnik (dodaj i zmień status)” narzędziem do uruchamiania scenariuszy,
z danymi: akcja = "dodaj", tytul, kategoria, rodzaj, termin, opis, kwota, zrodlo = "Claude".

Kategoria – czego dotyczy sprawa:
- imię dziecka (np. "Szymon" lub "Michał") – sprawy dzieci (szkoła, przedszkole, lekarz, zajęcia).
- "Dom" – sprawy domowe (rachunki, naprawy, urzędy, zakupy).
Jeśli nie wiadomo, którego dziecka dotyczy sprawa, zapytaj.

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
- [x] Make: Silnik + API, walidacja danych wejściowych, deduplikacja, kolejka
- [x] Dashboard z trybem demo (`?demo=1`), logowaniem i konfiguracją z API
- [x] Publikacja na GitHub Pages, przypomnienia i testy w GitHub Actions
- [x] Kategorie, przekazywanie drugiej osobie, powiadomienia „Tylko przypisane”
- [x] Prywatne dane poza repozytorium (przykładowe dane w kodzie i w demo)
- [ ] Scraper dziennika szkolnego → AI wyciąga sprawy (termin, kwota, rodzaj) → webhook S1-W
- [ ] Nagranie demo
