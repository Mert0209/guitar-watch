#!/usr/bin/env python3
"""
guitar_watch.py
----------------
Durchsucht mehrere Quellen nach einem bestimmten Gitarren-Modell und schreibt
neue Treffer in results.md / results.json.

Quellen:
  1. Reverb – offizielle API (braucht kostenlosen Token in REVERB_TOKEN);
     ohne Token nur Such-Link. International.
  2. Shopify-Shops (Music Zoo, Willcutt, Tone Shop, Walt Grace, Chicago
     Music Exchange) über die /search/suggest.json-Schnittstelle
  3. Große Plattformen & eBay (Thomann, Music Store, Catawiki, eBay US/DE):
     Best-Effort-Check plus fertiger Such-Link zum manuellen Nachschauen
  4. Feste Händler-Einzelseiten (z.B. Peach Guitars)

Hintergrund: Reverb, eBay, Music Store und Catawiki blockieren
automatische Roh-Zugriffe (HTTP 403). Deshalb läuft Reverb über die
offizielle API, und die anderen liefern einen zuverlässigen Such-Link.

WICHTIG:
- Kein Login, keine API-Keys nötig -> läuft "out of the box" in GitHub Actions.
- Die Selektoren (HTML-Klassen, JSON-Struktur) können sich mit der Zeit
  ändern, weil das inoffizielles Scraping ist. Wenn ein Lauf 0 Treffer
  liefert, obwohl du weißt, dass es welche geben müsste: zuerst prüfen,
  ob sich die Seitenstruktur geändert hat (siehe README, Abschnitt
  "Wartung").
"""

import json
import re
import sys
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Suchbegriffe, die ALLE (case-insensitive) im Titel vorkommen müssen
MUST_INCLUDE = ["iommi", "monkey"]

# Begriffe, die NICHT vorkommen dürfen (schließt Linkshänder-Modelle aus)
MUST_EXCLUDE = ["left-handed", "left handed", "lefty", " lh ", "(lh)"]

# Reverb – OFFIZIELLE API (wird nicht blockiert, im Gegensatz zum Scraping).
# Braucht einen kostenlosen persönlichen Token, den GitHub Actions als
# geheime Umgebungsvariable REVERB_TOKEN bereitstellt (siehe README).
# Ohne Token schreibt das Skript ersatzweise nur einen Such-Link.
REVERB_API_URL = "https://api.reverb.com/api/listings"
REVERB_QUERY = "Tony Iommi Monkey SG"
# Menschlicher Such-Link als Fallback / zum manuellen Nachschauen:
REVERB_WEB_SEARCH = (
    "https://reverb.com/marketplace?query=Tony+Iommi+Monkey+SG&product_type=electric-guitars"
)

# ---------------------------------------------------------------------------
# Shopify-Shops: Viele Gitarrenhändler laufen technisch auf Shopify. Diese
# haben eine eingebaute Such-Schnittstelle, die sauberes JSON liefert:
#     https://<shop-domain>/search/suggest.json?q=<suchbegriff>&resources[type]=product
# Damit können wir den KOMPLETTEN Shop durchsuchen und auch NEUE Angebote
# finden – nicht nur eine feste Produktseite beobachten.
#
# Neue Shopify-Shops hinzufügen: einfach {"name": ..., "domain": ...} ergänzen.
# Die "domain" ist der Teil aus der URL ohne "https://" und ohne Pfad.
# Tipp zum Testen, ob ein Shop Shopify ist: Rufe im Browser
#     https://<domain>/products.json
# auf – kommt eine JSON-Liste mit Produkten, ist es Shopify.
SHOPIFY_SHOPS = [
    {"name": "The Music Zoo", "domain": "www.themusiczoo.com"},
    {"name": "Willcutt Guitars", "domain": "willcuttguitars.com"},
    {"name": "Tone Shop Guitars", "domain": "www.toneshopguitars.com"},
    {"name": "Walt Grace Vintage", "domain": "waltgracevintage.com"},
    {"name": "Chicago Music Exchange", "domain": "www.chicagomusicexchange.com"},
    # Weitere Shopify-Shops hier ergänzen:
    # {"name": "...", "domain": "..."},
]

