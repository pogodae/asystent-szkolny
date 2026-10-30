# Asystent szkolny – moduł zadań

Sprawy ze szkoły (wycieczki, zgody, wpłaty, zebrania) giną między dwojgiem rodziców, bo każde zakłada, że drugie się tym zajmie. Asystent zamienia każdą sprawę w **zadanie z właścicielem**: mail trafia do obojga, jedno klika **Biorę to**, a system przypomina, dopóki sprawa nie jest przypisana i zrobiona. To ten sam mechanizm co w procesie rekrutacyjnym: zgłoszenie, przypisanie osoby, przypomnienie, status.

## Jak to działa

1. Zadanie dodajesz zdaniem „dodaj: wycieczka do Krakowa 14.11, 40 zł i zgoda” w Claude (konektor Make) albo webhookiem (pod przyszły scraper MobiDziennika).
2. Oboje rodzice dostają mail z przyciskami **Biorę to** i **Zrobione**. Link najpierw pokazuje stronę potwierdzenia (GET), a zmiana następuje dopiero po kliknięciu na tej stronie (POST), więc skaner linków w poczcie niczego nie przypisze.
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

## Instrukcje dla projektu Claude „Asystent szkolny”

```markdown
Gdy piszę „dodaj …”, dodajesz sprawy szkolne scenariuszem Make „Asystent – Silnik” z akcja=dodaj.
- Strefa czasowa: Europe/Warsaw. Daty względne („w czwartek”, „jutro”) liczysz od dzisiejszej daty.
- Brak godziny: wycieczki i przyniesienie czegoś = 07:30, zebrania bez godziny = zapytaj.
- Data niejednoznaczna: zapytaj jednym krótkim pytaniem, zanim uruchomisz scenariusz.
- tytul krótki (do 60 znaków), szczegóły i rzeczy do przyniesienia w opis, kwotę w PLN w kwota.
- Kilka spraw w jednej wiadomości = osobne wywołania.
- Po wywołaniu odpowiedz jedną linią: co dodałeś i na kiedy.
```

## Status

- [x] Airtable: schemat, rodzice, formuły
- [x] Make: Silnik + API, testy 2–5, 8–14 automatycznie, 6–7 i 9–11 sprawdzone na żywo
- [x] Dashboard (tryb demo: `?demo=1`)
- [ ] Publikacja na GitHub Pages i sekrety dla GitHub Actions
- [ ] Test 1 („dodaj” w Claude), zrzuty ekranu, nagranie demo
