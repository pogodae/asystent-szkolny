# Asystent szkolny – moduł zadań

Oct 27, 2026 · @Ewa

## Cel i zakres

V1 zamienia szkolne sprawy w zadania z właścicielem: każde zadanie trafia mailem do obojga rodziców, jedno klika „Biorę to”, a system przypomina, dopóki sprawa nie jest przypisana i zrobiona. To ten sam mechanizm co w procesie rekrutacyjnym: zgłoszenie, przypisanie osoby, przypomnienie, status.

**W zakresie v1**

- Dodawanie zadań komendą „dodaj …” w Claude (przez konektor Make) oraz przez webhook (pod przyszły scraper).
- Baza zadań, rodziców i dziennika zdarzeń w Airtable oraz dashboard, na którym widać wolne i przypisane zadania i można je przejąć.
- Mail do obojga rodziców z przyciskami „Biorę to” i „Zrobione”.
- Przypisanie z ochroną przed podwójnym kliknięciem i przed kliknięciem przez skaner linków.
- Przypomnienia: nieprzypisane zadanie wraca, przypisane przypomina się wieczór przed terminem, po terminie jest eskalacja.

**Poza zakresem v1** (roadmapa na końcu): wyciąganie zadań z wiadomości MobiDziennika przez AI, Google Calendar, WhatsApp, podsumowanie tygodnia.

**Jak użyć z Claude Code:** wklej cały dokument jako `SPEC.md` do pustego repozytorium i poproś: „Przeczytaj SPEC.md i zbuduj projekt zgodnie z sekcją Kolejność budowy. Pytaj mnie o sekrety, nie zgaduj ich.”

## Architektura

Cztery wejścia prowadzą do scenariuszy Make, a jedynym miejscem, gdzie żyje stan zadań, jest Airtable.

&#91;embedded content: architektura v1 · 4 wejścia, 4 scenariusze Make, Airtable i Gmail\]

S2 i S5 zmieniają status przez wspólny podscenariusz „Zmień status”, więc mail i dashboard stosują te same reguły. S3 nie ma wejścia z zewnątrz, uruchamia go harmonogram.

## Airtable: baza „Asystent szkolny”

Trzy tabele: `Zadania`, `Rodzice`, `Zdarzenia`. Strefa czasowa bazy i wszystkich pól daty: Europe/Warsaw. Pustą bazę zakładasz ręcznie, tabele tworzy skrypt przez Airtable Web API (endpoint meta tables).

**Tabela `Rodzice`**

| Pole | Typ | Uwagi |
| --- | --- | --- |
| Imię | single line text (primary) | np. Ewa |
| Klucz | single line text | krótki, unikalny: `ewa`, `tomek`; trafia do linków w mailach |
| Email | email | adres powiadomień |
| Aktywny | checkbox | tylko aktywni dostają maile |

**Tabela `Zadania`**

| Pole | Typ | Uwagi |
| --- | --- | --- |
| Tytuł | single line text (primary) | krótko, np. „Wycieczka do Krakowa” |
| Opis | long text | szczegóły, co przynieść |
| Termin | date + time, 24h | wymagany |
| Kwota | currency PLN | opcjonalna |
| Status | single select | `Nowe`, `Przypisane`, `Zrobione`, `Anulowane` |
| Osoba | link do `Rodzice`, max 1 | kto bierze |
| Przypisano | date + time | ustawia S2 |
| Zrobiono | date + time | ustawia S2 |
| Token | single line text | losowy UUID, zabezpiecza linki w mailach |
| Źródło | single select | `Claude`, `Webhook`, `Scraper` |
| ID źródła | single line text | do deduplikacji, np. ID wiadomości z MobiDziennika |
| Liczba przypomnień | number, integer | domyślnie 0 |
| Ostatnie przypomnienie | date + time | ustawia S3 |
| Przypomnienie przed terminem | checkbox | wieczór przed terminem wysłane |
| Po terminie | checkbox | eskalacja wysłana |
| Utworzono | created time | automatycznie |
| Godzin do terminu | formula | `DATETIME_DIFF({Termin}, NOW(), 'hours')` |
| Czas do przypisania (h) | formula | `IF({Przypisano}, DATETIME_DIFF({Przypisano}, {Utworzono}, 'minutes')/60)` |

