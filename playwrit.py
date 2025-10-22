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
        logging.FileHandler(f'form_stats_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)

def form_stats():
    csv_file_path = "data/form_stats.csv"
    columns = ["Player", "Team", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]

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
            
            logging.info("Navigating to understat.com for form stats...")
            page.goto("https://understat.com/league/EPL", timeout=30000)
            
            logging.info("Waiting for player table...")
            page.wait_for_selector("#league-players", timeout=15000)
            
            try:
                page.wait_for_selector("#league-players > table > tbody > tr", timeout=10000)
            except PlaywrightTimeout:
                logging.error("No player data found - season may not have started")
                return
            
            page.evaluate("document.querySelector('#league-players').scrollIntoView();")
            time.sleep(1)
            
            logging.info("Configuring table for form stats...")
            page.locator("#league-players").get_by_role("button").click()
            time.sleep(1)
            
            # Configure columns with minutes filter
            try:
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div > .row-display > label").first.click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(6) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(5) > .row-filter > input").first.click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(5) > .row-filter > input").first.fill("180")
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(8) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(9) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(11) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(14) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(15) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(18) > .row-display > label").click()
                page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(19) > .row-display > label").click()
                page.locator("div:nth-child(20) > .row-display > label").click()
            except Exception as e:
                logging.warning(f"Error configuring columns: {e}")
            
            time.sleep(1)
            page.locator("#league-players").get_by_text("Apply").click()
            time.sleep(2)
            
            # Select "5 games"
            try:
                page.locator("div").filter(has_text=re.compile(r"^All games$")).click(timeout=5000)
                page.locator("li").filter(has_text="5 games").click(timeout=5000)
            except Exception as e:
                logging.warning(f"Could not select '5 games': {e}")
            
            page.locator("#players-filter").click()
            page.wait_for_timeout(3000)

            players = []
            page_number = 1
            max_pages = 50
            
            while page_number <= max_pages:
                logging.info(f"Scraping form stats page {page_number}...")
                
                try:
                    rows = page.locator("#league-players > table > tbody > tr")
                    row_count = rows.count()
                    
                    if row_count == 0:
                        break
                    
                    for i in range(row_count):
                        try:
                            row = rows.nth(i)
                            player = row.locator("td:nth-child(1)").inner_text(timeout=3000).strip()
                            
                            if not player:
                                continue
                            
                            team = row.locator("td:nth-child(2)").inner_text(timeout=3000).strip()
                            xA90 = float(row.locator("td:nth-child(6)").inner_text(timeout=3000))
                            nPxG90xA90 = float(row.locator("td:nth-child(7)").inner_text(timeout=3000))
                            xgchain90 = float(row.locator("td:nth-child(8)").inner_text(timeout=3000))
                            xgbuildup90 = float(row.locator("td:nth-child(9)").inner_text(timeout=3000))
                            
                            players.append({
                                "Player": player,
                                "xA90": xA90,
                                "Team": team,
                                "NPxG90_xA90": nPxG90xA90,
                                "xGChain90": xgchain90,
                                "xGBuildup90": xgbuildup90
                            })
                        except Exception as e:
                            logging.warning(f"Error parsing row {i}: {e}")
                            continue
                    
                    next_button = page.locator("#league-players a").get_by_text(f"{page_number + 1}", exact=True)
                    if next_button.count() > 0:
                        next_button.click()
                        page.wait_for_selector("#league-players > table > tbody > tr", timeout=5000)
                        time.sleep(1)
                        page_number += 1
                    else:
                        break
                        
                except Exception as e:
                    logging.error(f"Error on page {page_number}: {e}")
                    break

            logging.info(f"Total players scraped (form): {len(players)}")
            
            if save_to_csv(players):
                logging.info("Form stats saved successfully")
            else:
                logging.error("Failed to save form stats")

        except Exception as e:
            logging.error(f"Fatal error in form_stats: {e}", exc_info=True)
            try:
                page.screenshot(path=f"error_screenshot_form_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
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
    logging.info("Starting form stats scraper")
    logging.info("=" * 50)
    form_stats()
    logging.info("Form stats scraper completed")