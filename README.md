# SIMon mobile für Home Assistant

Inoffizielle Home-Assistant-Custom-Integration für das SIMon-mobile-Kundenportal.

> [!IMPORTANT]
> Diese Integration steht in keiner Verbindung zu SIMon mobile oder Vodafone.
> Sie verwendet eine nicht öffentlich dokumentierte Cloud-API, die sich jederzeit
> ändern kann.

## Funktionen

- Einrichtung vollständig über die Home-Assistant-Oberfläche
- automatischer Access-Token-Refresh
- Aktualisierung alle 15 Minuten
- gesamtes, verbrauchtes und verbleibendes Datenvolumen
- prozentualer Datenverbrauch
- nächstes Ablaufdatum eines Datenpakets
- verbleibende SMS, sofern von SIMon bereitgestellt
- einzelne Tarif- und Optionskontingente als standardmäßig deaktivierte Sensoren
- Unterstützung mehrerer SIMon-Konten
- Reauthentifizierung bei abgelaufenen oder geänderten Zugangsdaten
- Diagnoseausgabe ohne Mobilfunknummer, Passwort oder Tokens

## Einschränkungen

- Konten mit aktivierter mTAN/MFA werden erkannt, aber noch nicht unterstützt.
- SIMon stellt keine öffentliche API-Dokumentation bereit.
- Telefonminuten werden bei einer Flatrate offenbar nicht über die Verbrauchsabfrage geliefert.

## Installation zum Testen

1. Den Ordner `custom_components/simon_mobile` nach
   `/config/custom_components/simon_mobile` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen.
4. Nach **SIMon mobile** suchen.
5. Mobilfunknummer und Kundenpasswort eingeben.

Die Mobilfunknummer kann als `0152…`, `49152…` oder `+49152…` eingegeben werden.

## Installation über HACS

HACS installiert Custom-Integrationen aus einem öffentlichen GitHub-Repository.
Nach dem Hochladen dieses Projekts in ein Repository:

1. In `custom_components/simon_mobile/manifest.json` den Platzhalter `OWNER`
   durch deinen GitHub-Benutzernamen ersetzen.

2. HACS öffnen.
3. **Integrationen → Drei-Punkte-Menü → Benutzerdefinierte Repositories**.
4. URL des Repositorys eintragen.
5. Kategorie **Integration** wählen.
6. **SIMon mobile** herunterladen und Home Assistant neu starten.

## Entitäten

| Entität | Standard |
| --- | --- |
| Datenvolumen gesamt | aktiviert |
| Datenvolumen verbraucht | aktiviert |
| Datenvolumen verbleibend | aktiviert |
| Datenverbrauch | aktiviert |
| Nächster Ablauf | aktiviert |
| SMS verbleibend | aktiviert, sofern vorhanden |
| Einzelnes Tarif-/Optionskontingent | deaktiviert |

Einzelne Kontingente können in den Geräteeinstellungen manuell aktiviert werden.
Die Aufschlüsselung aller Datenpakete steht zusätzlich als Attribut am Sensor
**Datenvolumen gesamt** zur Verfügung.

## Datenschutz und Sicherheit

- Access- und Refresh-Tokens werden ausschließlich im Arbeitsspeicher gehalten.
- Nach einem Neustart meldet sich die Integration neu an.
- Home Assistant speichert Mobilfunknummer und Passwort im Config Entry.
- Diagnosedaten entfernen Mobilfunknummer und Passwort.
- Verwende ein aktuelles Home Assistant und sichere den Zugriff auf Backups und
  das `/config`-Verzeichnis.

## Haftung

Die Nutzung erfolgt auf eigene Verantwortung. Zu häufige fehlgeschlagene
Anmeldeversuche können zu einer temporären Kontosperre führen.
