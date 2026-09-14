# Geräteprofile

Ein Profil ist eine JSON-Datenbeschreibung. Es wird weder mit `eval` noch als Python oder JavaScript ausgeführt. Geräteinformationen und Übersetzung gelten für den Gerätetyp; Standort, Bezeichnung und Zweck lassen sich je angeschlossenem Port überschreiben.

```json
{
  "id": "custom_drucksensor",
  "name": "Mein Drucksensor",
  "manufacturer": "Hersteller",
  "model": "Modell",
  "description": "Geräteinformationen",
  "purpose": "Filterüberwachung",
  "image": "/local/mein-sensor.png",
  "notes": "Skalierung anhand der Herstellerdatei prüfen",
  "length": 4,
  "match": [{"vendorid": 310, "deviceid": 602}],
  "fields": [
    {"key": "pressure", "name": "Druck", "type": "int", "offset": 0,
     "length": 2, "scale": 0.0001, "unit": "bar", "device_class": "pressure",
     "state_class": "measurement", "precision": 4,
     "invalid_values": [-32760, 32760, 32764]},
    {"key": "out1", "name": "OUT1", "type": "bool", "offset": 3,
     "length": 1, "shift": 0, "bits": 1}
  ]
}
```

- `length`: exakte erwartete PDIN-Länge, 1–32 Byte. Eine abweichende Länge führt zu „nicht verfügbar“ statt zu einer geratenen Interpretation.
- `offset`: Byteposition ab Anfang des vom Master gelieferten Hex-Strings, ab 0.
- `type`: `uint`, `int`, `float32`, `float64` oder `bool`; `endian` ist standardmäßig `big`.
- Ganzzahlen: zuerst nach rechts um `shift` verschieben, dann `bits` auswählen. `int` interpretiert das Vorzeichen innerhalb dieser Bitbreite.
- Messwert = Rohwert × `scale` + `add`. `precision` begrenzt die Nachkommastellen. Float-Werte müssen vollständige Bytes belegen.
- `invalid_values`: numerische Sonderwerte, die nicht als Messung ausgegeben werden. `invalid_when: {"offset": 21, "mask": 4}` sperrt das Feld, wenn das angegebene Statusbit gesetzt ist.
- Für binäre Sammelmeldungen kann `mask` mehrere Bits verknüpfen. Beispiel: `mask: 2031` entspricht dem bestehenden BADU-Node-RED-ODER der Bits 0–3 und 5–10.
- `match`: optionaler Schutz gegen falsche Gerätekennungen. Leere Liste erlaubt manuelle generische Profile. Ein Import übernimmt nur die primäre aktive Device-ID; Kompatibilitäts-IDs gelten nicht automatisch für dasselbe Layout.
- `conditions`: optionale Liste aus `{"index": 64, "value": 0}`. Der Index wird über IO-Link nur gelesen; ein abweichender Wert sperrt die Dekodierung.
- `parameters`: optionale herstellerspezifische Parameterliste mit Index, Name, Beschreibung und bei unterstützten Typen einem eigenen Decoder. Werte werden im Panel gezielt einzeln gelesen; komplexe Records bleiben als Rohwert zugänglich.

## Parameter als Home-Assistant-Entity

Unter **Parameterliste anzeigen** lässt sich je Port pro Parameter eine Checkbox aktivieren, um ihn als eigene Entity anzulegen; **Auswahl als Entity speichern** persistiert die Auswahl und lädt den Master neu. Ein Parameter mit `access: "rw"` und einem Decoder aus genau einem vollen Byte-Feld vom Typ `uint`/`int` (kein `shift`/Teil-Byte) wird zu einer `number`-Entity, die sich aus Home Assistant heraus setzen lässt; alle übrigen Parameter (Nur-Lese-Zugriff, `StringT`, `RecordT`, `ArrayT` oder Teil-Byte-Felder) werden zu einer nur lesenden `sensor`-Entity. Beide lesen den Wert per acyclic Read (`iolreadacyclic`) unabhängig vom schnellen Prozessdaten-Poll: beim Hinzufügen, nach jedem Schreibvorgang und danach stündlich. Ändert sich das zugewiesene Profil eines Ports, wird die Auswahl zurückgesetzt, da Parameterindizes profilspezifisch sind.

Im ZIP enthaltene PNG/JPEG-Bilder werden als lokale Daten-URL gespeichert. Alternativ: HTTPS-URL, `/local/`-Pfad oder PNG/JPEG/WebP-Upload. Eigene Profil-IDs beginnen mit `custom_`. Mitgelieferte Profile werden im Editor als eigene Kopie geöffnet.

## Unbekanntes Gerät

Im Port „Unbekannt“ auswählen und speichern oder **Debug-Datei** klicken. Der Export enthält Gerätekennungen, bis zu 30 zeitgestempelte PDIN-Proben, Antwortcodes und eine Profilvorlage. Netzwerkadresse, Zugangsdaten, Seriennummern und Standorttexte aus der Konfiguration werden nicht ausgegeben. Frei eingegebene Texte in eigenen Profilen sollten vor Weitergabe zusätzlich geprüft werden.

Die Datei kann zusammen mit der IODD einem Assistenten zur Profilentwicklung gegeben werden. Eine Bitfolge allein belegt weder Einheit noch Skalierung. Ein erzeugtes JSON-Profil im Editor einfügen, mit Rohwerten testen und speichern.

## Grenzen des automatischen Imports

Die IODD beschreibt mögliche Formate und Gerätevarianten. Manche Geräte wählen Format, Einheiten oder Wertebedeutungen über Laufzeitparameter. Solche Bedingungen müssen berücksichtigt werden; gleiche Paketlänge bedeutet nicht gleiches Format. Der Import priorisiert direkte, layoutspezifische Prozessdatendefinitionen. Bei dynamischen Menüs wird keine beliebige Einheit aus der ersten gefundenen Darstellung übernommen. Fehlende Einheiten und nicht unterstützte Felder werden in der Vorschau angezeigt.

Der Import führt keine Fremdskripte aus, extrahiert keine ZIP-Pfade auf das Dateisystem und akzeptiert keine DTD-/Entity-Deklarationen. Es gelten Größen-, Feld- und Dateianzahlgrenzen.
