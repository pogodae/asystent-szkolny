# Decyzje projektowe

## Dlaczego dwa kroki (GET → POST)

Link w mailu (GET) tylko pokazuje stronę potwierdzenia. Stan zmienia dopiero przycisk na tej stronie (POST z `ok=1`). Skanery linków w poczcie i podglądy linków wykonują GET, więc nie przypiszą zadania przez przypadek.

## Dlaczego token w linku

Link zawiera ID rekordu, klucz rodzica i losowy `Token` zadania (UUID). S2 szuka rekordu formułą `AND(RECORD_ID()='t', {Token}='k')`. Zmieniony lub zgadnięty link kończy się stroną „Link nieważny” (HTTP 403) i zdarzeniem `Odrzucone kliknięcie`. Parametry są najpierw sprawdzane wyrażeniami regularnymi, żeby nie dało się wstrzyknąć niczego do formuły Airtable.

## Dwa scenariusze zamiast siedmiu

Darmowy plan Make pozwala na 2 aktywne scenariusze. **Silnik** (na żądanie, w kolejce) robi wszystko, co zmienia stan: dodawanie i zmiany statusu. **API** (jeden webhook) przyjmuje kliknięcia z maili, S1-W, żądania dashboardu i przypomnienia, rozróżniając je parametrem `?cel=`. Harmonogram S3 trzyma GitHub Actions, który 3 razy dziennie wywołuje `?cel=przypomnienia`. Szczegóły i budżet operacji: [architektura.md](architektura.md).

## Dlaczego sekwencyjnie – i gdzie dokładnie

SPEC zakładał przetwarzanie sekwencyjne webhooka S2. W praktyce Make przy sekwencyjnym webhooku odpowiada od razu `Accepted`, więc przeglądarka nie dostaje strony potwierdzenia.

Rozwiązanie: **sekwencyjny jest Silnik**, a webhook API działa równolegle. Odczyt stanu, decyzja i zapis odbywają się w jednym przebiegu podscenariusza, a Make ustawia jego wywołania w kolejce. Test dwóch jednoczesnych kliknięć „Zrobione” dał jedno zdarzenie zamiast dwóch. Bez kolejki oba „Biorę to” przechodziły i zadanie było przez chwilę przypisane dwa razy.

## Wynik podscenariusza czytany z Airtable

Podscenariusz utworzony przez API nie przekazuje wyjść (`Return output`) do modułu `Call a scenario`, bo Make synchronizuje ich definicję tylko w edytorze. Po wywołaniu S2 czyta więc zadanie jeszcze raz i dobiera stronę wyniku do jego stanu: „Gotowe, to Twoje”, „Już przejęte przez X”, „Zadanie zamknięte” albo „Zrobione, dzięki”. Źródłem prawdy zostaje Airtable.

`Return output` kończy trasę, dlatego maile w podscenariuszu są wysyłane przed nim.

## Pola Airtable po ID

Blueprinty adresują pola przez ID (`make/schema_ids.json`), a odczyty idą przez `Make an API call` z `returnFieldsByFieldId=true`. Nazwy z polskimi znakami i spacjami są w ścieżkach Make kłopotliwe, a ID nie zmienia się po zmianie nazwy pola. Pomocnicze formuły (`Termin tekst`, `Osoba imię`, `Kwota linia`) formatują dane po stronie Airtable, więc Make nie musi tego robić.

## Blueprinty generowane z kodu

`make/build.py` opisuje scenariusze w Pythonie, a `make/deploy.py` wgrywa je przez API Make i eksportuje stan z powrotem do `make/`. URL-e webhooków i klucz API są w repo zastąpione znacznikami `__NAZWA__`.

## Dashboard bez sekretów Airtable

Strona zna tylko adres webhooka API. Każde żądanie niesie parę `u` + `s` (klucz rodzica i losowy klucz dostępu z tabeli `Rodzice`), którą API sprawdza w Airtable. Żądania są „prostymi” POST-ami (`application/x-www-form-urlencoded`), więc przeglądarka nie wysyła preflightu, a odpowiedź ma `Access-Control-Allow-Origin` ustawione na adres GitHub Pages. Adres webhooka jest w kodzie strony jawny, podobnie jak w każdym mailu. Chronią go token zadania, para u + s albo `X-Api-Key`.
