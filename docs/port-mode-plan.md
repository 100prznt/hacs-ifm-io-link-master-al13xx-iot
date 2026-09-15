# Pin 2 als Digitaleingang + Portmodus-Umschaltung (Pin 4)

Arbeitsnotiz/Plan, nicht Teil der Nutzer-Doku. Teil 1 ist umgesetzt (ab Version 0.4.0, Bugfix in 0.4.2). Teil 2 ist ab 0.5.0 vollständig umgesetzt (Backend, Websocket-Commands, Panel-Vorschau/Bestätigung, `switch`-Plattform für den DO-Ausgangszustand), siehe Abschnitt "Stand nach 0.5.0" unten.

## Context

Der AL1350/AL1352 hat laut ifm-Datenblatt an jedem M12-Port zwei nutzbare Signale zusätzlich zur Sensorversorgung:

- **Pin 2** ist hardwareseitig **immer** ein digitaler Eingang (11–30 V high / 0–5 V low, kurzschlussfest) – unabhängig davon, ob der Port sonst als IO-Link läuft oder nicht.
- **Pin 4 (C/Q)** ist umschaltbar: entweder IO-Link-Kommunikation (heutiger, einziger unterstützter Zustand) oder digitaler Ausgang (max. 300 mA, kurzschlussfest).

Ziel: Pin 2 als reinen `binary_sensor` je Port sichtbar machen (**erledigt**), und eine **Umschalt-Logik** für den Portmodus von Pin 4 ergänzen (IO-Link ⇄ Digitalausgang, **offen**), analog zum bestehenden Parameter-Restore-Flow abgesichert – weil ein Moduswechsel den ggf. angeschlossenen IO-Link-Sensor vom Port trennt.

Klärung mit dem Nutzer: Pin-2-Sensor entsteht an **allen** Ports (unabhängig vom zugewiesenen Profil). Der Portmodus-Wechsel läuft **ausschließlich im Command-Center-Panel mit Vorschau+Bestätigung** (kein direktes HA-`select`/`switch` zum Umschalten des Modus, da das eine Automation versehentlich einen Sensor-Port kappen könnte). Sobald ein Port im DO-Modus ist, wird der reine Ausgangszustand (an/aus) als normales `switch`-Entity exponiert – das ist ungefährlich und automatisierbar.

**API verifiziert (2026-09-15, gegen echten AL1352 unter 192.168.1.22, Testmaster ohne Produktivbetrieb):**

| Zweck | Pfad | Format |
|---|---|---|
| Pin-2-Eingang lesen | `/iolinkmaster/port[X]/pin2in` | nur `getdata`, Integer 0/1. **Liegt direkt unter `port[X]`, nicht unter `iolinkdevice`** – `port_path()` (in `const.py`) darf hier NICHT verwendet werden, die Funktion hängt immer `/iolinkdevice/` an. Siehe Bugfix-Hinweis unten. |
| Portmodus lesen/schreiben | `/iolinkmaster/port[X]/mode` | Enum `0=Disabled, 1=DI, 2=DO, 3=IO-Link`, `getdata`+`setdata` |
| Portmodus schreiben | `POST /` mit `{"code":"request","cid":1,"adr":"/iolinkmaster/port[X]/mode/setdata","data":{"newvalue":<int>}}` | Antwort `{"code":200}` ohne `data` – passt zu `empty_response=True` wie bei `write_parameter` |
| DO-Ausgangswert (nicht live gegen ein DO getestet, nur Struktur bestätigt) | `/iolinkmaster/port[X]/iolinkdevice/pdout` | Hex-String, `getdata`+`setdata`, gleicher Knoten wie IO-Link-Ausgangsprozessdaten |

Live-Test: Port 3 (unbenutzt, `status=0`) per `setdata` von IO-Link (3) auf DI (1) und zurück auf IO-Link (3) geschaltet, beide Male per `getdata` zurückgelesen und bestätigt – Payload-Form `{"newvalue": <int>}` funktioniert wie bei der ifm-IoT-Core-Standardkonvention erwartet. Der Modus-Pfad ist einfacher als ursprünglich angenommen (`mode` direkt, kein verschachteltes `mode/portmode_device`; Integer-Enum statt String-Enum wie `IOL_AUTOSTART`/`DI_C/Q`/`DO_C/Q`).

