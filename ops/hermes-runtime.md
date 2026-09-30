# Hermes-Laufzeitvertrag für das AI-Briefing

Die Pipeline nutzt die zehn gleichzeitig zulässigen Hermes-Kind-Agenten. Bei 41
Pflichtquellen entstehen fünf Pakete plus Discovery: ein gemeinsamer Batch.
Weitere Quellen erzeugen automatisch weitere Pakete, ohne Quellen wegzulassen.
Suchbudget 35 je Recherche-Agent und Hermes-Schutzlimit 50 bleiben unverändert.

Hermes-Cron unterstützt keine verlässlich zustellbare asynchrone Delegation und
fällt auf synchrone Batches zurück. Der allgemeine 420-Sekunden-Tool-Wächter
unterbricht diese sonst vor dem Ende der Kinder. Verwende die unterstützte,
persistente Konfiguration aus `ops/hermes-runtime.yaml` in `/opt/data/config.yaml`:
beide Tool-Executor-Fristen sind 1800 Sekunden, nicht unbegrenzt. Diese Werte gelten
für das Default-Profil einschließlich seiner anderen Jobs; spezifische HTTP-/Terminal-
Fristen, Approval-Regeln und Suchbudgets werden nicht geändert. Es gibt keinen Patch
im Hermes-Installationsverzeichnis, der bei einem Update verloren gehen könnte.

Der Cron-Prompt hat eine einzige versionierte Vorlage:
`ops/ai-briefing-cron-prompt.txt`. Für Job `a4f79267477a` wird sie über `hermes cron
edit --prompt` eingespielt; Zeitplan, Modell, Skills und Zustellung bleiben erhalten.
Die Berliner Gate-Datei `ai-briefing-berlin-gate.py` lässt nur den Lauf um 08:00 Uhr zu.

## Deployment und Abnahme

1. Sichere `config.yaml` und `cron/jobs.json` außerhalb des Git-Repositories mit
   restriktiven Dateirechten. Die Dateien können Zugangsdaten enthalten.
2. Committe und pushe die Implementierung. Führe auf dem VPS als `hermes` ein
   `git pull --ff-only origin main` in `/opt/data/ai-briefing` aus. Erhalte alle
   laufenden Recherche-Zwischenstände und vorhandenen Datenänderungen.
3. Merge ausschließlich die Runtime-Schlüssel aus der YAML-Vorlage und spiele den
   versionierten Prompt über die Cron-CLI ein. Ändere keine Scheduling-/Delivery-Felder.
4. Führe auf dem VPS aus:

   ```sh
   /opt/hermes/.venv/bin/python scripts/check_hermes_runtime.py
   python3 -m unittest discover -s scripts/test -t scripts/test
   ```

   Der Runtime-Check nutzt die tatsächlichen Hermes-Timeout-Resolver, nicht nur
   das Vorhandensein von YAML-Schlüsseln. Alle Checks müssen `true` sein.
5. Prüfe eine Planung in einem separaten temporären Run-Verzeichnis: sechs
   Task-IDs im ersten `dispatch-ready`-Batch, kein zweiter Batch. Keine Modellaufrufe,
   Veröffentlichung oder Telegram-Nachricht sind dafür erforderlich.
6. Prüfe den nächsten Cron-Termin einschließlich Berliner Gate. Ein Neustart ist
   für die auf jedem Toolaufruf gelesenen Timeout-Werte und den vom nächsten Cron-
   Start gelesenen Prompt nicht erforderlich; ein laufendes Briefing bleibt unberührt.

`scripts/editor_context.py` liefert maximal 12.000 Zeichen je Abruf und explizite
Seiten-/Textfortsetzungen. Kandidaten, vollständige Belege und Artikel bleiben in den
Run-Dateien erhalten. `check-editor` erzwingt weiterhin eine Entscheidung je Kandidat
und belegte Original-URLs. Kontextbegrenzung ist keine Kürzung der Quellenabdeckung.
