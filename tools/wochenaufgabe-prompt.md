# Wöchentliche Wartung – Auftrag für die lokale Sitzung (Claude-Desktop-App)

## Einrichtung (einmalig, in der lokalen Sitzung ausführen)

1. Falls `~/sitecheck-berichte` noch nicht existiert: `git clone https://github.com/sitecheck-ch/sitecheck-berichte.git ~/sitecheck-berichte`. Sonst dort `git pull --ff-only` auf `main`.
2. `mkdir -p ~/sitecheck && cp ~/sitecheck-berichte/tools/sitecheck.py ~/sitecheck/sitecheck.py`
3. `pip install requests beautifulsoup4` (bzw. `python3 -m pip install requests beautifulsoup4`)
4. In `~/sitecheck-berichte`: `git push --dry-run origin main` ausführen. Schlägt das fehl (Anmeldung/Rechte), abbrechen und mir genau melden, was fehlt. Nichts selbst an den Zugangsdaten ändern.
5. Eine geplante Aufgabe anlegen: wöchentlich Montag 08:00, Zeitzone Europe/Zurich, Arbeitsordner `~/sitecheck-berichte`, Auftragstext = der gesamte Abschnitt „Wöchentlicher Auftrag“ unten. Der eingebaute Browser, `python3` und `git` müssen ohne Rückfrage laufen dürfen.
6. Die Aufgabe einmal sofort testweise ausführen und mir das Ergebnis zeigen (Zusammenfassung und geänderte data.json-Einträge).

## Wöchentlicher Auftrag

Wöchentliche Wartung der Kundenwebsites (Montag 08:00, Europe/Zurich). Arbeitsordner: ~/sitecheck-berichte (lokaler Klon von sitecheck-ch/sitecheck-berichte). Prüfskript: ~/sitecheck/sitecheck.py (Python 3 mit requests und beautifulsoup4).

Websites:
- sabix: öffentlich https://www.sabix.ch, Backend https://www.sabix.ch/wp-admin, data.json: sabix-265cce3007/data.json
- newimmohouse: öffentlich https://newimmohouse.ch, Backend https://newimmohouse.ch/wp-admin, data.json: newimmohouse-59266d88c0/data.json

Feste Regeln:
- Im Backend nur den eingebauten Browser benutzen, in dem ich dauerhaft angemeldet bin. Nie ein Passwort eingeben. Ist eine Anmeldung nötig, Website abbrechen, backup = "Fehler", Status mindestens "Achtung", mich benachrichtigen.
- Nie Formulare absenden (Kontakt, Anmeldung, Einstellungen). Erlaubt sind nur diese Aktionen: UpdraftPlus "Jetzt sichern" (Standardoptionen: Datenbank + Dateien), die erlaubten Plugin-Updates und der Rollback bei Fehlern.
- Interne Details (offene Updates, Fehlermeldungen, URLs) kommen NIE in data.json, sondern nur in die Zusammenfassung am Ende des Laufs.

0. Vorbereitung: git pull --ff-only auf main.

Für jede Website nacheinander:
1. Öffentliche Prüfung: python3 ~/sitecheck/sitecheck.py <site>. Ergebnis als "vorher" merken.
2. Backup: wp-admin > Einstellungen > UpdraftPlus-Backups > "Jetzt sichern". Abwarten, bis das Backup fertig ist und in der Liste der vorhandenen Backups erscheint (höchstens 30 Minuten, zwischendurch prüfen). Klappt das: backup = "OK". Sonst backup = "Fehler" und KEINE Updates installieren.
3. Updates (nur mit erfolgreichem Backup), unter Dashboard > Aktualisierungen bzw. Plugins:
   - Automatisch installieren: Patch-Updates, also nur die dritte Versionsstelle ändert sich (x.y.Z, z. B. 3.25.4 > 3.25.5), auch bei Elementor/Elementor Pro. Ausserdem jedes Update von Akismet, Loco Translate, Code Snippets, Duplicate Page und Better Search Replace.
   - Nur melden, nicht installieren: alle Minor-/Major-Updates, Themes, WordPress-Core, Yoast SEO, UpdraftPlus, Formular-Plugins (z. B. Contact Form 7), Cookie-Plugins und Bold Page Builder. Bei Unklarheit: nur melden.
   - Bei jedem installierten Update vorher die alte Versionsnummer notieren.
4. Nach den Updates: Schritt 1 wiederholen ("nachher"). Ist "nachher" schlechter als "vorher" (eine Seite nicht erreichbar, Formular nicht OK, mehr defekte Links):
   - Elementor: Elementor > Werkzeuge > Versionskontrolle > Rollback auf die notierte Version, danach erneut prüfen.
   - Andere Plugins: keinen Rollback auf eigene Faust (kein Wiederherstellen aus UpdraftPlus). Nur melden.
   - Ist die Verschlechterung durch Updates entstanden, ist der Status in jedem Fall "Fehler".
5. Eintrag für data.json mit date = heutiges Datum (YYYY-MM-DD, Europe/Zurich). pages_ok, pages_total, links_broken, form und resp_ms kommen aus der letzten Prüfung.
   - Status: "Fehler", wenn eine Seite nicht erreichbar ist, das Formular nicht antwortet oder Updates einen Fehler verursacht haben. Sonst "Achtung", wenn links_broken > 0, resp_ms > 2500 oder backup = "Fehler". Sonst "In Ordnung".
   - client_note: 1-2 kurze, sachliche deutsche Sätze für den Kunden, ohne Technik-Details und Plugin-Namen. Nichts verschweigen. Bei Achtung/Fehler neutral formulieren, dass wir es prüfen. Beispiel "In Ordnung": "Sicherung erstellt und Aktualisierungen eingespielt. Alle Seiten erreichbar, Kontaktformular funktioniert." Beispiel "Achtung": "Alle Seiten sind erreichbar. Ein Verweis auf der Website funktioniert nicht, wir prüfen das und beheben es."
   - Schreiben: python3 ~/sitecheck/sitecheck.py write <ordner>/data.json '<eintrag-json>'. Das ersetzt einen bestehenden Eintrag mit gleichem Datum.

6. Danach: nur die beiden data.json-Dateien stagen, Commit "Wochenlauf YYYY-MM-DD", git push origin main. Schlägt der Push fehl: einmal git pull --rebase und erneut pushen; scheitert es wieder, mich benachrichtigen.
7. Zusammenfassung für mich (nicht in data.json): je Website die Status vorher/nachher, Backup, installierte Updates (alt > neu), offene Updates, die nur gemeldet werden, Rollbacks und defekte URLs. Eine Push-Benachrichtigung nur, wenn eine Website "Achtung" oder "Fehler" hat oder der Push gescheitert ist.