**Tabela `Zdarzenia`** (dziennik, z niego później metryki)

| Pole | Typ | Uwagi |
| --- | --- | --- |
| Opis | single line text (primary) | np. „Ewa wzięła: Wycieczka” |
| Zadanie | link do `Zadania` |  |
| Typ | single select | `Utworzono`, `Przypisano`, `Zrobione`, `Przypomnienie`, `Eskalacja`, `Odrzucone kliknięcie`, `Błąd` |
| Kto | link do `Rodzice` | puste dla zdarzeń systemowych |
| Kiedy | created time | automatycznie |

Widoki do utworzenia: `Otwarte` (Status ≠ Zrobione, Anulowane; sort po Terminie), `Nieprzypisane`, `Po terminie`, `Zrobione w tym tygodniu`.

## S1 – Dodaj zadanie (Make)

S1 to scenariusz uruchamiany na żądanie (scheduling: On demand) ze zdefiniowanymi wejściami i wyjściami (Scenario inputs/outputs). Dzięki temu Claude widzi go jako narzędzie, a scraper i webhook wywołują go tym samym kontraktem.

**Wejścia**

| Nazwa | Typ | Wymagane | Opis dla Claude |
| --- | --- | --- | --- |
| tytul | text | tak | Krótka nazwa sprawy, maks. 100 znaków |
| termin | text (ISO 8601) | tak | Data i godzina w Europe/Warsaw, np. 2026-11-14T08:00:00+01:00 |
| opis | text | nie | Co przynieść, ile zapłacić, szczegóły |
| kwota | number | nie | Kwota w PLN |
| zrodlo | text | nie | Claude, Webhook lub Scraper; domyślnie Claude |
| id\_zrodla | text | nie | Identyfikator do deduplikacji |

**Kroki**

1. Walidacja: `tytul` niepusty; `termin` parsuje się przez `parseDate` i jest w przyszłości. Błąd → wyjście `status = blad`, `komunikat` po polsku, koniec.
2. Deduplikacja: gdy `id_zrodla` jest podane, Airtable Search records w `Zadania` z formułą `{ID źródła} = '<id>'`. Znaleziono → wyjście `status = duplikat` z ID istniejącego rekordu, bez maili.
3. Airtable Create record w `Zadania`: Status `Nowe`, Token = `{{uuid}}`, Liczba przypomnień = 0, pozostałe z wejść.
4. Airtable Create record w `Zdarzenia`: Typ `Utworzono`, link do zadania.
5. Airtable Search records w `Rodzice` z formułą `{Aktywny}`; Iterator po rodzicach.
6. Gmail Send an email do każdego rodzica, szablon „Nowe zadanie”. Linki są osobiste, bo zawierają klucz rodzica (sekcja Szablony maili).
7. Wyjścia scenariusza: `status = utworzono`, `id`, `tytul`, `termin`, `wyslano_maili`.

**Obsługa błędów:** na module Gmail i Airtable error handler Break z 3 ponowieniami co 1 minutę; włączone Incomplete executions. Po nieudanych ponowieniach zapis zdarzenia typu `Błąd` z treścią błędu.

**Wejście z webhooka (S1-W):** osobny, mały scenariusz z Custom webhook (POST JSON o tych samych polach), który wywołuje S1 modułem Scenarios „Run a scenario” i zwraca jego wyjścia w Webhook response (200 lub 400). Webhook chroni nagłówek `X-Api-Key` sprawdzany filtrem.

## S2 – Kliknięcia z maila (Make)

S2 przyjmuje kliknięcia przycisków w dwóch krokach. Link z maila (GET) tylko pokazuje stronę z potwierdzeniem, a zmianę robi dopiero przycisk na tej stronie (POST). Dzięki temu skaner linków w poczcie ani podgląd linku nie przypisze zadania przez przypadek.

**Trigger:** Custom webhook, włączone przetwarzanie sekwencyjne (bez równoległego). Kolejka Make wykonuje kliknięcia po kolei, więc dwa jednoczesne „Biorę to” nie nadpiszą się nawzajem.

