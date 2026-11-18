#!/usr/bin/env python3
"""Oeffentliche Wochenpruefung fuer Kundenwebsites (nur lesend, sendet keine Formulare ab).

Aufruf:  python3 sitecheck.py <site> [--json]
  site = sabix | newimmohouse
Ausgabe: JSON mit "entry" (kundentaugliche Felder fuer data.json, ohne client_note/backup)
         und "internal" (Details nur fuer den Betreiber, NIE in data.json schreiben).
"""
import json, re, sys, time, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse, urldefrag
import requests
from bs4 import BeautifulSoup

SITES = {
    "sabix": {"base": "https://www.sabix.ch", "hosts": {"sabix.ch", "www.sabix.ch"}, "form_id": 3802},
    "newimmohouse": {"base": "https://newimmohouse.ch", "hosts": {"newimmohouse.ch"}, "form_id": None},
}
UA = "Mozilla/5.0 (compatible; SitecheckWartung/1.0)"
S = requests.Session()
S.headers["User-Agent"] = UA
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
_retry = Retry(total=4, connect=4, read=2, backoff_factor=1.5, status_forcelist=(502, 503, 504),
               allowed_methods=frozenset({"GET", "HEAD"}), raise_on_status=False)
S.mount("https://", HTTPAdapter(max_retries=_retry, pool_maxsize=8))
TIMEOUT = 25


def get(url, **kw):
    return S.get(url, timeout=TIMEOUT, allow_redirects=True, **kw)


def sitemap_urls(base):
    """Seitenliste aus /wp-sitemap.xml (folgt Weiterleitung, z. B. auf Yoast sitemap_index.xml)."""
    seen, pages, todo = set(), [], [base + "/wp-sitemap.xml"]
    while todo:
        u = todo.pop(0)
        if u in seen:
            continue
        seen.add(u)
        r = get(u)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        if root.tag.endswith("sitemapindex"):
            todo += [l.text.strip() for l in root.iter(ns + "loc")]
        else:
            pages += [l.text.strip() for l in root.iter(ns + "loc")]
    return list(dict.fromkeys(pages))


def is_internal(url, hosts):
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.hostname in hosts


def extract_refs(html, page_url, hosts):
    soup = BeautifulSoup(html, "html.parser")
    refs = set()
    def add(v):
        if not v:
            return
        v = v.strip()
        if v.startswith(("mailto:", "tel:", "javascript:", "data:", "#")):
            return
        u = urldefrag(urljoin(page_url, v))[0]
        if is_internal(u, hosts):
            refs.add(u)
    for a in soup.find_all("a", href=True):
        add(a["href"])
    for t in soup.find_all(["img", "script", "source", "iframe"]):
        add(t.get("src"))
        for attr in ("srcset", "data-srcset"):
            if t.get(attr):
                for part in t[attr].split(","):
                    add(part.strip().split(" ")[0])
    for l in soup.find_all("link", href=True):
        rel = " ".join(l.get("rel", [])).lower()
        if any(k in rel for k in ("stylesheet", "icon", "preload", "modulepreload")):
            add(l["href"])
    return refs, soup


