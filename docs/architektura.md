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
| **Asystent – API** | jeden Custom webhook, trasa po `?cel=` | S2 kliknięcia z maili, S1-W, S5 API dashboardu, S3 przypomnienia |

Wszystkie zmiany stanu z kliknięć i z dashboardu przechodzą przez Silnik, więc mail i dashboard stosują te same reguły. S3 aktualizuje tylko pola przypomnień, dlatego działa bezpośrednio w API.

## Adresy

| Wejście | Adres |
| --- | --- |
| Kliknięcia z maili | `S2_WEBHOOK_URL?t=…&a=take&p=…&k=…` |
| S1-W | `S2_WEBHOOK_URL?cel=dodaj` + nagłówek `X-Api-Key` |
| Dashboard | `S2_WEBHOOK_URL?cel=api` (pola formularza `u`, `s`, `akcja`, `id`) |
| S3 | `S2_WEBHOOK_URL?cel=przypomnienia` + `X-Api-Key` (opcjonalnie `odstep=0`, `wieczor=1` do testów) |

## Budżet operacji

Darmowy plan ma około 1000 operacji miesięcznie. Pusty przebieg S3 kosztuje około 5 operacji, czyli przy 3 przebiegach dziennie około 450 miesięcznie. Odświeżenie dashboardu to 4 operacje, dlatego strona odświeża się przy otwarciu, po akcji, przy powrocie do karty i co 10 minut, a nie co 60 s.
