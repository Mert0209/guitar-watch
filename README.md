# Gitarren-Watch: Tony Iommi "Monkey" SG (Rechtshänder)

Dieses kleine Projekt durchsucht automatisch mehrmals täglich:

1. **Reverb** (Marktplatz-Suche, international)
2. **eBay** (US + Deutschland)
3. **Shopify-Läden** (Music Zoo, Willcutt, Tone Shop, Walt Grace,
   Chicago Music Exchange – findet auch neue Angebote)
4. **Feste Händler-Seiten** (z. B. Peach Guitars)
5. **Große Plattformen** (Thomann, Music Store, Catawiki): grober
   Treffer-Check plus fertiger Such-Link zum selbst Nachschauen

...nach der Gibson Custom Shop Tony Iommi "Monkey" SG (Rechtshänder) und
schreibt die Treffer in `results.md`. Neue Treffer seit dem letzten Lauf
werden mit 🆕 markiert.

Läuft komplett kostenlos über **GitHub Actions** – du musst dafür keinen
eigenen Server betreiben und nichts dauerhaft laufen lassen.

---

## Einmaliges Setup (ca. 10 Minuten)

### Schritt 1: GitHub-Account

Falls du noch keinen hast: auf https://github.com registrieren (kostenlos).

### Schritt 2: Neues Repository anlegen

1. Oben rechts auf **"+"** → **"New repository"**
2. Name z. B. `guitar-watch`
3. **Private** auswählen (muss nicht öffentlich sein)
4. **"Create repository"** klicken — noch nichts weiter ankreuzen

### Schritt 3: Dateien hochladen

Du hast von mir diese Dateistruktur bekommen:

```
guitar-watch/
├── guitar_watch.py
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── watch.yml
```

Im neuen, leeren Repository auf GitHub:

1. Klick auf **"uploading an existing file"** (Link auf der Startseite des
   leeren Repos)
2. Zieh die Datei `guitar_watch.py` und `requirements.txt` per Drag & Drop
   in das Upload-Feld
3. Unten **"Commit changes"** klicken

Für den Ordner `.github/workflows/watch.yml` musst du den Pfad manuell
anlegen, da GitHubs Weboberfläche keine ganzen Ordner per Drag & Drop
akzeptiert:

1. Auf der Repo-Startseite: **"Add file" → "Create new file"**
2. Als Dateiname exakt eingeben: `.github/workflows/watch.yml`
   (die Schrägstriche legen automatisch die Unterordner an)
3. Inhalt der Datei `watch.yml` hineinkopieren
4. **"Commit changes"**

*(Alternative, falls du lieber mit Git auf der Kommandozeile arbeitest —
das nehme ich an, da du dir das zutraust:)*

```bash
git clone https://github.com/<dein-username>/guitar-watch.git
cd guitar-watch
# alle Dateien aus diesem Projekt hier reinkopieren
git add .
git commit -m "Initial setup"
git push
```

### Schritt 4: Actions aktivieren

1. Im Repo auf den Tab **"Actions"** klicken
2. Falls eine Meldung kommt "Workflows aren't being run on this
   repository" → **"I understand my workflows, go ahead and enable
   them"** klicken

### Schritt 5: Ersten Testlauf starten

1. Tab **"Actions"** → links **"Guitar Watch"** anklicken
2. Rechts **"Run workflow"** → **"Run workflow"** (grüner Button)
3. Nach ca. 30–60 Sekunden auf den Lauf klicken und Logs ansehen —
   dort siehst du direkt, wie viele Treffer gefunden wurden

### Schritt 6: Ergebnisse ansehen

Nach jedem Lauf (egal ob manuell oder automatisch) landet die Datei
`results.md` aktualisiert im Repo. Einfach im Repo drauf klicken, um die
aktuelle Liste zu sehen. Da es ein **Private**-Repo ist, siehst nur du
das.

---

## Zeitplan ändern