def check_url(u):
    try:
        r = S.head(u, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code in (403, 405, 501) or r.status_code >= 400:
            r = S.get(u, timeout=TIMEOUT, allow_redirects=True, stream=True)
            r.close()
        return u, r.status_code
    except requests.RequestException as e:
        return u, f"error: {type(e).__name__}"


def find_form(soups, form_id):
    """Sucht das CF7-Formular im Quelltext; liefert (form_id, unit_tag, hat_pflichtfelder, seite)."""
    for page, soup in soups.items():
        for f in soup.select("div.wpcf7"):
            fid_input = f.find("input", {"name": "_wpcf7"})
            fid = int(fid_input["value"]) if fid_input else None
            if form_id is not None and fid != form_id:
                continue
            unit = f.find("input", {"name": "_wpcf7_unit_tag"})
            required = bool(f.select(".wpcf7-validates-as-required, [aria-required=true]"))
            return fid, unit["value"] if unit else f.get("id"), required, page
    return form_id, None, None, None


def check_form(base, fid, unit_tag, required):
    """Nur Validierung: leere Felder an den CF7-REST-Endpunkt. Erwartet validation_failed, es wird keine Mail ausgeloest."""
    if fid is None:
        return "Fehler", "Formular-ID nicht gefunden"
    if required is False:
        return "Fehler", "Formular ohne Pflichtfelder - Test uebersprungen, damit nichts abgeschickt wird"
    url = f"{base}/wp-json/contact-form-7/v1/contact-forms/{fid}/feedback"
    data = {"_wpcf7": str(fid), "_wpcf7_unit_tag": unit_tag or f"wpcf7-f{fid}-o1", "_wpcf7_version": "", "_wpcf7_locale": ""}
    try:
        r = S.post(url, files={k: (None, v) for k, v in data.items()}, timeout=TIMEOUT)
        j = r.json()
    except Exception as e:
        return "Fehler", f"keine Antwort: {type(e).__name__}"
    st = j.get("status")
    if st == "validation_failed":
        return "OK", f"validation_failed ({len(j.get('invalid_fields', []))} Pflichtfelder gemeldet)"
    if st == "mail_sent":
        return "Fehler", "ACHTUNG: leeres Formular wurde angenommen (mail_sent)"
    return "Fehler", f"unerwartete Antwort: HTTP {r.status_code} {st or j.get('code')}"


def run(site):
    cfg = SITES[site]
    base, hosts = cfg["base"], cfg["hosts"]
    internal = {"site": site}
    pages = sitemap_urls(base)
    times, ok, failed_pages, soups, refs = [], 0, [], {}, set()
    for p in pages:
        try:
            r = get(p)
            times.append(r.elapsed.total_seconds() * 1000)
            if r.status_code == 200:
                ok += 1
                rr, soup = extract_refs(r.text, r.url, hosts)
                refs |= rr
                soups[p] = soup
            else:
                failed_pages.append([p, r.status_code])
        except requests.RequestException as e:
            failed_pages.append([p, type(e).__name__])
    refs -= set(pages)  # Sitemap-Seiten sind schon geprueft
    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(check_url, sorted(refs)))
    broken = [[u, s] for u, s in results if not (isinstance(s, int) and s < 400)]
    broken += [x for x in failed_pages]  # nicht erreichbare Sitemap-Seiten zaehlen nicht doppelt als Link
    broken_links = [b for b in broken if b not in failed_pages]

    fid, unit, required, form_page = find_form(soups, cfg["form_id"])
    form, form_detail = check_form(base, fid, unit, required)
    resp_ms = round(sum(times) / len(times)) if times else None

    if ok < len(pages) or form != "OK":
        status = "Fehler"
    elif broken_links or (resp_ms or 0) > 2500:
        status = "Achtung"
    else:
        status = "In Ordnung"
    entry = {"status": status, "pages_ok": ok, "pages_total": len(pages), "links_broken": len(broken_links),
             "form": form, "resp_ms": resp_ms}
    internal.update({"failed_pages": failed_pages, "broken_links": broken_links, "checked_refs": len(refs),
                     "form_id": fid, "form_page": form_page, "form_detail": form_detail})
    return {"entry": entry, "internal": internal}


KEYS = ["date", "status", "pages_ok", "pages_total", "links_broken", "form", "resp_ms", "backup", "client_note"]


def write_entry(path, entry):
    """Ersetzt den Eintrag mit gleichem Datum (oder haengt an); nur die kundentauglichen Felder."""
    if set(entry) != set(KEYS):
        raise SystemExit(f"Felder muessen genau {KEYS} sein, erhalten: {sorted(entry)}")
    if entry["status"] not in ("In Ordnung", "Achtung", "Fehler") or entry["backup"] not in ("OK", "Fehler", None):
        raise SystemExit("ungueltiger status/backup")
    runs = json.load(open(path, encoding="utf-8"))
    runs = [r for r in runs if r.get("date") != entry["date"]] + [{k: entry[k] for k in KEYS}]
    runs.sort(key=lambda r: r["date"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(runs, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "write":   # python3 sitecheck.py write <pfad/data.json> '<eintrag-json>'
        write_entry(sys.argv[2], json.loads(sys.argv[3]))
    else:
        print(json.dumps(run(sys.argv[1]), ensure_ascii=False, indent=1))