**Parametry** (query w GET, pola formularza w POST)

| Parametr | Znaczenie |
| --- | --- |
| t | ID rekordu zadania w Airtable |
| a | akcja: `take` (Biorę to) albo `done` (Zrobione) |
| p | klucz rodzica z tabeli `Rodzice` |
| k | token zadania |
| ok | `1` tylko w POST z formularza potwierdzenia |

**Kroki wspólne**

1. Airtable Get a record `Zadania` po `t`. Brak rekordu albo `k` ≠ Token → strona „Link nieważny” (HTTP 403) i zdarzenie `Odrzucone kliknięcie`.
2. Airtable Search records `Rodzice` po `Klucz = p`. Brak → jak wyżej.
3. Router: `ok` puste → gałąź Potwierdzenie; `ok = 1` i `a = take` → gałąź Biorę; `ok = 1` i `a = done` → gałąź Zrobione.

**Gałąź Potwierdzenie (GET):** Webhook response z HTML: tytuł, termin, opis i jeden przycisk. Przycisk to formularz `method=POST` na ten sam adres webhooka z ukrytymi polami t, a, p, k oraz `ok=1`. Jeśli zadanie ma już osobę albo jest zamknięte, strona od razu mówi „Już przejęte przez X” lub „Zadanie zamknięte”, bez przycisku.

**Gałąź Biorę (POST, a = take)** – router po aktualnym stanie rekordu:

| Stan zadania | Akcja | Strona |
| --- | --- | --- |
| Status `Nowe` | Update: Osoba = rodzic, Status `Przypisane`, Przypisano = now; zdarzenie `Przypisano`; mail do drugiego rodzica „X bierze: tytuł” | „Gotowe, to Twoje” |
| `Przypisane` do tego samego rodzica | brak | „Już to masz” |
| `Przypisane` do innego rodzica | zdarzenie `Odrzucone kliknięcie` | „Już przejęte przez Y” |
| `Zrobione` lub `Anulowane` | brak | „Zadanie zamknięte” |

**Gałąź Zrobione (POST, a = done):** gdy Status to `Zrobione`, strona „Już oznaczone”. W przeciwnym razie Update: Status `Zrobione`, Zrobiono = now, Osoba = rodzic, jeśli była pusta; zdarzenie `Zrobione`; strona „Zrobione, dzięki”.

**Odpowiedzi:** każda gałąź kończy się Webhook response, status 200 (403 dla nieważnego linku), nagłówek `Content-Type: text/html; charset=utf-8`. HTML jest prosty i mobilny: jedna kolumna, duży przycisk, bez zewnętrznych zasobów.

## S3 – Przypomnienia (Make)

S3 uruchamia się co 2 godziny między 7:00 a 21:00 (Europe/Warsaw, ograniczenie godzin w zaawansowanym harmonogramie) i ma trzy gałęzie routera. Każda zaczyna się od Airtable Search records z formułą, a kończy aktualizacją rekordu, więc to samo przypomnienie nie wyjdzie dwa razy.

**Parametry** (zmienne na początku scenariusza, moduł Set multiple variables)

| Zmienna | Wartość | Znaczenie |
| --- | --- | --- |
| ODSTEP\_H | 4 | co ile godzin wraca nieprzypisane zadanie |
| PILNE\_PO | 2 | od którego przypomnienia temat dostaje dopisek PILNE |
| PRZED\_TERMINEM\_H | 28 | okno „wieczór przed” liczone w godzinach do terminu |

**Gałąź A – Nikt nie wziął**

Formuła: `AND({Status}='Nowe', DATETIME_DIFF(NOW(),{Utworzono},'hours')>=4, OR({Ostatnie przypomnienie}=BLANK(), DATETIME_DIFF(NOW(),{Ostatnie przypomnienie},'hours')>=4))`

Akcje: mail „Nikt jeszcze nie wziął” do obojga rodziców z tymi samymi przyciskami; temat z dopiskiem PILNE, gdy Liczba przypomnień ≥ 2 albo Godzin do terminu < 24. Potem Update: Liczba przypomnień + 1, Ostatnie przypomnienie = now; zdarzenie `Przypomnienie`.

