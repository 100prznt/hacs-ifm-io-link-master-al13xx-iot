# Prüfstand der öffentlichen Testversion 0.1.3

## Automatisierte Prüfungen

150 Tests prüfen Dekodierung, IODD-Import, API-Kommunikation, Coordinator-Verhalten, Parametersicherungen und Wiederherstellung. Die Home-Assistant-WebSocket-Decorator-/Task-Grenze wird simuliert; dies ist kein vollständiger Home-Assistant-Core-Testlauf.

- Prozessdaten der PN-Profile sowie die bestätigte BADU-Übersetzung.
- IODD-Varianten, Bilder, unterstützte Datentypen und Importgrenzen.
- API-Fehler, Serialisierung und Schreibtransport gegen einen lokalen HTTP-Testserver.
- Unpassende und unvollständige Sicherungen, ungültige Hexwerte, abweichende Datenlängen.
- Geräte-/Profilwechsel und veränderte Werte zwischen Vorschau und Ausführung.
- Administratorrechte, Benutzer-/Portbindung, Ablauf und einmalige Verwendung der Vorschau.
- Schreibfehler, Rücklesefehler, persistierter Fortschritt und Abbruch ohne automatische Wiederholung.
- PN-Schalt-/Rückschaltpunkte in beiden Änderungsrichtungen; variable Textkennzeichen.

Zusätzlich: Ruff, Python-Kompilierung und JavaScript-Syntaxprüfung. Der Workflow `tests.yml` führt die Prüfungen bei Push und Pull Request aus.

## Reale Anlage

Getestet mit Home Assistant 2026.8.3 auf einer Entwicklungsinstanz:

- Zwei AL1350 mit insgesamt vier Ports je Master eingerichtet.
- PN7094 Status B an drei Druckluft-Messstellen.
- PN7096 Status B für Poolfilter und Heizkreis.
- BADU FlowSonic Plus mit bestätigtem Float-Format, Durchfluss in m³/h und Zählern in m³.
- Prozesswerte, Portzuordnung, Gerätebibliothek und grafische Übersicht geprüft.
- Sammelabfrage: je 27 Profilparameter für PN7094/PN7096; drei Parameter für BADU.
- Vollständige Port-Sicherungen angelegt und nach erneutem Öffnen angezeigt.
- PN7094-Wiederherstellung aus einer bestehenden Sicherung: 21 unveränderte schreibbare Parameter geprüft, sechs Lesewerte ausgelassen, null Schreibzugriffe; Protokoll gespeichert und erneut angezeigt.
- Mastername gespeichert; echte Masterlöschung nicht an der Anlage getestet.
- Menüstruktur, identische Buttongrößen, JSON-Dateiupload und Vorschau im Browser geprüft. Wiederherstellung mit geänderten Werten in der Demo simuliert.
- Updates mit Sicherung der vorherigen Dateien und erfolgreichem `ha core check`; Live-Messwerte und Portzuordnungen anschließend vorhanden.

## Noch nicht an realer Hardware geprüft

AL1352, PN-Default-Varianten, tatsächliches Zurückschreiben geänderter Sensorwerte und physischer Sensortausch. Unterstützung weiterer IODDs hängt von deren Datenformaten ab. Nicht unterstützte Angaben werden als Importhinweise ausgegeben.

Die Integration liefert Entitäten. Pool-Wintersteuerung, Filterverschmutzungsbewertung, Heizungs- und Druckluftalarme sind anlagenspezifische Home-Assistant-Automationen und nicht Teil des getesteten Integrationsumfangs.
