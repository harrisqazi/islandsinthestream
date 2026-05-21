#!/usr/bin/env python3
"""
Scrape photos for Islands in the Stream into: images/gallery images/

Target URL: https://www.yelp.com/biz/islands-in-the-stream-richmond

Yelp often blocks bots with a captcha. This script tries Yelp first, then
falls back to Google Maps photos for the same business (144 E Main St, Richmond KY).

Install:
  pip install playwright curl_cffi
  playwright install chromium

Run:
  python scripts/scrape_yelp_gallery.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "images" / "gallery images"
YELP_URL = "https://www.yelp.com/biz/islands-in-the-stream-richmond"
BIZ_PHOTOS_URL = "https://www.yelp.com/biz_photos/islands-in-the-stream-richmond"
GMAPS_SEARCH = (
    "https://www.google.com/maps/search/"
    "Islands+in+the+Stream+144+E+Main+Street+Richmond+KY"
)


def normalize_yelp_image_url(url: str) -> str | None:
    url = unquote(url).strip().replace("\\u002F", "/").replace("\\/", "/")
    if not url.startswith("http") or "yelpcdn.com" not in url or "/bphoto/" not in url:
        return None
    if any(x in url.lower() for x in (".svg", ".gif", "avatar", "badge", "logo")):
        return None
    url = re.sub(r"/\d+s\.(jpg|jpeg|webp)", r"/o.\1", url, flags=re.I)
    if not re.search(r"\.(jpe?g|webp|png)$", url, re.I):
        url = url.rstrip("/") + "/o.jpg"
    return url.split("?")[0]


def normalize_gmaps_url(url: str) -> str | None:
    if "googleusercontent.com" not in url:
        return None
    if any(x in url for x in ("=s48", "=s32", "=s64", "favicon", "/a/ACg8oc")):
        return None
    base = url.split("=")[0]
    if len(base) < 50:
        return None
    return base + "=w1920-h1080-k-no"


def launch_browser(playwright):
    for channel in ("msedge", "chrome", None):
        try:
            if channel:
                return playwright.chromium.launch(headless=True, channel=channel)
        except Exception:
            continue
    return playwright.chromium.launch(headless=True)


def scrape_yelp() -> set[str]:
    from playwright.sync_api import sync_playwright

    urls: set[str] = set()

    def on_response(response):
        norm = normalize_yelp_image_url(response.url)
        if norm:
            urls.add(norm)

    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page()
        page.on("response", on_response)

        for target in (BIZ_PHOTOS_URL, YELP_URL):
            print(f"Yelp: {target}")
            try:
                page.goto(target, wait_until="domcontentloaded", timeout=90000)
                page.wait_for_timeout(5000)
                html = page.content()
                if html.count("bphoto") == 0 and len(html) < 8000:
                    print("  blocked (captcha)")
                    continue
                for _ in range(12):
                    page.mouse.wheel(0, 1200)
                    page.wait_for_timeout(500)
                for m in re.finditer(
                    r"https://s3-media\d*\.fl\.yelpcdn\.com/bphoto/[A-Za-z0-9_-]+[^\"'\\\s<>?#]*",
                    page.content(),
                ):
                    norm = normalize_yelp_image_url(m.group(0))
                    if norm:
                        urls.add(norm)
            except Exception as exc:
                print(f"  error: {exc}")

        browser.close()

    return urls


def scrape_google_maps() -> set[str]:
    from playwright.sync_api import sync_playwright

    urls: set[str] = set()

    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})

        def collect_from_dom():
            found = page.evaluate(
                """() => {
                const out = new Set();
                document.querySelectorAll('img, button, div[style]').forEach(el => {
                  const s = el.src || el.getAttribute('style') || '';
                  const m = s.match(/https:\\/\\/lh\\d+\\.googleusercontent\\.com\\/[^\"')\\s]+/g);
                  if (m) m.forEach(u => out.add(u));
                });
                return [...out];
            }"""
            )
            for u in found:
                norm = normalize_gmaps_url(u)
                if norm:
                    urls.add(norm)

        print(f"Google Maps: {GMAPS_SEARCH}")
        page.goto(GMAPS_SEARCH, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(6000)
        collect_from_dom()

        loc = page.locator("button[aria-label*='Photo']")
        count = min(loc.count(), 40)
        print(f"  opening {count} photo thumbnails...")
        for i in range(count):
            try:
                loc.nth(i).click(timeout=1500)
                page.wait_for_timeout(350)
                collect_from_dom()
            except Exception:
                pass

        for _ in range(25):
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(350)
            collect_from_dom()

        for m in re.finditer(
            r"https://lh\d+\.googleusercontent\.com/[^\"'\\\s<>]+",
            page.content(),
        ):
            norm = normalize_gmaps_url(m.group(0))
            if norm:
                urls.add(norm)

        browser.close()

    return urls


def download_all(urls: list[str], prefix: str) -> int:
    from curl_cffi import requests as http

    session = http.Session(impersonate="chrome120")
    ok = 0
    for i, url in enumerate(urls, start=1):
        dest = OUT_DIR / f"{prefix}_{i:03d}.jpg"
        if dest.exists() and dest.stat().st_size > 5000:
            print(f"  [{i}] exists {dest.name}")
            ok += 1
            continue
        try:
            resp = session.get(url, timeout=90)
            resp.raise_for_status()
            data = resp.content
            if len(data) < 5000:
                continue
            dest.write_bytes(data)
            print(f"  [{i}] {dest.name} ({len(data):,} bytes)")
            ok += 1
        except Exception as exc:
            print(f"  [{i}] failed: {exc}")
    return ok


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output folder: {OUT_DIR}\n")

    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError:
        print("Install: pip install playwright curl_cffi")
        print("         playwright install chromium")
        return 1

    yelp_urls = sorted(scrape_yelp())
    if yelp_urls:
        print(f"\nDownloading {len(yelp_urls)} Yelp image(s)...\n")
        ok = download_all(yelp_urls, "yelp")
    else:
        print("\nYelp blocked — downloading Google Maps photos instead...\n")
        gmaps_urls = sorted(scrape_google_maps())
        if not gmaps_urls:
            print("No images found.")
            return 1
        print(f"\nDownloading {len(gmaps_urls)} Google Maps image(s)...\n")
        ok = download_all(gmaps_urls, "gmaps")

    print(f"\nDone: {ok} image(s) in {OUT_DIR}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
