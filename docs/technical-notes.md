# Technische Details

## Mitgelieferte Geräte

| Profil | Kennung | Prozessdaten | Grundlage |
|---|---|---|---|
| PN7094 Status B | Vendor 310 / Device 601 | 4 Byte; Druck × 0,001 bar, Gerätestatus, OUT1/OUT2 | bereitgestellte ifm-IODD |
| PN7096 Status B | Vendor 310 / Device 602 | 4 Byte; Druck × 0,0001 bar, Gerätestatus, OUT1/OUT2 | bereitgestellte ifm-IODD |
| PN7094 Default | Vendor 310 / Device 403 | 2 Byte; signed 14 Bit × 0,01 bar, OUT1/OUT2 | bereitgestellte ifm-IODD |
| PN7096 Default | Vendor 310 / Device 404 | 2 Byte; signed 14 Bit × 0,01 bar, OUT1/OUT2 | bereitgestellte ifm-IODD |
| BADU FlowSonic Plus | Vendor 839 / Device 1599537 (`0x186831`) | 22 Byte; Durchfluss, Temperatur, zwei Zähler, Status | vom Nutzer bestätigter Node-RED-Flow; Format/Einheiten am Gerät ausgelesen |

Die ifm-Originalbilder stammen aus den bereitgestellten IODDs. Das BADU-Profil verwendet das vom Nutzer bereitgestellte Bild des tatsächlichen FlowSonic Plus. Die Masterbilder wurden vom Nutzer bereitgestellt.

### BADU: bestehende Übersetzung hat Vorrang

Die bestätigte Node-RED-Zuordnung bleibt erhalten, auch für Leerrohr, Luftblasen, Charge, Fehler und die Sammelmeldung „Systemfehler“. Die Sammelmeldung bildet wie im Flow das logische ODER der dort überwachten Statusflags und enthält deshalb auch Aktivitäts-/Grenzwertmeldungen. Das verwandte JUMO-IODD-Archiv von 2022 enthält die tatsächliche BADU-ID `0x186831` **nicht** und verwendet teilweise andere Statuspositionen. Es ersetzt das bestehende BADU-Profil deshalb nicht automatisch.

Am tatsächlichen Gerät gelesen: Index 64 = 0 (Float), 121 = 4 (m³/h), 123 = 2 (m³). Diese Bedingungen werden nach Einrichtung und periodisch geprüft. Bytes 8–11 bleiben zusätzlich als Rohwort sichtbar. Der Tageswert „Gefiltertes Wasservolumen heute“ ist ein abgeleiteter Home-Assistant-Verbrauchszähler, kein eigener IO-Link-Prozesswert. Ein vorhandener Tageszähler kann auf den neuen Summenzähler umgestellt werden.

## Neue Geräte über IODD

1. **ifm IO-Link → Gerätebibliothek → IODD importieren** (Upload bis 2 MB).
2. Hersteller-ZIP/XML wählen. Bei mehreren Modellen die Variante anhand ihrer Geräte-ID und des Prozessdatenlayouts auswählen.
3. Importhinweise prüfen. Statische ifm-Prozesswerte werden vollständig übernommen. Bedingte Formate werden über ihren Parameterindex geprüft; dynamische Einheiten bleiben ausdrücklich unbeschriftet, wenn sie nicht eindeutig aus den statischen Angaben hervorgehen.
4. Optional Namen, Zweck, Bild und Informationen ergänzen. Einen aktuellen Rohwert mit **Übersetzung testen** prüfen.
5. Speichern und das Profil anschließend an beliebig vielen passenden Ports auswählen.

**Importumfang:** IODD 1.1, Ganzzahlen, Bool, IEEE-754-Floats, einfache Records, Datentypreferenzen, Bitpositionen, statische Skalierungen, ausgewählte Standardeinheiten, Bilder und explizite Herstellerparameter. Nicht unterstützte Datentypen/Einheiten und bedingte Darstellungen werden angezeigt. Dies ist kein vollständiger IODD-Interpreter für jeden Sensor am Markt. Geräteeinstellungen werden nicht automatisch geschrieben. XML allein enthält keine Bilddateien; dafür das vollständige ZIP verwenden.

## Betrieb