## Teil 1 – Pin 2 als `binary_sensor` (erledigt, ab 0.4.0)

Umgesetzt in `coordinator.py`, `entity.py`, `binary_sensor.py`, `__init__.py`, `frontend/panel.js`.

**Bugfix in 0.4.2:** Der erste Versuch nutzte `port_path(port, "pin2in")`, was fälschlich `/iolinkmaster/port[X]/iolinkdevice/pin2in` erzeugte (die Hilfsfunktion hängt immer `/iolinkdevice/` an – richtig für `pdin`/`status`/`vendorid` etc., aber falsch für `pin2in`, das direkt unter dem Port liegt). Das führte dazu, dass der Wert immer `None`/`unbekannt` war, obwohl Pin 2 korrekt verdrahtet war. Fix: Pfad direkt als `f"/iolinkmaster/port[{port}]/pin2in"` bauen, ohne `port_path()`.

Falls für Teil 2 weitere direkt-unter-Port-liegende Knoten gebraucht werden (z. B. `mode`), gilt dieselbe Falle: **nicht** `port_path()` verwenden, sondern den Pfad explizit bauen.

## Teil 2 – Portmodus-Umschaltung (Pin 4) — offen

Folgt strukturell exakt dem bestehenden Parameter-Restore-Flow (`restore.py` + `websocket.py:preview_restore`/`restore_parameters`), der genau für "seltene, risikobehaftete, bestätigungspflichtige Schreibaktion" gebaut ist.

**`custom_components/ifm_iolink/api.py`**
- `request()`-Whitelist um den Lesepfad für den aktuellen Portmodus erweitern (`adr.endswith("/mode")`), damit `client.multi()` ihn wie `pdin`/`pin2in` batchen kann.
- Neue eigenständige Methode `write_port_mode(self, port, mode)`, analog zu `write_parameter()`: eigene strikte Validierung (`port` int 1–8, `mode` int aus `{0, 1, 2, 3}` – Disabled/DI/DO/IO-Link, **nicht** aus `request()`-Whitelist erreichbar), ruft `self._request(f"/iolinkmaster/port[{port}]/mode/setdata", {"newvalue": mode}, empty_response=True)`. Payload-Form live verifiziert.

**`custom_components/ifm_iolink/coordinator.py`**
- Portmodus ändert sich selten – wie `PORT_PROPERTIES` nur alle 60 s im `refresh_metadata`-Zweig mitlesen und im Item-Dict als `item["mode"]` ablegen, damit Panel und Websocket-Snapshot den aktuellen Modus ohne Extra-Request anzeigen können. **Pfad direkt bauen** (`f"/iolinkmaster/port[{port}]/mode"`), nicht über `port_path()`.

**Neues Modul `custom_components/ifm_iolink/port_mode.py`** (Geschwistermodul zu `restore.py`)
- `prepare_mode_change(coordinator, port, target_mode)`: liest aktuellen Modus + Portidentität, warnt falls aktuell ein IO-Link-Gerät verbunden ist (`connected`), baut ein reines Vorschau-Dict `{port, current_mode, target_mode, device_connected, assignment_name, profile_id}`. Keine Schreibzugriffe – Vorbild: `prepare_restore` in `restore.py`.
- `execute_mode_change(coordinator, port, plan, record, still_current)`: prüft `still_current()` + unveränderten Zustand seit Vorschau erneut, ruft `coordinator.client.write_port_mode(...)`, liest zurück zur Bestätigung, invalidiert `coordinator.metadata_at = 0` (erzwingt sofortigen Metadaten-Refresh) und räumt `coordinator.condition_values` für den Port auf. Vorbild: `execute_restore` in `restore.py`.