**Gałąź B – Wieczór przed terminem**

Filtr wejściowy: godzina ≥ 18 (`formatDate(now; "H"; "Europe/Warsaw")`) albo Godzin do terminu ≤ 6.

Formuła: `AND({Status}='Przypisane', NOT({Przypomnienie przed terminem}), {Godzin do terminu}>0, {Godzin do terminu}<=28)`

Akcje: mail „Jutro: tytuł” tylko do przypisanej osoby, z przyciskiem Zrobione. Update: Przypomnienie przed terminem = true; zdarzenie `Przypomnienie`.

**Gałąź C – Po terminie**

Formuła: `AND(OR({Status}='Nowe', {Status}='Przypisane'), IS_BEFORE({Termin}, NOW()), NOT({Po terminie}))`

Akcje: mail „Po terminie: czy zrobione?” do obojga z przyciskiem Zrobione. Update: Po terminie = true; zdarzenie `Eskalacja`.

**Obsługa błędów:** jak w S1. Błąd jednego rekordu nie zatrzymuje pozostałych (error handler Resume na module Gmail z zapisem zdarzenia `Błąd`).

## Szablony maili

Pięć szablonów HTML trzymanych w repo w `templates/`. Wklejasz je do pola Content w module Gmail, a zmienne Make podstawiasz w miejsce znaczników `{{...}}`. Tematy zaczynają się od `[Szkoła]`, żeby dało się ustawić filtr w Gmailu.

| Szablon | Do kogo | Temat | Przyciski |
| --- | --- | --- | --- |
| `nowe.html` | oboje | \[Szkoła\] Nowe: {{tytul}} – do {{termin\_krotko}} | Biorę to, Zrobione |
| `przypomnienie.html` | oboje | \[Szkoła\] Nikt jeszcze nie wziął: {{tytul}} (+ PILNE) | Biorę to, Zrobione |
| `przejete.html` | drugi rodzic | \[Szkoła\] {{imie}} bierze: {{tytul}} | brak |
| `jutro.html` | przypisana osoba | \[Szkoła\] Jutro: {{tytul}} | Zrobione |
| `po_terminie.html` | oboje | \[Szkoła\] Po terminie: {{tytul}} – zrobione? | Zrobione |

**Treść każdego maila:** tytuł, termin w formacie `D MMMM YYYY, HH:mm` po polsku (Make: `formatDate` z locale pl), opis, kwota (jeśli jest) i przyciski. W stopce informacja, kto już wziął zadanie.

**Link przycisku** (osobny dla każdego rodzica):

```
{{S2_WEBHOOK_URL}}?t={{record_id}}&a=take&p={{klucz_rodzica}}&k={{token}}
```

**Przycisk w HTML** (tabela i style inline, bo klienci poczty ignorują CSS w `<head>`):

```html
<table role="presentation" cellspacing="0" cellpadding="0"><tr>
  <td style="border-radius:8px;background:#2563eb;">
    <a href="{{link_take}}" style="display:inline-block;padding:12px 20px;color:#ffffff;font-family:Arial,sans-serif;font-size:16px;text-decoration:none;">Biorę to</a>
  </td>
  <td width="12"></td>
  <td style="border-radius:8px;background:#16a34a;">
    <a href="{{link_done}}" style="display:inline-block;padding:12px 20px;color:#ffffff;font-family:Arial,sans-serif;font-size:16px;text-decoration:none;">Zrobione</a>
  </td>
</tr></table>
```

## Integracja z Claude: „dodaj …”

Konektor Make w claude.ai udostępnia Claude'owi scenariusze uruchamiane na żądanie, które mają zdefiniowane wejścia. S1 jest więc od razu narzędziem. Claude zamienia zdanie pisane po ludzku na pola `tytul`, `termin`, `opis` i `kwota`, a potem uruchamia scenariusz.

**Opcjonalnie S4 – Lista otwartych:** drugi scenariusz na żądanie, bez wejść. Szuka w `Zadania` widoku `Otwarte` i zwraca tablicę (tytuł, termin, status, osoba). Dzięki niemu działa pytanie „co mamy na ten tydzień?”.

