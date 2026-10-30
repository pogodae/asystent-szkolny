# Architektura

```
 Claude („dodaj …”) ──► konektor Make ──────────────┐
                                                    ▼
 Webhook S1-W (POST JSON, X-Api-Key) ─┐   ┌──────────────────────────────┐
 Kliknięcia z maili (GET / POST)  ────┤   │ Asystent – Silnik            │
 Dashboard (POST form, u + s)     ────┼──►│ na żądanie, kolejka          │──► Airtable
 GitHub Actions cron (3× dziennie) ───┘   │ dodaj · take · done ·        │    (Zadania,
          │                               │ release · przejmij           │     Rodzice,
          ▼                               └──────────────────────────────┘     Zdarzenia)
 ┌──────────────────────────────────┐                   │
 │ Asystent – API (jeden webhook)   │── odczyty ────────┘
 │ ?cel=  (brak) → S2 kliknięcia    │                   │
 │        dodaj  → S1-W             │                   ▼
 │        api    → S5 dashboard     │                 Gmail
 │        przypomnienia → S3        │      (Nowe, Przejęte, Wolne, Przypomnienie,
 └──────────────────────────────────┘       Jutro, Po terminie)
```

## Dlaczego 2 scenariusze zamiast 7

Darmowy plan Make pozwala na 2 aktywne scenariusze. Role ze SPEC (S1, S1-W, S2, S3, S4, S5 i „Zmień status”) są więc rozdzielone według tego, **co zmienia stan**, a co tylko przyjmuje żądania:

| Scenariusz | Wyzwalacz | Odpowiada za |
| --- | --- | --- |
| **Asystent – Silnik** | na żądanie (Claude, Call a scenario), kolejka | S1 dodaj zadanie; „Zmień status”: take, done, release, przejmij |
| **Asystent – API** | jeden Custom webhook, trasa po `?cel=` | S1-W, S5 API dashboardu, S3 przypomnienia (dawne S2 – kliknięcia z maili – usunięte) |

Wszystkie zmiany stanu z kliknięć i z dashboardu przechodzą przez Silnik, więc mail i dashboard stosują te same reguły. S3 aktualizuje tylko pola przypomnień, dlatego działa bezpośrednio w API.

## Adresy

| Wejście | Adres |
| --- | --- |
| Stary link z maila | `S2_WEBHOOK_URL?t=…` – strona z odnośnikiem do listy spraw |
| S1-W | `S2_WEBHOOK_URL?cel=dodaj` + nagłówek `X-Api-Key`; JSON: `tytul`, `termin`, `rodzaj` (Do dnia / W dniu / Wydarzenie), `opis`, `kwota`, `id_zrodla` |
| Dashboard | `S2_WEBHOOK_URL?cel=api` (pola formularza `u`, `s`, `akcja`, `id`) |
| S3 | `S2_WEBHOOK_URL?cel=przypomnienia` + `X-Api-Key` (raz dziennie rano z GitHub Actions) |

## Budżet operacji

Darmowy plan Make ma około 1000 operacji miesięcznie, a po jego wyczerpaniu Make wstrzymuje scenariusze. Dlatego:

| Co | Operacje | Jak często |
| --- | --- | --- |
| Przypomnienia (S3) | 3 + 2–3 na każdą sprawę na jutro | raz dziennie rano (GitHub Actions) |
| Lista na dashboardzie | 4 | przy otwarciu, gdy lista w telefonie jest starsza niż 30 min, albo „Odśwież” |
| Akcja z dashboardu (biorę, zrobione, oddaj, przejmij) | 4 (API 2 + Silnik 2) | na kliknięcie |
| Przypisanie Dawidowi | 6 (z mailem) | na kliknięcie |
| Dodanie sprawy z dashboardu | 3 | na sprawę |
| Dodanie sprawy przez Claude | 1–2 | na sprawę |

Maile wychodzą tylko rano dzień przed terminem (do osoby przypisanej, a przy sprawie wolnej do rodziców z powiadomieniami „Wszystkie”) oraz od razu przy przypisaniu sprawy osobie z ustawieniem „Tylko przypisane”. Dostęp do API dashboardu sprawdzają filtry z parami klucz + klucz dostępu, bez zapytania do Airtable. Silnik dostaje ID i imię rodzica od wywołującego (nie szuka go w Airtable), nie zapisuje wpisów do tabeli `Zdarzenia` i nie odczytuje zadania drugi raz po zmianie – dashboard sam przesuwa kartę, a prawdziwy stan pokazuje najbliższe pobranie listy. Filtry i routery w Make są darmowe, więc jeden duży scenariusz z trasami nie kosztuje więcej niż kilka małych.