Standardmäßig läuft die Suche **3× täglich** (04:00 / 10:00 / 16:00 UTC,
also im Sommer ca. 06:00 / 12:00 / 18:00 deutscher Zeit). Wenn du das
ändern willst: Datei `.github/workflows/watch.yml` öffnen und die
`cron`-Zeilen anpassen. Format: `Minute Stunde Tag Monat Wochentag`
(UTC-Zeit, nicht deutsche Zeit!). Jede `- cron:`-Zeile ist ein eigener
Startzeitpunkt; mehr Zeilen = häufiger.

Hinweis zur Fairness gegenüber den Seiten: 3× täglich ist völlig
unkritisch. Bei sehr hoher Frequenz (viele Male pro Stunde) könnten
Plattformen deine IP zeitweise sperren.

---

## Weitere Shops hinzufügen

Es gibt zwei Wege, je nachdem, wie der Shop technisch gebaut ist:

### a) Shopify-Shops (bevorzugt – findet auch neue Angebote)

Viele Gitarrenhändler laufen auf Shopify. Diese kann das Skript richtig
*durchsuchen*. In `guitar_watch.py` gibt es die Liste `SHOPIFY_SHOPS`:

```python
{"name": "Mein Shop", "domain": "www.meinshop.com"},
```

**So findest du heraus, ob ein Shop Shopify ist:** Ruf im Browser
`https://<domain>/products.json` auf (z. B.
`https://willcuttguitars.com/products.json`). Kommt eine JSON-Liste mit
Produkten → Shopify → in `SHOPIFY_SHOPS` eintragen. Kommt ein Fehler oder
eine normale Fehlerseite → kein Shopify → Weg b).

### b) Andere Shops (feste Produktseite beobachten)

Für Shops ohne Shopify-Suche trägst du eine konkrete Produktseite in
`KNOWN_DEALER_PAGES` ein. Das Skript meldet die Seite, solange dort kein
"ausverkauft"-Hinweis steht:

```python
{"name": "Peach Guitars", "url": "https://... Produkt-URL ..."},
```

Aktuell schon eingetragen:
- **Shopify:** Music Zoo, Willcutt Guitars, Tone Shop Guitars,
  Walt Grace Vintage, Chicago Music Exchange
- **Feste Seite:** Peach Guitars

Wenn du einen bestimmten Shop ergänzen willst und unsicher bist, welcher
Weg passt – sag Bescheid, dann machen wir das zusammen.

---

## Wartung / wenn's mal nichts findet

Diese Art von Skript scraped öffentliche Webseiten, die keine offizielle
API dafür anbieten. Wenn Reverb oder eBay ihr Seiten-Layout ändern,
kann es sein, dass das Skript plötzlich 0 Treffer liefert, obwohl es
welche gäbe. Kurzer Check dann:

1. Log des letzten Actions-Laufs ansehen (Tab "Actions" → letzter Lauf)
   — steht dort eine Fehlermeldung wie "Kein apollo-state gefunden"?
2. Das bedeutet: Reverb hat die Seitenstruktur geändert → die
   entsprechende Funktion in `guitar_watch.py` muss angepasst werden.

Das ist der Kompromiss bei "kostenlos + keine offizielle API" — dafür
kostet dich das Ganze aber auch nichts außer gelegentlicher Wartung.

---

## Rechtlicher Hinweis

Das Skript ruft nur öffentlich zugängliche Suchergebnis-Seiten ab (wie
ein normaler Browser-Aufruf) und speichert nur Titel/Preis/Link — kein
Login, keine automatisierten Käufe. Trotzdem: Nutzungsbedingungen der
jeweiligen Plattformen gelten weiterhin; bei sehr hoher Abruffrequenz
(hier: 1×/Tag, also unkritisch) können Plattformen IP-Sperren
aussprechen. Der aktuelle Zeitplan (täglich) ist bewusst niedrig
gehalten.
