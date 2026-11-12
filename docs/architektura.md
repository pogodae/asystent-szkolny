# Architektura

```
 Claude („dodaj …”) ──► konektor Make ────────────────┐
                                                      ▼
 Webhook S1-W (POST JSON, X-Api-Key) ─┐     ┌────────────────────────────┐
 Dashboard (POST form, u + s)     ────┤     │ Asystent – Silnik          │
 GitHub Actions (raz dziennie)    ────┤     │ na żądanie, kolejka        │──► Airtable
 Stare linki z maili (GET)        ────┤     │ dodaj · done · przypisz    │    (Zadania,
                                      ▼     └────────────────────────────┘     Rodzice)
 ┌──────────────────────────────────────┐          ▲            │                ▲
 │ Asystent – API (jeden webhook)       │──────────┘            ▼                │
 │ ?cel=dodaj         → S1-W            │                     Gmail              │
 │      api           → S5 dashboard    │──── lista, dodaj z formularza, usuń ───┤
 │      przypomnienia → S3              │──── przypomnienia dzień przed ─────────┤
 │ (brak)             → strona z linkiem│                                        │
 └──────────────────────────────────────┘                                        │
 Dashboard – odczyt listy ──► Google Apps Script (0 operacji Make) ──────────────┘
```

## Dlaczego 2 scenariusze zamiast 7

Darmowy plan Make pozwala na 2 aktywne scenariusze. Role ze SPEC (S1, S1-W, S2, S3, S4, S5 i „Zmień status”) są więc rozdzielone według tego, **co zmienia stan**, a co tylko przyjmuje żądania:

| Scenariusz | Wyzwalacz | Odpowiada za |
| --- | --- | --- |
| **Asystent – Silnik** | na żądanie (Claude, Call a scenario), kolejka | S1 dodaj zadanie (właściciel: pierwsza osoba z `Rodzice`); zmiany: done, przypisz (przekazanie drugiej osobie) |
| **Asystent – API** | jeden Custom webhook, trasa po `?cel=` | S1-W, S5 API dashboardu, S3 przypomnienia (dawne S2 – kliknięcia z maili – usunięte) |

Zmiany statusu (Zrobione, przekazanie) i dodawanie spraw z Claude oraz S1-W przechodzą przez Silnik, który działa w kolejce – dwie jednoczesne zmiany tej samej sprawy nie nadpiszą się nawzajem. Dodanie z formularza dashboardu, „miękkie” usunięcie i przypomnienia (S3) zapisują bezpośrednio w API: nie konkurują z innymi zmianami, a każde wywołanie Silnika to dodatkowe operacje Make.

## Adresy

| Wejście | Adres |
| --- | --- |
| Stary link z maila | `S2_WEBHOOK_URL?t=…` – strona z odnośnikiem do listy spraw |
| S1-W | `S2_WEBHOOK_URL?cel=dodaj` + nagłówek `X-Api-Key`; JSON: `tytul`, `termin`, `rodzaj` (Do dnia / W dniu / Wydarzenie), `kategoria`, `opis`, `kwota`, `id_zrodla` (litery, cyfry, `_ . : -`) |
| Dashboard | `S2_WEBHOOK_URL?cel=api` (pola formularza `u`, `s`, `akcja`, `id`, `dla`); odczyt listy zwykle przez Apps Script |
| S3 | `S2_WEBHOOK_URL?cel=przypomnienia` + `X-Api-Key` (raz dziennie rano z GitHub Actions) |

## Budżet operacji

Darmowy plan Make ma około 1000 operacji miesięcznie, a po jego wyczerpaniu Make wstrzymuje scenariusze. Dlatego:

| Co | Operacje | Jak często |
| --- | --- | --- |
| Przypomnienia (S3) | 3 + 2–3 na każdą sprawę na jutro | raz dziennie rano (GitHub Actions) |
| Lista na dashboardzie | 0 z Google Apps Script ([apps-script/](../apps-script/)); 4 z Make, gdy skrypt nie jest podłączony | Apps Script: co minutę przy powrocie do karty i co 5 min; Make: co 30 min |
| Zrobione | 4 (API 2 + Silnik 2) | na kliknięcie |
| Przekazanie drugiej osobie (z mailem) | 6 | na kliknięcie |
| Usuń (kosz; status Anulowane, sprawa zostaje w Airtable) | 3 | na kliknięcie |
| Dodanie sprawy z dashboardu | 3 | na sprawę |
| Dodanie sprawy przez Claude | 1–2 | na sprawę |

Maile wychodzą tylko rano dzień przed terminem (do osoby przypisanej, a przy sprawie wolnej do rodziców z powiadomieniami „Wszystkie”) oraz od razu przy przypisaniu sprawy osobie z ustawieniem „Tylko przypisane”. Dostęp do API dashboardu sprawdzają filtry z parami klucz + klucz dostępu, bez zapytania do Airtable. Silnik dostaje ID i imię rodzica od wywołującego (nie szuka go w Airtable), nie zapisuje wpisów do tabeli `Zdarzenia` i nie odczytuje zadania drugi raz po zmianie – dashboard sam przesuwa kartę, a prawdziwy stan pokazuje najbliższe pobranie listy. Filtry i routery w Make są darmowe, więc jeden duży scenariusz z trasami nie kosztuje więcej niż kilka małych.
