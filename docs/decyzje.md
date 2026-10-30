# Decyzje projektowe

## Każda sprawa ma właściciela

Nie ma już „wolnych” spraw ani przycisków Biorę to / Oddaj / Przejmij. Nowa sprawa od razu należy do Ewy (RODZIC1), która może ją zamknąć (Zrobione) albo przekazać Dawidowi (→ Dawid, mail od razu). Przypomnienie dzień przed zawsze trafia do właściciela. To prostsze i tańsze (mniej tras i operacji), a odpowiada temu, jak naprawdę dzielimy sprawy.

## Oszczędzanie operacji Make

Darmowy plan ma około 1000 operacji miesięcznie, a po ich wyczerpaniu Make wstrzymuje scenariusze. Dlatego akcje z dashboardu kosztują 4 operacje: Silnik dostaje gotowe ID rodzica, nie pisze do `Zdarzeń` i nie ma ponownego odczytu. Dodanie sprawy z dashboardu to 3 operacje, bo zapis idzie od razu w API. Przypomnienia działają raz dziennie, a lista na dashboardzie jest trzymana w telefonie przez 30 minut. Ceną jest to, że konflikt (dwie osoby klikną to samo prawie naraz) widać dopiero przy następnym pobraniu listy, a dziennik `Zdarzenia` nie dostaje już nowych wpisów (statystyki liczą się z pól zadania).

## Maile bez przycisków akcji

Po przejściu na jedno przypomnienie dzień przed terminem maile mają tylko przycisk **Otwórz listę spraw**. Wszystkie akcje robi się na dashboardzie, więc z Make zniknęła obsługa kliknięć (S2): strony potwierdzenia, token w linku i wywołania Silnika z maila. Scenariusz API zmniejszył się mniej więcej o połowę. Link z dawnego maila pokazuje stronę z odnośnikiem do listy. Dwie sekcje poniżej opisują wcześniejsze rozwiązanie.

## Dlaczego dwa kroki (GET → POST) – wcześniej

Link w mailu (GET) tylko pokazuje stronę potwierdzenia. Stan zmienia dopiero przycisk na tej stronie (POST z `ok=1`). Skanery linków w poczcie i podglądy linków wykonują GET, więc nie przypiszą zadania przez przypadek.

## Dlaczego token w linku – wcześniej

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