# Nicht-Shopify-Shops mit fester Produktseite, die wir einzeln beobachten.
# "url" wird abgerufen; wenn KEINER der SOLD_OUT_MARKERS im Text vorkommt,
# gilt das Angebot als (vermutlich) verfügbar.
KNOWN_DEALER_PAGES = [
    {
        "name": "Peach Guitars (Pair-Listing)",
        "url": "https://www.peachguitars.com/gibson-custom-tony-iommi-monkey-1964-sg-special-aged-and-signed-pair.htm",
    },
    # Weitere Einzelseiten hier ergänzen: {"name": "...", "url": "..."}
]

# Große Plattformen (Thomann, Music Store, Catawiki, ...): jede ist anders
# gebaut, deshalb KEIN Präzisions-Parser, sondern ein robuster Best-Effort:
# Wir rufen die Suchseite auf, prüfen grob, ob ein Treffer wahrscheinlich ist,
# und schreiben in JEDEM Fall den fertigen Such-Link in die Ergebnisdatei,
# damit du ihn mit einem Klick selbst prüfen kannst.
#
# "{q}" im search_url wird durch den URL-kodierten Suchbegriff ersetzt.
# "no_results_markers": Texte, die auf einer Treffer-LEEREN Seite stehen.
GENERIC_SEARCH_SITES = [
    {
        "name": "Thomann",
        "search_url": "https://www.thomann.de/de/search_dir.html?sw={q}",
        "query": "Iommi Monkey",
        "no_results_markers": ["keine artikel", "keine ergebnisse", "no results", "0 artikel"],
    },
    {
        "name": "Music Store",
        "search_url": "https://www.musicstore.de/de_DE/EUR/search?text={q}",
        "query": "Iommi Monkey",
        "no_results_markers": ["keine ergebnisse", "keine treffer", "no results", "0 treffer"],
    },
    {
        "name": "Catawiki",
        "search_url": "https://www.catawiki.com/de/s?q={q}",
        "query": "Iommi Monkey SG",
        "no_results_markers": ["keine ergebnisse", "keine treffer", "no results found", "0 ergebnisse"],
    },
    {
        "name": "eBay US",
        "search_url": "https://www.ebay.com/sch/i.html?_nkw={q}",
        "query": "Gibson Tony Iommi Monkey SG",
        "no_results_markers": ["0 results", "0 ergebnisse", "keine ergebnisse", "no exact matches"],
    },
    {
        "name": "eBay DE",
        "search_url": "https://www.ebay.de/sch/i.html?_nkw={q}",
        "query": "Gibson Tony Iommi Monkey SG",
        "no_results_markers": ["0 ergebnisse", "keine ergebnisse", "0 results", "keine exakten treffer"],
    },
    # Weitere große Such-Seiten hier ergänzen (Muster wie oben):
    # {"name": "...", "search_url": "https://.../search?q={q}", "query": "...",
    #  "no_results_markers": ["..."]},
]

