#!/usr/bin/env python3
"""
guitar_watch.py
----------------
Durchsucht mehrere Quellen nach einem bestimmten Gitarren-Modell und schreibt
neue Treffer in results.md / results.json.

Quellen:
  1. Reverb.com Marktplatz-Suche (liest das eingebettete "apollo-state" JSON
     aus der Suchergebnis-Seite aus)
  2. eBay-Suche (parst die klassische Ergebnisliste)
  3. Eine feste Liste bekannter Gitarrenshops/Direktlinks, die regelmäßig
     erneut geprüft werden (z.B. Music Zoo, Walt Grace Vintage, Guitar-Place)

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
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

# Suchbegriffe, die ALLE (case-insensitive) im Titel vorkommen müssen
MUST_INCLUDE = ["iommi", "monkey"]

# Begriffe, die NICHT vorkommen dürfen (schließt Linkshänder-Modelle aus)
MUST_EXCLUDE = ["left-handed", "left handed", "lefty", " lh ", "(lh)"]

# Reverb Marktplatz-Suche (kein API-Key nötig, wir lesen die HTML-Seite)
REVERB_SEARCH_URL = (
    "https://reverb.com/marketplace?query=Tony+Iommi+Monkey+SG&product_type=electric-guitars"
)

# eBay-Suche
EBAY_SEARCH_URL = (
    "https://www.ebay.com/sch/i.html?_nkw=Gibson+Tony+Iommi+Monkey+SG+Custom+Shop&_sacat=0"
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
    )
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
    try:
        resp = requests.get(REVERB_SEARCH_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[reverb] Abruf fehlgeschlagen: {e}", file=sys.stderr)
        return hits

    soup = BeautifulSoup(resp.text, "html.parser")
    meta = soup.find("meta", attrs={"name": "apollo-state"})
    if not meta or not meta.get("content"):
        print("[reverb] Kein apollo-state gefunden (Seitenstruktur evtl. geändert)", file=sys.stderr)
        return hits

    try:
        state = json.loads(meta["content"])
    except json.JSONDecodeError as e:
        print(f"[reverb] JSON-Parse-Fehler: {e}", file=sys.stderr)
        return hits

    for key, obj in state.items():
        if not key.startswith("Listing:id:"):
            continue
        title = obj.get("title") or ""
        if not matches_filters(title):
            continue
        slug = obj.get("slug", "")
        listing_id = obj.get("id", "")
        url = f"https://reverb.com/item/{listing_id}-{slug}" if slug else ""
        price = ""
        pricing = obj.get("pricing") or {}
        buyer_price = pricing.get("buyerPrice") or {}
        price = buyer_price.get("display", "")
        state_desc = obj.get("stateDescription", "")
        hits.append(Hit(source="Reverb", title=title, url=url, price=price, note=state_desc))

    return hits


# ---------------------------------------------------------------------------
# Quelle 2: eBay
# ---------------------------------------------------------------------------

def search_ebay() -> list[Hit]:
    hits: list[Hit] = []
    try:
        resp = requests.get(EBAY_SEARCH_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ebay] Abruf fehlgeschlagen: {e}", file=sys.stderr)
        return hits

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("li.s-item")
    for item in items:
        title_el = item.select_one(".s-item__title")
        link_el = item.select_one("a.s-item__link")
        price_el = item.select_one(".s-item__price")
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        if not matches_filters(title):
            continue
        hits.append(
            Hit(
                source="eBay",
                title=title,
                url=link_el.get("href", ""),
                price=price_el.get_text(strip=True) if price_el else "",
            )
        )
    return hits


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
    all_hits += search_ebay()
    all_hits += search_shopify_shops()
    all_hits += check_known_dealers()

    new_count = sum(1 for h in all_hits if h.key() not in previous_keys)
    print(f"Gefunden: {len(all_hits)} Treffer insgesamt, davon {new_count} neu.")

    write_results(all_hits, previous_keys)


if __name__ == "__main__":
    main()
