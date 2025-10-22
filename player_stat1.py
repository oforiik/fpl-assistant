import re
import time
import pandas as pd
from playwright.sync_api import Playwright, sync_playwright, TimeoutError as PlaywrightTimeout
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'season_stats_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

def season_stats():
    csv_file_path = "data/season_stats.csv"
    columns = ["Player", "Team", "Minutes", "NpGI90", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]

    def save_to_csv(data):
        if not data:
            logging.warning("No data to save!")
            return False
        df = pd.DataFrame(data, columns=columns)
        df.to_csv(csv_file_path, index=False)
        logging.info(f"Saved {len(data)} records to {csv_file_path}")
        return True

    def run(playwright: Playwright) -> None:
        browser = None
        try:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            
            logging.info("Navigating to understat.com...")
            page.goto("https://understat.com/league/EPL", timeout=30000)
            
            # Wait for the table to load
            logging.info("Waiting for player table...")
            page.wait_for_selector("#league-players", timeout=15000)
            
            # Check if table has data
            try:
                page.wait_for_selector("#league-players > table > tbody > tr", timeout=10000)
            except PlaywrightTimeout:
                logging.error("No player data found in table - season may not have started yet")
                return
            
            # Scroll and open settings
            page.evaluate("document.querySelector('#league-players').scrollIntoView();")
            time.sleep(1)
            
            logging.info("Configuring table columns...")
            page.locator("#league-players").get_by_role("button").click()
            time.sleep(1)
            
            # Configure columns (with error handling)
            column_selectors = [
                "#league-players > .table-popup > .table-popup-body > .table-options > div > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(6) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(7) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(11) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(14) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(15) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(18) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(19) > .row-display > label",
                "div:nth-child(20) > .row-display > label",
                "#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(9) > .row-display > label"
            ]
            
            for selector in column_selectors:
                try:
                    page.locator(selector).first.click(timeout=2000)
                except Exception as e:
                    logging.warning(f"Could not click selector {selector}: {e}")
            
            time.sleep(1)
            page.locator("#league-players").get_by_text("Apply").click()
            time.sleep(2)
            
            # Select "All games"
            try:
                page.locator("div").filter(has_text=re.compile(r"^All games$")).click(timeout=5000)
                page.locator("li").filter(has_text="All games").click(timeout=5000)
            except Exception as e:
                logging.warning(f"Could not select 'All games': {e}")
            
            page.locator("#players-filter").click()
            page.wait_for_timeout(3000)

            # Scrape data
            players = []
            page_number = 1
            max_pages = 50  # Safety limit
            
            while page_number <= max_pages:
                logging.info(f"Scraping page {page_number}...")
                
                try:
                    rows = page.locator("#league-players > table > tbody > tr")
                    row_count = rows.count()
                    
                    if row_count == 0:
                        logging.warning("No rows found on this page")
                        break
                    
                    for i in range(row_count):
                        try:
                            row = rows.nth(i)
                            player = row.locator("td:nth-child(1)").inner_text(timeout=3000).strip()
                            
                            if not player:
                                continue
                            
                            team = row.locator("td:nth-child(2)").inner_text(timeout=3000).strip()
                            minutes = int(row.locator("td:nth-child(4)").inner_text(timeout=3000))
                            npg = float(row.locator("td:nth-child(5)").inner_text(timeout=3000))
                            assists = float(row.locator("td:nth-child(6)").inner_text(timeout=3000))
                            xA90 = float(row.locator("td:nth-child(8)").inner_text(timeout=3000))
                            nPxG90xA90 = float(row.locator("td:nth-child(9)").inner_text(timeout=3000))
                            xgchain90 = float(row.locator("td:nth-child(10)").inner_text(timeout=3000))
                            xgbuildup90 = float(row.locator("td:nth-child(11)").inner_text(timeout=3000))
                            
                            players.append({
                                "Player": player,
                                "Team": team,
                                "Minutes": minutes,
                                "NpGI90": (npg + assists) * 90 / minutes if minutes > 0 else 0,
                                "xA90": xA90,
                                "NPxG90_xA90": nPxG90xA90,
                                "xGChain90": xgchain90,
                                "xGBuildup90": xgbuildup90
                            })
                        except Exception as e:
                            logging.warning(f"Error parsing row {i}: {e}")
                            continue
                    
                    # Try next page
                    next_button = page.locator("#league-players a").get_by_text(f"{page_number + 1}", exact=True)
                    if next_button.count() > 0:
                        next_button.click()
                        page.wait_for_selector("#league-players > table > tbody > tr", timeout=5000)
                        time.sleep(1)
                        page_number += 1
                    else:
                        logging.info("No more pages to scrape")
                        break
                        
                except Exception as e:
                    logging.error(f"Error on page {page_number}: {e}")
                    break

            logging.info(f"Total players scraped: {len(players)}")
            
            if save_to_csv(players):
                logging.info("Season stats saved successfully")
            else:
                logging.error("Failed to save season stats")

        except Exception as e:
            logging.error(f"Fatal error in season_stats: {e}", exc_info=True)
            # Take screenshot for debugging
            try:
                page.screenshot(path=f"error_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            except:
                pass
        finally:
            if browser:
                context.close()
                browser.close()

    with sync_playwright() as playwright:
        run(playwright)

if __name__ == "__main__":
    logging.info("=" * 50)
    logging.info("Starting season stats scraper")
    logging.info("=" * 50)
    season_stats()
    logging.info("Season stats scraper completed")