**Instrukcje do wklejenia w projekt Claude „Asystent szkolny”:**

```markdown
Gdy piszę „dodaj …”, dodajesz sprawy szkolne scenariuszem Make „Dodaj zadanie”.
- Strefa czasowa: Europe/Warsaw. Daty względne („w czwartek”, „jutro”) liczysz od dzisiejszej daty.
- Brak godziny: wycieczki i przyniesienie czegoś = 07:30, zebrania bez godziny = zapytaj.
- Data niejednoznaczna: zapytaj jednym krótkim pytaniem, zanim uruchomisz scenariusz.
- tytul krótki (do 60 znaków), szczegóły i rzeczy do przyniesienia w opis, kwotę w PLN w kwota.
- Kilka spraw w jednej wiadomości = osobne wywołania.
- Po wywołaniu odpowiedz jedną linią: co dodałeś i na kiedy. Przy status=duplikat lub blad powiedz to wprost.
```

**Przykład:** „dodaj: wycieczka do Krakowa 14.11, 40 zł i zgoda” zamienia się w `tytul` „Wycieczka do Krakowa”, `termin` 2026-11-14T07:30:00+01:00, `opis` „Przynieść 40 zł i podpisaną zgodę”, `kwota` 40.

## Dashboard „Kto to ogarnia”

Dashboard to jedna strona HTML (bez frameworka, hosting na GitHub Pages), którą oboje otwieracie w telefonie. Pokazuje wszystkie otwarte sprawy i pozwala je przejąć, oddać albo zamknąć jednym kliknięciem. Strona nigdy nie zna tokenu Airtable: dane czyta i zmienia przez webhook Make (S5), więc sekrety zostają w Make.

**Układ**

| Kolumna | Co pokazuje | Przyciski na karcie |
| --- | --- | --- |
| Wolne | Status `Nowe`, sort po terminie | Biorę to, Zrobione |
| Ewa | `Przypisane` do Ewy | Zrobione, Oddaj |
| Mąż | `Przypisane` do męża | Zrobione, Przejmij |
| Zrobione | ostatnie 7 dni, zwinięte | brak |

- Karta: tytuł, termin („za 2 dni”, „jutro 7:30”), kwota, opis po rozwinięciu.
- Kolory: termin < 24 h = pomarańczowy pasek, po terminie = czerwony, wolne dłużej niż 4 h = znacznik „wisi”.
- Licznik u góry: wolne / moje / po terminie.
- Telefon: kolumny jako zakładki; komputer: cztery kolumny obok siebie. Tryb jasny i ciemny.
- Odświeżanie co 60 s i po każdej akcji; po kliknięciu karta od razu się przesuwa, a przy błędzie wraca z komunikatem (np. „Już przejęte przez Tomka”).

**Logowanie:** w tabeli `Rodzice` dochodzi pole `Klucz dostępu` (losowy ciąg, single line text). Każdy rodzic raz otwiera swój link `.../?u=ewa&s=<klucz dostępu>`; strona zapisuje to w localStorage i usuwa z paska adresu. S5 sprawdza parę u + s przy każdym żądaniu.

**S5 – API dashboardu (Make)**

Custom webhook, przetwarzanie sekwencyjne, ten sam zestaw reguł co S2. Żądania to „proste” POST-y z `Content-Type: text/plain` i JSON w treści, bez własnych nagłówków. Dzięki temu przeglądarka nie wysyła zapytania preflight OPTIONS. Odpowiedź zawsze JSON z nagłówkiem `Access-Control-Allow-Origin` ustawionym na adres strony.

| akcja | Treść żądania | Wynik |
| --- | --- | --- |
| `lista` | u, s | otwarte zadania + zrobione z 7 dni: id, tytuł, termin, kwota, opis, status, osoba, godziny wolne |
| `take` | u, s, id | jak gałąź Biorę w S2 |
| `done` | u, s, id | jak gałąź Zrobione w S2 |
| `release` (Oddaj) | u, s, id | tylko osoba przypisana: Osoba puste, Status `Nowe`, Liczba przypomnień = 0, Ostatnie przypomnienie = now; zdarzenie `Oddano`; mail do drugiego rodzica „Wolne: tytuł” |
| `przejmij` | u, s, id | zadanie przypisane do drugiej osoby przechodzi na pytającego; zdarzenie `Przypisano`; mail do poprzedniej osoby |