SOLD_OUT_MARKERS = [
    "no longer available",
    "out of stock",
    "sold",
    "not available",
    "nicht verfügbar",
    "ausverkauft",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

RESULTS_JSON = Path(__file__).parent / "results.json"
RESULTS_MD = Path(__file__).parent / "results.md"


@dataclass
class Hit:
    source: str
    title: str
    url: str
    price: str = ""
    note: str = ""

    def key(self) -> str:
        # Eindeutiger Schlüssel für "haben wir das schon gesehen?"
        return f"{self.source}|{self.url}"


def matches_filters(title: str) -> bool:
    t = title.lower()
    if not all(term in t for term in MUST_INCLUDE):
        return False
    if any(term in t for term in MUST_EXCLUDE):
        return False
    return True


# ---------------------------------------------------------------------------
# Quelle 1: Reverb
# ---------------------------------------------------------------------------

def search_reverb() -> list[Hit]:
    hits: list[Hit] = []
    token = os.environ.get("REVERB_TOKEN", "").strip()

    # Ohne Token: nur Such-Link ausgeben, damit du trotzdem klicken kannst.
    if not token:
        print("[reverb] Kein REVERB_TOKEN gesetzt – gebe nur Such-Link aus.", file=sys.stderr)
        hits.append(
            Hit(
                source="Reverb",
                title="Reverb – Suche „Tony Iommi Monkey SG“",
                url=REVERB_WEB_SEARCH,
                note="Kein API-Token hinterlegt – Link manuell prüfen (siehe README)",
            )
        )
        return hits

    api_headers = {
        "Accept": "application/hal+json",
        "Accept-Version": "3.0",
        "Authorization": f"Bearer {token}",
    }
    params = {"query": REVERB_QUERY, "product_type": "electric-guitars", "per_page": "50"}

    try:
        resp = requests.get(REVERB_API_URL, headers=api_headers, params=params, timeout=25)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"[reverb] API-Abruf fehlgeschlagen: {e}", file=sys.stderr)
        hits.append(
            Hit(
                source="Reverb",
                title="Reverb – Suche „Tony Iommi Monkey SG“",
                url=REVERB_WEB_SEARCH,
                note="API-Abruf fehlgeschlagen – Link manuell prüfen",
            )
        )
        return hits

    for listing in data.get("listings", []):
        title = listing.get("title", "")
        if not matches_filters(title):
            continue
        # Web-Link zum Angebot
        url = ""
        links = listing.get("_links", {}) or {}
        web = links.get("web", {}) or {}
        url = web.get("href", "")
        # Preis
        price = ""
        price_obj = listing.get("price", {}) or {}
        price = price_obj.get("display", "")
        # Verfügbarkeit
        state = (listing.get("state", {}) or {}).get("slug", "")
        note = "verfügbar" if state == "live" else (state or "")
        hits.append(Hit(source="Reverb", title=title, url=url, price=price, note=note))

    return hits


# ---------------------------------------------------------------------------
# (eBay wird jetzt über die Such-Link-Quellen in GENERIC_SEARCH_SITES
#  abgedeckt, da eBay automatische Scraping-Zugriffe blockiert.)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Quelle 3: Shopify-Shops durchsuchen (findet auch NEUE Angebote)
# ---------------------------------------------------------------------------

def search_shopify_shops() -> list[Hit]:
    hits: list[Hit] = []
    for shop in SHOPIFY_SHOPS:
        url = (
            f"https://{shop['domain']}/search/suggest.json"
            "?q=iommi+monkey&resources[type]=product&resources[limit]=10"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"[shopify:{shop['name']}] Abruf fehlgeschlagen: {e}", file=sys.stderr)
            continue

        products = (
            data.get("resources", {})
            .get("results", {})
            .get("products", [])
        )
        for p in products:
            title = p.get("title", "")
            if not matches_filters(title):
                continue
            handle_url = p.get("url", "")
            # Shopify liefert oft nur den Pfad -> vollständige URL bauen
            if handle_url.startswith("/"):
                handle_url = f"https://{shop['domain']}{handle_url}"
            price = ""
            if p.get("price"):
                price = str(p.get("price"))
            available = p.get("available")
            note = "" if available is None else ("verfügbar" if available else "nicht verfügbar")
            hits.append(
                Hit(
                    source=shop["name"],
                    title=title,
                    url=handle_url,
                    price=price,
                    note=note,
                )
            )
    return hits


# ---------------------------------------------------------------------------
# Quelle 5: Große Plattformen (Thomann, Music Store, Catawiki) – Best-Effort
# ---------------------------------------------------------------------------

