# Lista spraw bez Make (Google Apps Script)

`lista.gs` to mała aplikacja internetowa Google, która czyta listę spraw prosto z Airtable. Dashboard pobiera z niej listę zamiast z Make, więc odświeżanie listy **nie zużywa operacji Make** i może być częste (co minutę przy powrocie do karty, co 5 minut, gdy strona jest otwarta). Akcje (Zrobione, → Dawid), dodawanie spraw i maile dalej idą przez Make.

## Wdrożenie (jednorazowo, ok. 10 minut)

### 1. Token Airtable tylko do odczytu
1. Wejdź na **airtable.com/create/tokens** → **Create new token**.
2. Nazwa: `Kto to ogarnia – lista (Apps Script)`.
3. Scope: tylko **`data.records:read`**.
4. Access: baza **„Asystent szkolny”**.
5. **Create token** i skopiuj go (pokazuje się raz).

### 2. Projekt Apps Script
1. Wejdź na **script.google.com** (Twoje konto Google) → **Nowy projekt**.
2. Nazwij go `Kto to ogarnia – lista`.
3. Usuń zawartość pliku `Kod.gs` i wklej całą zawartość pliku `apps-script/lista.gs` z repozytorium.
4. Zapisz (Ctrl+S).

### 3. Właściwości skryptu (sekrety)
1. Po lewej **⚙ Ustawienia projektu** → na dole **Właściwości skryptu** → **Dodaj właściwość skryptu**.
2. Dodaj dwie:
   - `AIRTABLE_TOKEN` – token z kroku 1,
   - `AIRTABLE_BASE_ID` – `appBSubdL1R6lgjY8`.
3. **Zapisz właściwości skryptu**.

### 4. Wdrożenie jako aplikacja internetowa
1. W prawym górnym rogu **Wdróż** → **Nowe wdrożenie**.
2. Kliknij ⚙ obok „Wybierz typ” → **Aplikacja internetowa**.
3. Opis: `lista`; **Wykonaj jako: Ja**; **Kto ma dostęp: Każdy**.
4. **Wdróż** → Google poprosi o autoryzację (dostęp do zewnętrznych usług – to zapytania do Airtable) → zezwól.
5. Skopiuj **URL aplikacji internetowej** (kończy się na `/exec`).

„Każdy” oznacza, że adres odpowiada bez logowania do Google – dane chroni para klucz rodzica + klucz dostępu (ta sama co w dashboardzie). Bez niej skrypt zwraca tylko `brak_dostepu`.

### 5. Podłączenie do dashboardu
Adres `/exec` wpisuje się w `dashboard/index.html` w `CONFIG.lista`. Po zmianie kodu skryptu trzeba zrobić **Wdróż → Zarządzaj wdrożeniami → edytuj → Nowa wersja**, żeby adres pokazywał nową wersję.