Odpowiedź akcji: `{ "ok": true, "zadanie": {...} }` albo `{ "ok": false, "powod": "przejete", "kto": "Tomek" }`.

**Wspólna logika:** zmiany statusu wydziel do podscenariusza „Zmień status” (wejścia: id, akcja, klucz rodzica), wywoływanego przez S2 i S5 modułem Run a scenario. Reguły są wtedy w jednym miejscu, a mail i dashboard zawsze zachowują się tak samo. Do typów w `Zdarzenia` dochodzi `Oddano`.

**Link w mailach:** w stopce każdego szablonu jest link „Zobacz wszystkie sprawy”, który otwiera dashboard (zmienna `DASHBOARD_URL` w `.env`).

**Dla rekrutera:** dashboard pokazuje metryki procesu, nie tylko samą automatyzację. Liczniki i czas do przypisania odpowiadają na wymóg z ogłoszenia: „pozwala sprawdzić wynik”.

**Plan B:** zamiast własnej strony można zbudować Airtable Interface (układ Kanban po polu Status, przyciski aktualizujące rekord). Jest szybciej, ale mąż potrzebuje konta Airtable, a w portfolio wypada słabiej niż własne API i front.

## Repo, konfiguracja i kolejność budowy

Czynności z logowaniem wykonujesz Ty: konto Airtable, token, połączenia Gmail i Airtable w Make (OAuth). Claude Code buduje resztę i pyta o wartości, których nie zna.

**Struktura repozytorium**

```
asystent-szkolny/
  SPEC.md                 # ten dokument
  README.md               # opis dla rekrutera: problem, diagram, decyzje, demo
  .env.example            # nazwy zmiennych bez wartości
  .gitignore              # .env, blueprints z prawdziwymi URL-ami
  airtable/
    setup_base.py         # tworzy tabele, pola, opcje selectów
    seed_rodzice.py       # dodaje dwóch rodziców z .env
  make/
    s1_dodaj_zadanie.json
    s1w_webhook.json
    s2_klikniecia.json
    s3_przypomnienia.json
    s4_lista_otwartych.json
    s5_api_dashboardu.json
    sub_zmien_status.json
  dashboard/
    index.html            # tablica zadań: HTML + CSS + JS w jednym pliku
  templates/              # maile i strony HTML dla S2
  tests/
    smoke_test.py         # scenariusze z sekcji Plan testów
  docs/
    architektura.md
    decyzje.md            # dlaczego dwa kroki, dlaczego token, dlaczego sekwencyjnie
```

**Zmienne w `.env`**

| Zmienna | Skąd |
| --- | --- |
| AIRTABLE\_TOKEN | Personal access token, zakresy: data.records:read, data.records:write, schema.bases:read, schema.bases:write |
| AIRTABLE\_BASE\_ID | z adresu pustej bazy (`app...`) |
| RODZIC1\_IMIE, RODZIC1\_KLUCZ, RODZIC1\_EMAIL | Ty |
| RODZIC2\_IMIE, RODZIC2\_KLUCZ, RODZIC2\_EMAIL | mąż |
| MAKE\_API\_TOKEN, MAKE\_ZONE, MAKE\_TEAM\_ID | profil Make, sekcja API |
| S1W\_API\_KEY | losowy ciąg dla webhooka S1-W |

**Kolejność budowy dla Claude Code**

