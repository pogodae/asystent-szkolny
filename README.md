# Kto to ogarnia – domowe sprawy z właścicielem

[![Testy](https://github.com/pogodae/asystent-szkolny/actions/workflows/testy.yml/badge.svg)](https://github.com/pogodae/asystent-szkolny/actions/workflows/testy.yml)

**👉 [Zobacz demo](https://pogodae.github.io/asystent-szkolny/?demo=1)** – działa w przeglądarce, bez logowania, na przykładowych danych.

## Problem

Zgoda na wycieczkę, 20 zł na teatr, zebranie w przedszkolu, rachunek za prąd. W domu z dwojgiem rodziców takie sprawy łatwo giną, bo każde z nas zakłada, że drugie już się tym zajęło. O terminie przypominamy sobie wieczorem dzień po nim.

## Rozwiązanie

**Każda sprawa ma jedną osobę, która ją „ogarnia”.** Widać, co jest moje, co należy do drugiej osoby i co już jest zrobione.

- **Dodanie sprawy zajmuje kilka sekund:** wystarczy napisać zdanie do asystenta AI, np. *„dodaj: wycieczka do Krakowa w piątek, 40 zł i zgoda”*, albo wypełnić krótki formularz na stronie.
- **Jedno kliknięcie przekazuje sprawę** drugiej osobie, a ona od razu dostaje maila.
- **Dzień przed terminem rano** właściciel sprawy dostaje jedno przypomnienie. Bez zasypywania skrzynki.
- **Lista działa na telefonie.** Sprawy są podzielone na moje, drugiej osoby i zrobione, a kolory pokazują, czego dotyczą (dziecko albo dom).

System działa w moim domu na co dzień.

## Jak powstał

Zaprojektowałam i zbudowałam go samodzielnie: od rozpisania potrzeb i specyfikacji ([SPEC.md](SPEC.md)), przez bazę danych i automatyzacje, po stronę, maile i testy.

**Jak korzystałam z AI:**
- **W samym produkcie** asystent AI (Claude) rozumie zwykłe zdania i zamienia je na uporządkowaną sprawę z datą, kwotą i rodzajem terminu. Wie, że „do piątku” znaczy coś innego niż „w piątek o 17:00”, a gdy czegoś brakuje, dopytuje.
- **Przy budowie** pracowałam z Claude Code jak z asystentem programisty. Najpierw pisałam, co ma powstać i jak to sprawdzę, a potem budowałam małymi krokami. Nie przyjmowałam niczego na słowo: kilka pomysłów, które na papierze wyglądały dobrze, nie zadziałało w praktyce i trzeba było je przeprojektować ([decyzje](docs/decyzje.md)).

## Jak sprawdziłam, że działa

- **Automatyczne testy** uruchamiają się przy każdej zmianie w kodzie. Jeden z nich wykrył realną lukę bezpieczeństwa, zanim mogła komukolwiek zaszkodzić.
- **Testy na żywo** sprawdzają prawdziwy system: próby dodania sprawy bez uprawnień, z datą z przeszłości albo dwa razy tej samej.
- **Testy ręczne:** dwie osoby klikające tę samą sprawę w tej samej sekundzie, maile w skrzynce, strona na telefonie.

## Kilka technicznych niuansów

- **Mieści się w darmowych planach.** Narzędzie do automatyzacji (Make) pozwala za darmo na 2 scenariusze i ok. 1000 operacji miesięcznie. Pierwszy projekt zakładał 7 scenariuszy. Połączyłam je w 2, a odczyt listy przeniosłam do Google Apps Script, więc przeglądanie spraw nic nie kosztuje.
- **Dwa kliknięcia naraz nie robią bałaganu.** Zmiany trafiają do kolejki i są wykonywane po kolei, tak jak w systemach rezerwacji.
- **Ta sama sprawa nie pojawi się dwa razy.** Gdy przychodzi z innego systemu (np. z dziennika szkolnego), ma swój identyfikator i duplikat jest odrzucany.
- **Prywatność.** Kod i strona są publiczne, a system działa na prawdziwych danych mojej rodziny. Imiona domowników są więc tylko w bazie i w konfiguracji, a w kodzie i w demo są przykładowe. Pilnuje tego test, który zatrzymuje publikację, gdyby prawdziwe dane miały trafić do repozytorium.
- **Automatyzacje zapisane jako kod.** Scenariusze w Make zwykle się „wyklikuje”. Tutaj są opisane w Pythonie i wgrywane przez API Make, więc każdą zmianę widać w historii, da się ją przetestować i cofnąć.

**Narzędzia:** Make · Airtable · Python · JavaScript · Google Apps Script · Gmail · GitHub Pages i Actions · Claude / Claude Code

Więcej: [architektura](docs/architektura.md) · [decyzje projektowe](docs/decyzje.md) · [specyfikacja](SPEC.md)

## Szczegóły techniczne

### Stos

- **Airtable** – jedyne źródło stanu (`Zadania`, `Rodzice`, `Zdarzenia`) z formułami pomocniczymi.
- **Make** – 2 scenariusze: *Silnik* (zmiany stanu, kolejka) i *API* (jeden webhook dla S1-W, dashboardu i przypomnień).
- **Python** – generator blueprintów Make, wdrażanie przez API Make, konfiguracja Airtable, testy.
- **Gmail** – maile HTML ([templates/](templates/)).
- **GitHub Pages** – dashboard w jednym pliku HTML ([dashboard/index.html](dashboard/index.html)).
- **Google Apps Script** – odczyt listy dla dashboardu bez operacji Make ([apps-script/](apps-script/README.md)).
- **GitHub Actions** – harmonogram przypomnień ([przypomnienia.yml](.github/workflows/przypomnienia.yml)) i testy ([testy.yml](.github/workflows/testy.yml)).

### Struktura

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

### Dodawanie zadań

- **Dashboard:** przycisk **+ Dodaj** (tytuł, kategoria, rodzaj, dzień, godzina tylko dla wydarzeń, kwota, szczegóły) – dla osób, które nie używają Claude. Każda nowa sprawa należy do pierwszej osoby z `.env` (RODZIC1). Przycisk **→ imię** przekazuje ją drugiej osobie (dostaje maila), a **kosz** usuwa ją po potwierdzeniu: status „Anulowane”, sprawa znika z listy, ale zostaje w Airtable i można ją przywrócić, zmieniając status.
- **Claude:** zdanie „dodaj …” w projekcie Claude z włączonym konektorem Make (instrukcje niżej).
- **Webhook S1-W:** `POST ?cel=dodaj` z nagłówkiem `X-Api-Key` i JSON-em (`tytul`, `termin`, `rodzaj`, `kategoria`, `opis`, `kwota`, `id_zrodla`). Ten sam `id_zrodla` drugi raz zwraca `duplikat`, więc źródło może wysyłać sprawy wielokrotnie.

Każda sprawa ma **kategorię** (z `KATEGORIE` w `.env`, np. dzieci i *Dom*: kolorowy znacznik i filtr na dashboardzie, dopisek w temacie maila) oraz **rodzaj**: *Do dnia* (np. zgoda – „do 14 listopada”), *W dniu* (np. przynieść 20 zł – „sobota, 14 listopada”) albo *Wydarzenie* (np. zebranie – „sobota, 14 listopada, 17:00”). Godzina jest ustalana i wyświetlana tylko dla wydarzeń. Dla pozostałych system używa stałej godziny wyłącznie do przypomnień (W dniu: 7:30, Do dnia: 20:00).

**Powiadomienia** (pole w tabeli `Rodzice`): *Wszystkie* – przypomnienia dzień przed o swoich i wolnych sprawach; *Tylko przypisane* – przypomnienia o swoich sprawach i mail od razu, gdy ktoś przypisze sprawę.

Nie dodawaj zadań ręcznie w Airtable: taki rekord nie przejdzie walidacji ani nie dostanie właściciela.

#### Instrukcje dla projektu Claude „Kto to ogarnia”

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

### Status

- [x] Airtable: schemat, rodzice, formuły
- [x] Make: Silnik + API, walidacja danych wejściowych, deduplikacja, kolejka
- [x] Dashboard z trybem demo (`?demo=1`), logowaniem i konfiguracją z API
- [x] Publikacja na GitHub Pages, przypomnienia i testy w GitHub Actions
- [x] Kategorie, przekazywanie drugiej osobie, powiadomienia „Tylko przypisane”
- [x] Prywatne dane poza repozytorium (przykładowe dane w kodzie i w demo)
- [ ] Scraper dziennika szkolnego → AI wyciąga sprawy (termin, kwota, rodzaj) → webhook S1-W
- [ ] Nagranie demo