def search_generic_sites() -> list[Hit]:
    """Ruft die Suchseite grosser Plattformen auf, prueft grob auf Treffer
    und liefert IMMER den Such-Link zum manuellen Nachschauen zurueck."""
    hits: list[Hit] = []
    for site in GENERIC_SEARCH_SITES:
        query = quote_plus(site["query"])
        search_url = site["search_url"].replace("{q}", query)

        note = "Such-Link – bitte manuell prüfen"
        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=25)
            resp.raise_for_status()
            page = resp.text.lower()

            has_all_terms = all(term in page for term in MUST_INCLUDE)
            has_no_results = any(m in page for m in site["no_results_markers"])

            if has_all_terms and not has_no_results:
                note = "⚠️ MÖGLICHER TREFFER – Suchbegriffe auf der Seite gefunden, bitte prüfen!"
            elif has_no_results:
                note = "keine Treffer auf der Suchseite (trotzdem Link zum Nachschauen)"
        except requests.RequestException as e:
            print(f"[{site['name']}] Abruf fehlgeschlagen: {e}", file=sys.stderr)
            note = "Automatik-Abruf fehlgeschlagen – Link manuell prüfen"

        hits.append(
            Hit(
                source=site["name"],
                title=f"{site['name']} – Suche „{site['query']}“",
                url=search_url,
                note=note,
            )
        )
    return hits


# ---------------------------------------------------------------------------
# Quelle 4: Bekannte Händler-Seiten (feste Einzel-Links)
# ---------------------------------------------------------------------------

def check_known_dealers() -> list[Hit]:
    hits: list[Hit] = []
    for dealer in KNOWN_DEALER_PAGES:
        try:
            resp = requests.get(dealer["url"], headers=HEADERS, timeout=20)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[dealer:{dealer['name']}] Abruf fehlgeschlagen: {e}", file=sys.stderr)
            continue

        text_lower = resp.text.lower()
        sold_out = any(marker in text_lower for marker in SOLD_OUT_MARKERS)
        if not sold_out:
            hits.append(
                Hit(
                    source="Direktlink",
                    title=dealer["name"],
                    url=dealer["url"],
                    note="Kein 'ausverkauft'-Hinweis gefunden -> manuell prüfen!",
                )
            )
    return hits


# ---------------------------------------------------------------------------
# Ergebnisse zusammenführen, mit vorherigem Lauf vergleichen, schreiben
# ---------------------------------------------------------------------------

def load_previous_keys() -> set[str]:
    if not RESULTS_JSON.exists():
        return set()
    try:
        data = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
        return {entry["key"] for entry in data.get("hits", [])}
    except (json.JSONDecodeError, KeyError):
        return set()


def write_results(all_hits: list[Hit], previous_keys: set[str]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # JSON (für den nächsten Lauf / Diff)
    RESULTS_JSON.write_text(
        json.dumps(
            {
                "last_run": now,
                "hits": [{**asdict(h), "key": h.key()} for h in all_hits],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Markdown (für dich zum Lesen)
    lines = [f"# Gitarren-Watch – Ergebnisse\n", f"Letzter Lauf: {now}\n"]
    if not all_hits:
        lines.append("Keine Treffer gefunden.\n")
    else:
        for h in all_hits:
            is_new = h.key() not in previous_keys
            marker = "🆕 " if is_new else ""
            lines.append(f"## {marker}{h.title}")
            lines.append(f"- Quelle: {h.source}")
            if h.price:
                lines.append(f"- Preis: {h.price}")
            if h.note:
                lines.append(f"- Hinweis: {h.note}")
            if h.url:
                lines.append(f"- Link: {h.url}")
            lines.append("")

    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    previous_keys = load_previous_keys()

    all_hits: list[Hit] = []
    all_hits += search_reverb()
    all_hits += search_shopify_shops()
    all_hits += search_generic_sites()
    all_hits += check_known_dealers()

    new_count = sum(1 for h in all_hits if h.key() not in previous_keys)
    print(f"Gefunden: {len(all_hits)} Treffer insgesamt, davon {new_count} neu.")

    write_results(all_hits, previous_keys)


if __name__ == "__main__":
    main()