1. Utwórz repo, `.gitignore`, `.env.example`, `README.md` (szkic).
2. Napisz i uruchom `airtable/setup_base.py`, potem `seed_rodzice.py`; sprawdź schemat odczytem przez API.
3. Zbuduj podscenariusz „Zmień status”, a potem S2 jako pierwszy ze scenariuszy z webhookiem, bo jego adres webhooka trafia do maili. Zapisz URL jako zmienną `S2_WEBHOOK_URL`.
4. Zbuduj S1, potem S1-W, S3, S4 i S5. Na końcu dashboard/index.html z adresem S5 w konfiguracji i publikacja na GitHub Pages.
5. Scenariusze twórz przez serwer MCP Make albo API Make, waliduj blueprint przed zapisem i eksportuj każdy do `make/`. Bez dostępu do API przygotuj blueprinty JSON do importu (Create scenario, Import blueprint) i listę kliknieęć do ustawienia po imporcie.
6. Po imporcie podłącz połączenia Gmail i Airtable w każdym module (robi to użytkowniczka).
7. Uruchom `tests/smoke_test.py` i przejdź ręczne testy z ostatniej sekcji.
8. Uzupełnij `README.md`: diagram, zrzuty ekranu, decyzje, link do nagrania demo.

**Zasady:** żadnych sekretów w repo ani w blueprintach (URL-e webhooków zastąpione znacznikami); każda zmiana w Make eksportowana do `make/`, żeby repo pokazywało aktualny stan.

## Testy, akceptacja i roadmapa

V1 jest gotowa, gdy wszystkie testy poniżej przechodzą na prawdziwych adresach obojga rodziców, a README z nagraniem demo jest w repo.

**Plan testów**

| # | Test | Oczekiwany wynik |
| --- | --- | --- |
| 1 | „dodaj: zebranie w czwartek 17:00” w Claude | rekord `Nowe`, termin w najbliższy czwartek 17:00, 2 maile, zdarzenie `Utworzono` |
| 2 | Ten sam `id_zrodla` wysłany 2 razy przez S1-W | drugi raz `status = duplikat`, brak maili |
| 3 | Termin w przeszłości | `status = blad`, komunikat po polsku, brak rekordu |
| 4 | Webhook S1-W bez `X-Api-Key` | 401, brak rekordu |
| 5 | Kliknięcie linku „Biorę to” (sam GET) | strona potwierdzenia, rekord bez zmian |
| 6 | Potwierdzenie przez Ewę | `Przypisane` do Ewy, mail „Ewa bierze” do męża |
| 7 | Mąż potwierdza to samo zadanie chwilę później | strona „Już przejęte przez Ewę”, zdarzenie `Odrzucone kliknięcie` |
| 8 | Link ze zmienionym tokenem | strona „Link nieważny”, 403 |
| 9 | Nieprzypisane zadanie po 4 h (test: ODSTEP\_H = 0) | mail przypomnienia, licznik + 1; kolejne uruchomienie przed upływem odstępu nic nie wysyła |
| 10 | Przypisane zadanie na jutro, przebieg S3 o 18:00 | jeden mail do przypisanej osoby, checkbox ustawiony |
| 11 | Zadanie po terminie, niezrobione | mail eskalacji raz, flaga `Po terminie` |
| 12 | Dashboard: „Biorę to” na wolnej karcie | karta w kolumnie Ewy, ten sam efekt co test 6 |
| 13 | Dashboard: „Oddaj” | karta wraca do Wolnych, licznik przypomnień wyzerowany |
| 14 | Dashboard ze złym kluczem dostępu | komunikat o braku dostępu, żadnych danych |
| 15 | Dashboard na telefonie | zakładki zamiast kolumn, bez poziomego przewijania |

**Kryteria akceptacji**

- [ ] Od „dodaj” w Claude do maili u obojga mija mniej niż 1 minuta.
- [ ] Jedno zadanie nigdy nie ma dwóch osób ani podwójnych przypomnień tego samego typu.
- [ ] W repo nie ma żadnego sekretu; blueprinty są aktualne.
- [ ] Tabela `Zdarzenia` pozwala policzyć średni czas do przypisania i liczbę przypomnień.

**Roadmapa v2**

1. Scraper MobiDziennika przekazuje wiadomości do Gemini lub Claude, które wyciągają zadania i wołają S1 z `zrodlo = Scraper` i ID wiadomości jako `id_zrodla`.
2. Zadania z terminem trafiają do Google Calendar; zmiana terminu aktualizuje wydarzenie.
3. Podsumowanie tygodnia w niedzielę o 19:00: co czeka, kto ile zrobił, średni czas do przypisania.
4. Powiadomienia przez WhatsApp Cloud API z przyciskami zamiast maili.