**`custom_components/ifm_iolink/websocket.py`**
- Zwei neue Commands, registriert in `register_commands()`: `ifm_iolink/preview_port_mode` und `ifm_iolink/set_port_mode`.
- Beide nutzen **denselben** `hass.data[DOMAIN]["parameter_backups"].busy`-Set und dieselbe `backups.plans`-Token-Struktur wie `preview_restore`/`restore_parameters` – 1:1 dasselbe Muster (Token via `secrets.token_urlsafe(24)`, 300 s TTL, an `connection.user.id` + `(entry_id, port)` + Coordinator-Objektidentität gebunden, Single-Use-Pop vor Ausführung). Dadurch blockieren sich Parameter-Restore und Moduswechsel am selben Port automatisch gegenseitig.
- `assign` prüft bereits `busy` vor einer Profilzuweisung – das greift unverändert auch während eines laufenden Moduswechsels.
- Nach erfolgreichem `set_port_mode`: `hass.config_entries.async_update_entry(...)` schreibt `entry.options["ports"][port]["mode"]` (neuer Schlüssel neben `profile`/`name`/`location`/`purpose`/`entities`, Default beim Fehlen: `3` = IO-Link). Wechselt ein Port in den DO-Modus (`2`), sollte `profile` dabei auf `"unknown"` zurückgesetzt werden (ein IO-Link-Profil kann keine DO-Prozessdaten decodieren).

**Neues `custom_components/ifm_iolink/switch.py`** (neue Plattform)
- `const.py` – `PLATFORMS` um `"switch"` erweitern.
- Eine Entity **nur für Ports, deren `mode == 2`** (DO, aus `entry.options["ports"][port]["mode"]`): `IfmPin4Switch(IfmEntity, SwitchEntity)`, liest/schreibt den reinen Ausgangszustand über `/iolinkmaster/port[X]/iolinkdevice/pdout` (Hex-String – Struktur bestätigt, exakte Bit-/Byte-Kodierung für den DO-Fall vor der Implementierung noch an einem Port mit `mode=DO` gegenlesen). Das ist die einzige Stelle, an der eine normale, automatisierbare HA-Entity entsteht – der Moduswechsel selbst bleibt Panel-only.
- `__init__.py`s erwartete-`unique_id`-Menge um `prefix + "pin4_do"` erweitern, aber **nur** wenn `mode == 2`, sonst greift die Aufräumlogik korrekt und entfernt das Switch-Entity, sobald ein Port zurück auf IO-Link umgeschaltet wird.

**Frontend (`custom_components/ifm_iolink/frontend/panel.js`)**
- Im Inspector (Bereich analog zu „Sensortausch & Sicherung“) ein neues `<details>` „Portmodus“ mit: aktuellem Modus, einer Auswahl (IO-Link / Digitalausgang), einem Hinweistext bei aktuell verbundenem Sensor, und demselben Vorschau→Bestätigen-Dialogmuster wie `previewRestore()` – neue Methode `previewPortMode()` ruft `preview_port_mode`, öffnet einen `<dialog>` mit Warnung + Checkbox-Bestätigung, ruft bei Bestätigung `set_port_mode`.

## Stand nach 0.5.0

Umgesetzt gegenüber dem ursprünglichen Plan oben, mit zwei bewussten Abweichungen:

- **Kein Whitelist-Eintrag für einen einzelnen `mode`-Lesepfad in `api.py`.** Sowohl der 60-Sekunden-Metadaten-Read im Coordinator als auch der frische Kontroll-Read direkt vor/nach dem Schreiben in `port_mode.py` laufen über `client.multi([...])` (genau wie `read_identity` in `parameters.py`), nicht über einen einzelnen `request()`-Aufruf. `client.multi()` ruft intern `/getdatamulti` auf, das schon in der Whitelist steht; die Pfade *innerhalb* von `datatosend` werden von `request()` gar nicht geprüft. Eine Erweiterung der Whitelist wäre also wirkungslos gewesen. `write_port_mode()` bleibt wie geplant komplett außerhalb von `request()` (eigene Methode, wie `write_parameter()`).
- **Kein separates `record`-Argument bei `execute_mode_change()`.** Anders als `execute_restore` (viele Einzelschritte, die bei einem Absturz mitten im Vorgang einen Fortschrittsbericht brauchen) ist ein Moduswechsel ein einziger atomarer Schreib+Rücklese-Schritt. Es gibt daher keinen Zwischenzustand, der persistiert werden müsste, und keinen `get_port_mode_report`-Websocket-Command.

Token-Kollisionen zwischen Restore- und Portmodus-Vorschauen (beide nutzen denselben `backups.plans`-Dict) werden dadurch verhindert, dass Restore-Pläne unter dem Schlüssel `"plan"` und Portmodus-Pläne unter `"mode_plan"` abgelegt werden; `restore_parameters`/`set_port_mode` prüfen jeweils, dass der passende Schlüssel im gefundenen Token-Eintrag existiert, bevor sie ihn verwenden.

