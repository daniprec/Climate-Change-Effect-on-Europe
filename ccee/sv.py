import argparse
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PRINT_URL = (
    "https://www.sozialversicherung.at/cdscontent/content_print.xhtml"
    "?contentid=10007.894919&print=true"
)

# German month name → month number (note "Jänner")
MONTHS_DE = {
    "Jänner": 1,
    "Januar": 1,
    "Februar": 2,
    "März": 3,
    "Maerz": 3,
    "April": 4,
    "Mai": 5,
    "Juni": 6,
    "Juli": 7,
    "August": 8,
    "September": 9,
    "Oktober": 10,
    "November": 11,
    "Dezember": 12,
}


def get_session():
    s = requests.Session()
    s.headers.update(
        {"User-Agent": "Mozilla/5.0 (compatible; sv-monatsberichte-downloader/1.0)"}
    )
    return s


def parse_listing(html: str):
    """
    Return a list of dicts: [{'year': 2025, 'month': 7, 'title': 'Monatsbericht Juli 2025', 'href': '...'}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    out = []

    # Each entry appears as an <a> whose text contains "Monatsbericht ..."
    for a in soup.find_all("a"):
        text = " ".join(a.get_text(strip=True).split())
        if not text.startswith("Monatsbericht"):
            continue

        # Try to pull month name and year from the anchor text
        # e.g., "Monatsbericht Juli 2025 ( Excel, 547 KB)"
        m = re.search(r"Monatsbericht\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})", text)
        if not m:
            continue
        month_name, year = m.group(1), int(m.group(2))
        month = MONTHS_DE.get(month_name, None)
        if month is None:
            # Some pages might use non-breaking spaces / variant spellings
            # Try a very loose fallback (first word after "Monatsbericht")
            month = MONTHS_DE.get(month_name.replace("\xa0", " "), None)
        href = a.get("href")
        if not href or "cdscontent/load" not in href:
            # Skip anything that doesn't look like a file endpoint
            continue

        out.append(
            {
                "year": year,
                "month": month,
                "title": text,
                "href": requests.compat.urljoin(PRINT_URL, href),
            }
        )
    # newest first on page; sort ascending if you prefer
    out.sort(key=lambda r: (r["year"], r["month"] or 99))
    return out


def choose(items, year_min=None, year_max=None):
    def ok(it):
        y = it["year"]
        if year_min is not None and y < year_min:
            return False
        if year_max is not None and y > year_max:
            return False
        return True

    return [it for it in items if ok(it)]


def safe_filename(year, month, title, url):
    # Prefer canonical pattern Mb_YYMM.xlsx if present in URL; else build our own.
    m = re.search(r"(Mb|MB)[\W_]?(\d{2})(\d{2})\.xlsx", url)
    if m:
        return f"{m.group(1)}_{m.group(2)}{m.group(3)}.xlsx"
    return f"Monatsbericht_{year:04d}-{month:02d}.xlsx"


def download_file(session, url, dest_path, retries=3, backoff=2.0):
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                # Try to extract a server-provided filename
                cd = r.headers.get("Content-Disposition", "")
                m = re.search(r'filename="?([^"]+)"?', cd)
                tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 15):
                        if chunk:
                            f.write(chunk)
                # If we got a name from headers and it's .xlsx, rename
                if m and m.group(1).lower().endswith(".xlsx"):
                    dest_path = dest_path.with_name(m.group(1))
                tmp_path.replace(dest_path)
                return dest_path
        except Exception:
            if attempt == retries:
                raise
            time.sleep(backoff * attempt)
    return dest_path


def main():
    ap = argparse.ArgumentParser(description="Download SV Monatsberichte (Excel)")
    ap.add_argument(
        "-o",
        "--out",
        default="data/monatsberichte",
        help="Output directory (default: data/monatsberichte)",
    )
    ap.add_argument("--year-min", type=int, default=None, help="Only >= this year")
    ap.add_argument("--year-max", type=int, default=None, help="Only <= this year")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    s = get_session()
    print("[INFO] Fetching listing…")
    html = s.get(PRINT_URL, timeout=30).text
    items = parse_listing(html)
    if not items:
        raise SystemExit(
            "No monthly links found — the page structure may have changed."
        )

    sel = choose(items, year_min=args.year_min, year_max=args.year_max)
    print(
        f"[INFO] Found {len(items)} months on the page; selected {len(sel)} after filtering."
    )

    for it in sel:
        if it["month"] is None:
            print(f"[WARN] Skipping (unknown month): {it['title']}")
            continue
        fname = safe_filename(it["year"], it["month"], it["title"], it["href"])
        fpath = outdir / fname
        if fpath.exists():
            print(f"[SKIP] {fname} (already present)")
            continue
        print(f"[GET ] {it['title']} -> {fname}")
        try:
            download_file(s, it["href"], fpath)
        except Exception as e:
            print(f"[FAIL] {fname}: {e}")

    print("[DONE] All requested files processed.")


if __name__ == "__main__":
    main()
