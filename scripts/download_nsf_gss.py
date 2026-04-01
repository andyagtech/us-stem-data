#!/usr/bin/env python3
"""
Download NSF GSS (Survey of Graduate Students and Postdoctorates in S&E) data.

Strategy:
  1. Try direct URL download for the user guide PDF (usually works).
  2. Use Playwright to navigate the NCSES microdata portal, accept any
     terms-of-use forms, and download the public-use data file.

Usage:
    python scripts/download_nsf_gss.py [--year 2023] [--headed]
"""

import argparse
import io
import os
import sys
import time
import zipfile

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "nsf_gss")

# NCSES microdata portal — the main entry point for PUF downloads
MICRODATA_PAGE = "https://ncses.nsf.gov/explore-data/microdata/graduate-students-postdoctorates-s-e"

# Survey overview page (has links to docs, data tables, etc.)
SURVEY_PAGE = "https://ncses.nsf.gov/surveys/graduate-students-postdoctorates-s-e/{year}"

# Direct URLs for supplemental files
DIRECT_URLS = {
    "user_guide": [
        "https://ncses.nsf.gov/826/assets/0/files/gss-{year}-puf-user-guide.pdf",
    ],
    "puf_data": [
        "https://ncses.nsf.gov/explore-data/microdata/download/graduate-students-postdoctorates-s-e/{year}",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# ---------------------------------------------------------------------------
# Direct download helpers
# ---------------------------------------------------------------------------

def try_direct_download(url: str, output_path: str, label: str) -> bool:
    """Attempt a direct HTTP download. Returns True on success."""
    print(f"  [direct] {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=120, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")

        # Reject HTML pages that aren't actual data
        if "text/html" in content_type and len(resp.content) < 100_000:
            print(f"  Got HTML landing page instead of data — skipping.")
            return False

        # Handle ZIP
        if resp.content[:4] == b"PK\x03\x04" or "zip" in content_type:
            try:
                with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                    zf.extractall(os.path.dirname(output_path))
                    print(f"  Extracted ZIP: {zf.namelist()}")
                    return True
            except zipfile.BadZipFile:
                pass

        # Save as-is
        with open(output_path, "wb") as f:
            f.write(resp.content)
        size_mb = len(resp.content) / (1024 * 1024)
        print(f"  Saved {label}: {os.path.basename(output_path)} ({size_mb:.1f} MB)")
        return True

    except requests.RequestException as e:
        print(f"  Direct download failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Playwright browser download
# ---------------------------------------------------------------------------

def playwright_download_gss(year: int, output_dir: str, headed: bool) -> bool:
    """
    Use Playwright to navigate the NCSES microdata portal and download
    the GSS public-use data file for the given year.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: playwright is not installed. Run: pip install playwright && playwright install chromium")
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # ------------------------------------------------------------------
        # Step 1: Navigate to the microdata portal
        # ------------------------------------------------------------------
        print(f"\n[Playwright] Navigating to NCSES microdata portal...")
        page.goto(MICRODATA_PAGE, wait_until="networkidle", timeout=60000)
        time.sleep(3)

        # ------------------------------------------------------------------
        # Step 2: Look for a download link or button for the target year
        # ------------------------------------------------------------------
        # The page may list multiple years. Try to find a link with the year.
        print(f"[Playwright] Looking for {year} download link...")

        # Try clicking a year-specific download link
        download_started = False
        for selector in [
            f"a:has-text('{year}')",
            f"a[href*='{year}']",
            f"button:has-text('{year}')",
            "a:has-text('Download')",
            "button:has-text('Download')",
            "a:has-text('Public Use')",
            "a:has-text('Data File')",
        ]:
            try:
                link = page.locator(selector).first
                if link.is_visible(timeout=3000):
                    text = link.text_content().strip()
                    print(f"  Found link: '{text}'")
                    link.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    time.sleep(2)
                    download_started = True
                    break
            except Exception:
                continue

        if not download_started:
            print("  No direct download link found on microdata page.")
            # Try navigating to the survey page instead
            survey_url = SURVEY_PAGE.format(year=year)
            print(f"[Playwright] Trying survey page: {survey_url}")
            page.goto(survey_url, wait_until="networkidle", timeout=60000)
            time.sleep(3)

        # ------------------------------------------------------------------
        # Step 3: Handle terms-of-use / agreement page if present
        # ------------------------------------------------------------------
        _handle_terms_of_use(page)

        # ------------------------------------------------------------------
        # Step 4: Find and click the actual data download
        # ------------------------------------------------------------------
        print(f"[Playwright] Attempting to trigger download...")
        downloaded_path = _find_and_download(page, year, output_dir)

        if downloaded_path:
            print(f"  Download saved: {downloaded_path}")
            browser.close()
            return True

        # ------------------------------------------------------------------
        # Step 5: If we're on a page with data tables, try the microdata link
        # ------------------------------------------------------------------
        for selector in [
            "a:has-text('microdata')",
            "a:has-text('Public Use File')",
            "a:has-text('PUF')",
            "a[href*='microdata']",
            "a[href*='download']",
        ]:
            try:
                link = page.locator(selector).first
                if link.is_visible(timeout=2000):
                    link.click()
                    page.wait_for_load_state("networkidle", timeout=15000)
                    time.sleep(2)
                    _handle_terms_of_use(page)
                    downloaded_path = _find_and_download(page, year, output_dir)
                    if downloaded_path:
                        print(f"  Download saved: {downloaded_path}")
                        browser.close()
                        return True
            except Exception:
                continue

        # Take a screenshot for debugging if headed
        if headed:
            screenshot_path = os.path.join(output_dir, "debug_screenshot.png")
            page.screenshot(path=screenshot_path)
            print(f"  Debug screenshot saved: {screenshot_path}")

        browser.close()

    print("  Playwright could not locate and download the data file.")
    return False


def _handle_terms_of_use(page) -> None:
    """Check for and accept any terms-of-use / agreement form."""
    for selector in [
        "input[type='checkbox']",
        "button:has-text('Agree')",
        "button:has-text('Accept')",
        "button:has-text('I Agree')",
        "a:has-text('Agree')",
        "input[type='submit'][value*='Agree']",
        "input[type='submit'][value*='Accept']",
    ]:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=2000):
                el.click()
                print(f"  Accepted terms of use ({selector})")
                page.wait_for_load_state("networkidle", timeout=15000)
                time.sleep(2)
        except Exception:
            continue


def _find_and_download(page, year: int, output_dir: str) -> str | None:
    """Try to find a download link on the current page and save the file."""
    download_selectors = [
        f"a[href*='download'][href*='{year}']",
        "a[href$='.zip']",
        "a[href$='.csv']",
        "a:has-text('Download CSV')",
        "a:has-text('Download Data')",
        "a:has-text('Download')",
        "button:has-text('Download')",
    ]

    for selector in download_selectors:
        try:
            link = page.locator(selector).first
            if link.is_visible(timeout=2000):
                text = link.text_content().strip()
                href = link.get_attribute("href") or ""
                print(f"  Trying download via: '{text}' (href: ...{href[-50:]})")

                with page.expect_download(timeout=120000) as download_info:
                    link.click()

                download = download_info.value
                suggested = download.suggested_filename or f"gss_{year}_puf.zip"
                dest = os.path.join(output_dir, suggested)
                download.save_as(dest)

                # Extract ZIP if needed
                if dest.endswith(".zip"):
                    try:
                        with zipfile.ZipFile(dest) as zf:
                            zf.extractall(output_dir)
                            print(f"  Extracted: {zf.namelist()}")
                    except zipfile.BadZipFile:
                        pass

                return dest
        except Exception:
            continue

    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def list_output_files(output_dir: str) -> None:
    """Print all files in the output directory."""
    print("\nFiles in output directory:")
    for f in sorted(os.listdir(output_dir)):
        path = os.path.join(output_dir, f)
        if os.path.isfile(path):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            print(f"  {f:50s} ({size_mb:.1f} MB)")


def print_manual_instructions(year: int):
    """Print manual download instructions as last resort."""
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║  MANUAL DOWNLOAD REQUIRED                                       ║
╚══════════════════════════════════════════════════════════════════╝

Both direct-URL and Playwright downloads failed for the GSS data.
Please download manually:

Step 1: Visit the GSS Microdata page:
  {MICRODATA_PAGE}

Step 2: Look for the {year} Public Use File download link.
  - You may need to agree to terms of use.
  - Download the ZIP file containing the CSV data.

Step 3: Also visit the survey page for documentation:
  {SURVEY_PAGE.format(year=year)}

Step 4: Place downloaded files in:
  {os.path.abspath(OUTPUT_DIR)}

Then run:
  python scripts/nsf_gss_filter.py --year {year}
""")


def main():
    parser = argparse.ArgumentParser(description="Download NSF GSS data files.")
    parser.add_argument(
        "--year", type=int, default=2023,
        help="GSS survey year to download (default: 2023)",
    )
    parser.add_argument(
        "--headed", action="store_true",
        help="Run browser in headed mode (visible) for debugging",
    )
    args = parser.parse_args()
    year = args.year

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"=== NSF GSS Download: Year {year} ===")
    print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}\n")

    # ---- Try direct downloads first ----
    data_ok = False
    print("Attempting direct URL downloads...")
    for url_template in DIRECT_URLS["puf_data"]:
        url = url_template.format(year=year)
        output_path = os.path.join(OUTPUT_DIR, f"gss_{year}_puf.csv")
        if try_direct_download(url, output_path, "PUF data"):
            data_ok = True
            break

    guide_ok = False
    print("\nDownloading user guide / codebook...")
    for url_template in DIRECT_URLS["user_guide"]:
        url = url_template.format(year=year)
        output_path = os.path.join(OUTPUT_DIR, f"gss-{year}-puf-user-guide.pdf")
        if try_direct_download(url, output_path, "User Guide"):
            guide_ok = True
            break

    if data_ok:
        print("\nDirect download succeeded for data file.")
        list_output_files(OUTPUT_DIR)
        return

    # ---- Fallback: Playwright browser automation ----
    print("\nDirect download failed for data. Falling back to Playwright...")
    if playwright_download_gss(year, OUTPUT_DIR, args.headed):
        print("\nPlaywright download completed.")
        list_output_files(OUTPUT_DIR)
        return

    # ---- Last resort: manual instructions ----
    if guide_ok:
        print("\nUser guide was downloaded, but data file requires manual download.")
    print_manual_instructions(year)
    sys.exit(1)


if __name__ == "__main__":
    main()