Ausgewählte Ziel-Modi sind im Backend (`port_mode.SWITCHABLE_MODES`) und im Panel bewusst auf `{2, 3}` (Digitalausgang/IO-Link) beschränkt – Disabled/DI sind zwar über `write_port_mode()` technisch erreichbar (API-Validierung erlaubt `{0,1,2,3}`), aber nicht Teil des hier abgedeckten Anwendungsfalls.

Im Panel gibt es dafür keine Dropdown-Auswahl (wie ursprünglich skizziert), sondern einen einzelnen Umschalt-Button, der immer auf den jeweils *anderen* der beiden Modi zeigt („Zu IO-Link wechseln …“ bzw. „Zu Digitalausgang wechseln …“) – einfacher als eine Auswahl, aus der man auch den bereits aktiven Modus wählen könnte.

**`pdout`-Byteformat verifiziert (2026-09-15, gegen echten AL1352 unter 192.168.1.22, Port 7/X07, unbenutzt/`status=0`, mit Zustimmung des Nutzers testweise auf DO geschaltet und danach zurück auf IO-Link):**

- Pfad ist ganz normal unter `iolinkdevice`, anders als `pin2in`/`mode`: `port_path(port, "pdout")` liefert korrekt `/iolinkmaster/port[X]/iolinkdevice/pdout` – **hier darf/muss `port_path()` verwendet werden.**
- Solange der Port nicht im DO-Modus ist, liefert `getdata` auf `pdout` einen Fehlercode (503); direkt nach dem Wechsel auf DO, aber vor dem ersten Schreiben, einen anderen Fehlercode (530, vermutlich „noch kein Wert gesetzt“).
- `setdata` mit `{"newvalue": "01"}` bzw. `{"newvalue": "00"}` funktioniert wie erwartet und wird per `getdata` unverändert zurückgelesen (1-Byte-Hex-String, gleiche Konvention wie `write_parameter`).
- Der Master validiert den Wert nicht als striktes Boolean: `"FF"` wird ebenso akzeptiert und unverändert zurückgelesen; ein zu langer Wert (`"0001"`) wird ohne Fehler auf das erste Byte gekürzt (Rücklesewert `"00"`). Die Implementierung schreibt daher ausschließlich `"01"`/`"00"` und liest beim Anzeigen defensiv „ein/aus“ als `raw != "00"`, statt strikt auf `"01"` zu vergleichen.
- Die physische Ausgangswirkung (tatsächlicher Pegel an Pin 4) wurde nicht mit einem Multimeter nachgemessen, nur die IoT-Core-Registerebene. Sollte ein Nutzer eine Abweichung zwischen `switch`-Zustand und realem Pegel melden, hier zuerst nachsehen.

Umgesetzt: `IfmClient.write_port_output()` in `api.py`, `pdout`-Read im Coordinator (nur für Ports mit gespeichertem `mode == 2`, um den sonst garantierten Fehlercode für IO-Link-Ports zu vermeiden), `switch.py` mit `IfmPin4Switch`, `PLATFORMS` in `const.py` um `"switch"` erweitert, erwartete-`unique_id`-Menge in `__init__.py` um `prefix + "pin4_do"` (nur bei `mode == 2`).

## Verifikation

1. `python -m pytest -q` (bestehende Suite darf nicht brechen – v. a. `tests/test_coordinator.py`, `tests/test_websocket.py`, `tests/test_api.py`, die um Tests für `write_port_mode`, `preview_port_mode`/`set_port_mode` und die `switch`-Plattform zu ergänzen sind).
2. `node --check custom_components/ifm_iolink/frontend/panel.js` nach jeder Panel-Änderung.
3. `python -m ruff check custom_components tests scripts` und `python -m compileall -q custom_components`.
4. Vor der `switch.py`-Implementierung noch das exakte `pdout`-Byteformat für den DO-Fall an einem Port mit `mode=DO` gegenlesen (z. B. Ausgang manuell schalten und `pdout` per `getdata` beobachten).
5. Manueller Test im Command Center (`scripts/preview.py` für UI-Layout, echter Master für Funktionstest): Portmodus-Wechsel eines Test-Ports zu DO, Ausgang per neuem `switch`-Entity schalten, zurück zu IO-Link wechseln und prüfen, dass der ursprüngliche Sensor wieder erkannt wird.
