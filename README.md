# guitar-watch

Ein automatischer Suchauftrag für eine ganz bestimmte Gitarre: die Gibson Custom Shop Tony Iommi „Monkey“ '64 SG Special. Von dem Modell gibt es nur wenige Exemplare, Angebote tauchen selten und auf verschiedenen Plattformen auf. Statt jeden Tag ein Dutzend Seiten von Hand zu prüfen, durchsucht dieses Skript sie dreimal täglich und schreibt die Treffer in eine Liste.

Die aktuelle Ergebnisliste liegt in [`results.md`](results.md).

## Was es macht

- Durchsucht Reverb über die offizielle API
- Durchsucht mehrere Gitarrenhändler, die auf Shopify laufen (u. a. The Music Zoo, Willcutt Guitars, Chicago Music Exchange)
- Beobachtet feste Produktseiten einzelner Händler und erkennt „ausverkauft“-Hinweise
- Erzeugt für Plattformen ohne nutzbare Schnittstelle (eBay, Thomann, Music Store, Catawiki) fertige Such-Links
- Rechnet Preise aus USD, GBP usw. grob in Euro um und blendet alles unter einem Mindestpreis aus, damit die günstigen Serienmodelle verschwinden
- Markiert Angebote, die seit dem letzten Lauf neu dazugekommen sind
- Speichert das Ergebnis als Markdown (zum Lesen) und als JSON (zum Weiterverarbeiten)

## Ablauf

```
GitHub Actions (Zeitplan, 3x täglich)
        │
        ▼
guitar_watch.py
        ├── Reverb-API
        ├── Shopify-Shops
        ├── feste Händlerseiten
        └── Such-Links für übrige Plattformen
        │
        ▼
Filter (Suchbegriffe, Mindestpreis) → Abgleich mit letztem Lauf
        │
        ▼
results.md + results.json → automatischer Commit ins Repository
```

Es gibt keinen eigenen Server. Der Workflow in `.github/workflows/watch.yml` startet das Skript nach Zeitplan, und die Ergebnisse werden als Commit zurück ins Repository geschrieben.

## Probleme und Entscheidungen

**Blockierte Zugriffe.** Die erste Version hat die Suchseiten direkt als HTML ausgelesen. Von den Servern von GitHub Actions aus haben Reverb, eBay, Music Store und Catawiki diese Anfragen mit HTTP 403 abgelehnt. Reverb läuft deshalb jetzt über die offizielle API. Für die anderen Plattformen habe ich mich gegen Umgehungstricks entschieden und liefere stattdessen einen Such-Link, den man selbst öffnet.

**Zugangsschlüssel.** Der Reverb-Token steht nicht im Code. Er liegt als verschlüsseltes Secret in GitHub und wird dem Skript im Workflow als Umgebungsvariable `REVERB_TOKEN` übergeben. Fehlt er, läuft das Skript trotzdem weiter und gibt für Reverb nur einen Such-Link aus.

**Zu viele Treffer.** Die Suche nach „Iommi Monkey“ findet auch das deutlich günstigere Serienmodell. Weil die Angebote in verschiedenen Währungen kommen, werden die Preise zuerst in Euro umgerechnet und dann gegen einen Mindestpreis gefiltert. Die Wechselkurse sind feste Näherungswerte, für einen Filter mit großem Abstand reicht das.

**Neue Angebote erkennen.** Jeder Treffer bekommt einen Schlüssel aus Quelle und Link. Das Skript vergleicht ihn mit der `results.json` vom letzten Lauf und markiert alles, was vorher nicht da war.

**Rücksicht auf die Seiten.** Die Abfragen laufen bewusst nur dreimal am Tag. Öfter wäre für diesen Zweck unnötig und würde die Seiten unnötig belasten.

## Lokal ausführen

Voraussetzung: Python 3.12

```bash
pip install -r requirements.txt
python guitar_watch.py
```

Optional für echte Reverb-Treffer einen Token setzen:

```bash
# Linux/macOS
export REVERB_TOKEN="dein-token"

# Windows PowerShell
$env:REVERB_TOKEN="dein-token"
```

Suchbegriffe, Mindestpreis, Wechselkurse und die Liste der Shops stehen als Konstanten am Anfang von `guitar_watch.py`.

## Projektstruktur

```
guitar_watch.py              Suche, Filter, Ausgabe
requirements.txt             requests, beautifulsoup4
results.md / results.json    Ergebnisse des letzten Laufs
.github/workflows/watch.yml  Zeitplan und automatischer Commit
```

## Grenzen

- Für eBay, Thomann, Music Store und Catawiki gibt es nur Such-Links, keine automatische Auswertung.
- Die Shopify-Suche nutzt eine öffentliche, aber nicht offiziell dokumentierte Schnittstelle der Shops. Ändert ein Shop sie, liefert er keine Treffer mehr.
- Die Wechselkurse werden nicht automatisch aktualisiert.

## Technik

Python · requests · Beautiful Soup · Reverb API · GitHub Actions
