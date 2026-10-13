#!/usr/bin/env python3
"""Scrape Understat EPL player tables into data/season_stats.csv and data/form_stats.csv."""

import csv
import logging
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

URL = "https://understat.com/league/EPL"
TABLE = "#league-players table"
MAX_PAGES = 50
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SEASON_COLUMNS = ["Player", "Team", "Minutes", "NpGI90", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]
FORM_COLUMNS = ["Player", "Team", "Minutes", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]

# Normalised header text (lowercase, only a-z 0-9 +) -> accepted aliases
HEADER_ALIASES = {
    "player": {"player"},
    "team": {"team"},
    "minutes": {"min", "minutes"},
    "goals": {"g", "goals"},
    "assists": {"a", "assists"},
    "xa90": {"xa90"},
    "npxg90_xa90": {"npxg90+xa90", "npxg+xa90"},
    "xgchain90": {"xgchain90"},
    "xgbuildup90": {"xgbuildup90"},
}


def norm(text):
    return re.sub(r"[^a-z0-9+]", "", text.lower())


def to_float(text):
    try:
        return float(text.strip())
    except ValueError:
        return 0.0


def save_csv(rows, path, columns):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    logging.info("Saved %d records to %s", len(rows), path)


def configure_table_columns(page):
    """Turn on xGBuildup90, xGChain90 and NPxG90 + xA90 in the table options popup."""
    page.locator("button[name='table-options']").nth(1).click()
    time.sleep(1)
    for child in (20, 19, 18):  # xGBuildup90, xGChain90, NPxG90 + xA90
        try:
            page.locator(
                f"#league-players .table-options > div:nth-child({child}) > .row-display > label"
            ).click()
        except Exception as e:
            logging.warning("Could not toggle option %d: %s", child, e)
    page.locator("#league-players").get_by_text("Apply").click()
    time.sleep(2)


def read_table(page):
    """Return (headers, rows) as plain text lists, in one browser round trip each."""
    headers = page.locator(f"{TABLE} thead th").evaluate_all(
        "ths => ths.map(t => t.innerText.trim())"
    )
    rows = page.locator(f"{TABLE} tbody tr").evaluate_all(
        "trs => trs.map(r => Array.from(r.querySelectorAll('td')).map(td => td.innerText.trim()))"
    )
    return headers, rows


def map_columns(headers, need_goals_assists):
    """Map logical column names to indices using the table's header row."""
    normed = [norm(h) for h in headers]
    wanted = ["player", "team", "minutes", "xa90", "npxg90_xa90", "xgchain90", "xgbuildup90"]
    if need_goals_assists:
        wanted += ["goals", "assists"]
    cols = {}
    for name in wanted:
        for idx, h in enumerate(normed):
            if h in HEADER_ALIASES[name]:
                cols[name] = idx
                break
    missing = [n for n in wanted if n not in cols]
    if missing:
        raise RuntimeError(f"Columns not found in table headers: {missing}. Headers seen: {headers}")
    return cols


def go_to_page(page, number, old_first_player, player_idx):
    """Click the pagination link for `number`; return True once the table content changes."""
    # Page-wide search (the pagination may sit outside #league-players), skipping links inside tables
    links = page.locator("xpath=//a[not(ancestor::table)]").filter(
        has_text=re.compile(rf"^\s*{number}\s*$")
    )
    total = links.count()
    logging.info("Page %d: %d candidate pagination links", number, total)
    for i in range(total):
        link = links.nth(i)
        try:
            if not link.is_visible():
                continue
            link.click(timeout=3000)
        except Exception:
            continue
        deadline = time.time() + 6
        while time.time() < deadline:
            time.sleep(0.3)
            _, rows = read_table(page)
            if rows and len(rows[0]) > player_idx and rows[0][player_idx] != old_first_player:
                return True
    return False


def scrape_table(page, season):
    """Scrape every page of the players table. `season` adds NpGI90 (needs goals/assists)."""
    players = []
    cols = None
    for page_no in range(1, MAX_PAGES + 1):
        headers, rows = read_table(page)
        if cols is None:
            cols = map_columns(headers, need_goals_assists=season)
            logging.info("Column map: %s", cols)
        if not rows:
            break

        max_idx = max(cols.values())
        added = 0
        for row in rows:
            if len(row) <= max_idx or not row[cols["player"]]:
                continue
            try:
                minutes = int(row[cols["minutes"]])
            except ValueError:
                continue
            record = {
                "Player": row[cols["player"]],
                "Team": row[cols["team"]],
                "Minutes": minutes,
            }
            if season:
                goals = int(to_float(row[cols["goals"]]))
                assists = int(to_float(row[cols["assists"]]))
                record["NpGI90"] = (goals + assists) * 90 / minutes if minutes > 0 else 0.0
            record["xA90"] = to_float(row[cols["xa90"]])
            record["NPxG90_xA90"] = to_float(row[cols["npxg90_xa90"]])
            record["xGChain90"] = to_float(row[cols["xgchain90"]])
            record["xGBuildup90"] = to_float(row[cols["xgbuildup90"]])
            players.append(record)
            added += 1

        logging.info("Page %d: %d players (total %d)", page_no, added, len(players))

        if not go_to_page(page, page_no + 1, rows[0][cols["player"]], cols["player"]):
            logging.info("No further pages after page %d", page_no)
            break
    return players


def switch_to_last_5_games(page):
    page.get_by_text("All").nth(3).click()
    time.sleep(1)
    page.get_by_role("listitem").filter(has_text="5").first.click()
    time.sleep(1)
    page.locator("#players-filter").click()
    time.sleep(2)
    logging.info("Switched to last 5 games")


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            page.set_default_timeout(15000)

            logging.info("Opening %s", URL)
            page.goto(URL)
            page.wait_for_selector(TABLE)
            configure_table_columns(page)

            logging.info("=== Season data ===")
            season = scrape_table(page, season=True)
            if not season:
                raise RuntimeError("No season data extracted")
            save_csv(season, "data/season_stats.csv", SEASON_COLUMNS)

            logging.info("=== Form data (last 5 games) ===")
            switch_to_last_5_games(page)
            form = scrape_table(page, season=False)
            if not form:
                raise RuntimeError("No form data extracted")
            save_csv(form, "data/form_stats.csv", FORM_COLUMNS)
        except Exception:
            try:
                page.screenshot(path="screenshot.png")
                logging.info("Screenshot saved to screenshot.png")
            except Exception:
                pass
            raise
        finally:
            browser.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s", stream=sys.stdout)
    try:
        run()
    except Exception:
        logging.exception("Scraper failed")
        sys.exit(1)
    logging.info("Scraping completed successfully")


if __name__ == "__main__":
    main()