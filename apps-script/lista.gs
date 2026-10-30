/**
 * Kto to ogarnia – odczyt listy spraw bez Make (Google Apps Script, aplikacja internetowa).
 *
 * Dashboard wysyła POST (text/plain, JSON {u, s, akcja: "lista"}). Skrypt sprawdza parę
 * klucz rodzica + klucz dostępu w tabeli Rodzice i zwraca otwarte sprawy oraz zrobione
 * w ostatnich 7 dniach – w tym samym formacie co API w Make ({ok, ja, zadania}).
 * Nie zużywa operacji Make. Token Airtable jest tylko we Właściwościach skryptu.
 *
 * Właściwości skryptu (Ustawienia projektu → Właściwości skryptu):
 *   AIRTABLE_TOKEN    – token Airtable tylko do odczytu (data.records:read) dla tej bazy
 *   AIRTABLE_BASE_ID  – ID bazy (app…)
 */

// takie same jak w API Make (make/build.py)
const OTWARTE = "OR({Status}='Nowe', {Status}='Przypisane', " +
  "AND({Status}='Zrobione', DATETIME_DIFF(NOW(), {Zrobiono}, 'days') < 7))";
// pola wysyłane do dashboardu (bez Tokenu i pól technicznych)
const POLA = ["Tytuł", "Opis", "Termin", "Rodzaj", "Kategoria", "Kwota", "Status", "Osoba imię",
  "Utworzono", "Przypisano", "Zrobiono"];

function doPost(e) {
  let req = {};
  try {
    req = JSON.parse((e && e.postData && e.postData.contents) || "{}");
  } catch (err) {
    return json_({ ok: false, powod: "zle_zadanie" });
  }
  return obsluz_(req);
}

function doGet() {
  return json_({ ok: false, powod: "uzyj_post" });
}

function obsluz_(req) {
  try {
    const u = String(req.u || ""), s = String(req.s || "");
    // wzorce jak w Make – chronią formułę Airtable przed wstrzyknięciem
    if (!/^[a-z0-9_-]{1,30}$/.test(u) || !/^[A-Za-z0-9_-]{16,64}$/.test(s)) {
      return json_({ ok: false, powod: "brak_dostepu" });
    }
    const rodzic = airtable_("Rodzice", "AND({Aktywny}, {Klucz}='" + u + "', {Klucz dostępu}='" + s + "')")[0];
    if (!rodzic) return json_({ ok: false, powod: "brak_dostepu" });
    if (req.akcja !== "lista") return json_({ ok: false, powod: "nieznana_akcja" });

    const zadania = airtable_("Zadania", OTWARTE).map(function (r) {
      return { id: r.id, fields: wybierz_(r.fields) };
    });
    return json_({ ok: true, ja: rodzic.fields["Imię"], zadania: zadania });
  } catch (err) {
    console.error(err);
    return json_({ ok: false, powod: "blad" });
  }
}

/** Wszystkie rekordy tabeli spełniające formułę (z obsługą stronicowania Airtable). */
function airtable_(tabela, formula) {
  const props = PropertiesService.getScriptProperties();
  const base = props.getProperty("AIRTABLE_BASE_ID");
  const token = props.getProperty("AIRTABLE_TOKEN");
  let rekordy = [], offset = "";
  do {
    const url = "https://api.airtable.com/v0/" + base + "/" + encodeURIComponent(tabela) +
      "?filterByFormula=" + encodeURIComponent(formula) + (offset ? "&offset=" + offset : "");
    const r = UrlFetchApp.fetch(url, { headers: { Authorization: "Bearer " + token }, muteHttpExceptions: true });
    if (r.getResponseCode() !== 200) throw new Error("Airtable " + r.getResponseCode() + ": " + r.getContentText());
    const j = JSON.parse(r.getContentText());
    rekordy = rekordy.concat(j.records);
    offset = j.offset || "";
  } while (offset);
  return rekordy;
}

function wybierz_(fields) {
  const out = {};
  POLA.forEach(function (k) { if (fields[k] !== undefined) out[k] = fields[k]; });
  return out;
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

/** Do sprawdzenia w edytorze (Uruchom → test): wypisuje liczbę spraw dla podanej pary. */
function test() {
  const wynik = JSON.parse(obsluz_({ u: "ewa", s: "WKLEJ_TU_KLUCZ_DOSTEPU", akcja: "lista" }).getContent());
  console.log(wynik.ok ? "OK, spraw: " + wynik.zadania.length : "Błąd: " + wynik.powod);
}