- Standardintervall 2 Sekunden; pro Master in den Integrationsoptionen einstellbar. Requests sind serialisiert.
- Portstatus und PDIN werden zyklisch gelesen; Identifikation und Profilbedingungen spätestens alle 60 Sekunden. Eine Änderung von Gerätemodus oder Einheit am Sensor kann daher bis zu diesem nächsten Abgleich brauchen.
- Lokale Netzsuche bis 1024 IPv4-Adressen, maximal 24 gleichzeitige Prüfungen. VLANs werden nicht automatisch überbrückt. Bei aktiviertem Security Mode manuell per HTTPS einrichten.
- Zugangsdaten nur bei Bedarf; Passwortzugriffe erfordern HTTPS. TLS-Prüfung ist standardmäßig an und kann für eigene Gerätezertifikate explizit deaktiviert werden.
- Profilverwaltung, Portzuweisung und Debug-Export benötigen einen Home-Assistant-Administrator.
- Eigene Profile liegen in Home Assistants `.storage/ifm_iolink.profiles`, Portzuweisungen in den Config-Entry-Optionen. Zusätzlich liegen Parametersicherungen in `.storage/ifm_iolink.parameter_backups`. Alle gehören in das normale HA-Backup.
- Bei Profilwechsel entfernt die Integration die alten, nicht mehr passenden Entitätsregistrierungen dieses Ports. Automationen, die auf solche Entitäten zeigen, müssen entsprechend angepasst werden.


## Sensortausch und Parametersicherung

Ab Version 0.1.3 kann eine vollständige Parametersicherung am Port oder aus einer JSON-Datei zurückgespielt werden. Auch Sicherungen aus 0.1.2 sind nach Prüfung verwendbar. Unter **Parameterliste anzeigen** steht die Zusatzüberschrift **Alle Gerätedaten lesen** mit einem kleinen **Lesen**-Button und dem Erklärungstext darunter. **Sensortausch & Sicherung** enthält Sicherungsaktionen, Zeitstempel und Restore-Protokoll.

Vor dem Schreiben zeigt eine Vorschau aktuelle und gesicherte Rohwerte. Hersteller-/Gerätekennung, Profil, Datenlängen und Seriennummer des Zielgeräts werden geprüft; die Seriennummer darf von der des alten Sensors abweichen. Nur unterstützte `rw`-Parameter aus dem zugewiesenen Profil werden übertragen, keine Nur-Lese-Werte oder Systembefehle. Unveränderte Werte werden nicht geschrieben. Jede Änderung wird zurückgelesen. Bei einem Fehler stoppt der Vorgang ohne automatische Wiederholung oder Rollback; das dauerhafte Protokoll enthält ursprüngliche Werte, bestätigte Änderungen und einen eventuell unbestätigten Schreibzugriff. Eine Vorschau gilt fünf Minuten, einmalig und nur für den bestätigenden Administrator und Zielport.

Herstellerparameter sind nur soweit vollständig, wie sie im Profil enthalten sind; beim BADU sind derzeit die drei verifizierten Format-/Einheitenindizes hinterlegt. Bei numerischen und strukturierten Parametern müssen Datenlängen übereinstimmen. Textkennzeichen dürfen unterschiedlich lang oder leer sein. Geänderte Profile benötigen eine passende Sicherung. Diese Funktion ersetzt keine vollständige IODD-Parameterverwaltung und aktiviert kein Data Storage im Master.

Der ifm-Master unterstützt selbst IO-Link Data Storage mit **Backup + Restore**: Bei passender Portkonfiguration werden Parameter gespeichert und an ein baugleiches IO-Link-1.1-Ersatzgerät im Auslieferungszustand übertragen. Vendor-ID und Device-ID müssen passen. Das ist eine eigene Funktion des Masters, die dieses Update nicht aktiviert oder verändert. Siehe [ifm-Betriebsanleitung AL1350, Kapitel Gerätevalidierung/Datenspeicherung und Sensortausch](https://www.quicktimeonline.com/assets/images/pdf/IFM%20Electronic/operating-instruction-AL1350.pdf).

Der Schreibzugriff nutzt `iolwriteacyclic` mit Index, Subindex 0 und Hexwert gemäß [ifm IoT-Core-Anleitung](https://www.ifm.com/mounting/80284138UK.pdf). Bei den PN-Profilen werden Schalt-/Rückschaltpunkte abhängig von den aktuellen Grenzen geordnet und die Bedienverriegelung zuletzt angewandt. Gerätespezifische Abhängigkeiten anderer Profile können eine Übertragung ablehnen; dann zeigt das Protokoll den erreichten Stand.
