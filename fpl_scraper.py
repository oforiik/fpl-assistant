#!/usr/bin/env python3

import os
import sys
import time
import logging
import re
import csv
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Set up logging
def setup_logging():
    """Set up logging configuration"""
    log_filename = f"fpl_scraper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    
    # Create handlers
    file_handler = logging.FileHandler(log_filename)
    file_handler.setFormatter(file_formatter)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    
    # Configure logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return log_filename

def get_current_season():
    """Get current season in format 2026/27"""
    current_year = datetime.now().year
    # FPL season runs from August to May, so if we're in Jan-July, it's still the previous season
    if datetime.now().month < 8:
        season_start = current_year - 1
    else:
        season_start = current_year
    
    season_end = str(season_start + 1)[-2:]  # Get last 2 digits
    return f"{season_start}/{season_end}"

class FPLScraper:
    def __init__(self):
        self.current_season = get_current_season()
        logging.info(f"Initialized scraper for season {self.current_season}")

    def save_to_csv(self, data, filepath, columns):
        """Save data to CSV file"""
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
            
            logging.info(f"Saved {len(data)} records to {filepath}")
            return True
        except Exception as e:
            logging.error(f"Error saving to {filepath}: {e}")
            return False

    def configure_table_columns(self, page):
        """Configure table to show all necessary columns including xGChain90 and xGBuildup90"""
        try:
            logging.info("Configuring table columns...")
            
            # Click table options button
            page.locator("button[name='table-options']").nth(1).click()
            time.sleep(2)
            
            # Use exact selectors from your codegen
            try:
                # Enable xGBuildup90 column (div 20)
                page.locator("div:nth-child(20) > .row-display > label").click()
                logging.info("Enabled xGBuildup90 column")
            except Exception as e:
                logging.warning(f"Could not enable xGBuildup90: {e}")
            
            try:
                # Enable xGChain90 column (div 19)
                page.locator("#league-players > .custom-scroll_inner > .table-popup-wrapper > .table-popup-container > .table-popup > .table-popup-body > .table-options > div:nth-child(19) > .row-display > label").click()
                logging.info("Enabled xGChain90 column")
            except Exception as e:
                logging.warning(f"Could not enable xGChain90: {e}")
            
            try:
                # Enable NPxG90 + xA90 column (div 18)
                page.locator("#league-players > .custom-scroll_inner > .table-popup-wrapper > .table-popup-container > .table-popup > .table-popup-body > .table-options > div:nth-child(18) > .row-display > label").click()
                logging.info("Enabled NPxG90 + xA90 column")
            except Exception as e:
                logging.warning(f"Could not enable NPxG90 + xA90: {e}")
            
            # Apply changes
            try:
                page.locator("#league-players").get_by_text("Apply").click()
                time.sleep(3)
                logging.info("Applied table column changes")
            except Exception as e:
                logging.warning(f"Could not apply changes: {e}")
            
            logging.info("Table column configuration completed")
            return True
            
        except Exception as e:
            logging.warning(f"Could not configure table columns: {e}")
            # Continue without advanced columns if configuration fails
            return False

    def scrape_players_table(self, page, is_season_data=True):
        """Scrape all pages of the players table with proper column extraction"""
        all_players = []
        page_number = 1
        max_pages = 50  # Scan all pages
        
        while page_number <= max_pages:
            try:
                logging.info(f"Scraping page {page_number}...")
                
                # Get the players table
                players_table = page.locator("#league-players table")
                rows = players_table.locator("tbody tr")
                row_count = rows.count()
                
                if row_count == 0:
                    logging.warning(f"No player data rows found on page {page_number}")
                    break
                
                # Process all rows on current page
                page_players = []
                for row_idx in range(row_count):
                    try:
                        row = rows.nth(row_idx)
                        cells = row.locator("td")
                        
                        if cells.count() < 10:
                            continue
                        
                        # Extract basic data based on the NEW table structure after enabling columns:
                        # Based on debug output: Col11=xGChain90, Col12=xGBuildup90, Col13=xA90
                        
                        player_name = cells.nth(1).inner_text(timeout=2000).strip()
                        team_name = cells.nth(2).inner_text(timeout=2000).strip()
                        
                        # Skip header rows or invalid data
                        if not player_name or player_name in ["Player", "№", ""]:
                            continue
                        
                        try:
                            minutes = int(cells.nth(4).inner_text(timeout=2000).strip())
                            goals = int(cells.nth(5).inner_text(timeout=2000).strip())
                            assists = int(cells.nth(6).inner_text(timeout=2000).strip())
                            
                            # Extract all potential metric values from columns 10-17
                            col_values = {}
                            for i in range(10, min(cells.count(), 18)):
                                try:
                                    val_text = cells.nth(i).inner_text(timeout=1000).strip()
                                    if val_text.replace('.', '').replace('-', '').isdigit():
                                        col_values[i] = float(val_text)
                                    else:
                                        col_values[i] = 0.0
                                except:
                                    col_values[i] = 0.0
                            
                            # Try to identify the correct columns based on reasonable value ranges
                            xa90 = 0.0
                            npxg90_xa90 = 0.0 
                            xg_chain90 = 0.0
                            xg_buildup90 = 0.0
                            
                            # Find xA90 (typically 0.0-1.0, smaller values)
                            for col, val in col_values.items():
                                if 0.0 <= val <= 1.0 and xa90 == 0.0:
                                    xa90 = val
                                    break
                            
                            # Find NPxG90+xA90 (typically 0.5-3.0, larger combined values)  
                            for col, val in col_values.items():
                                if 0.5 <= val <= 3.0 and npxg90_xa90 == 0.0:
                                    npxg90_xa90 = val
                                    break
                            
                            # Find xGChain90 (typically 0.5-2.0, medium values)
                            for col, val in col_values.items():
                                if 0.3 <= val <= 2.5 and val != xa90 and val != npxg90_xa90 and xg_chain90 == 0.0:
                                    xg_chain90 = val
                                    break
                            
                            # Find xGBuildup90 (typically 0.1-1.5, smaller than xGChain90)
                            for col, val in col_values.items():
                                if 0.0 <= val <= 1.5 and val != xa90 and val != npxg90_xa90 and val != xg_chain90 and xg_buildup90 == 0.0:
                                    xg_buildup90 = val
                                    break
                            
                        except (ValueError, IndexError) as e:
                            logging.warning(f"Error parsing data for {player_name}: {e}")
                            continue
                        
                        # Calculate NpGI90 (Non-penalty Goals + Assists per 90)
                        npgi90 = (goals + assists) * 90 / minutes if minutes > 0 else 0.0
                        
                        if is_season_data:
                            record = {
                                "Player": player_name,
                                "Team": team_name,
                                "Minutes": minutes,
                                "NpGI90": npgi90,
                                "xA90": xa90,
                                "NPxG90_xA90": npxg90_xa90,
                                "xGChain90": xg_chain90,
                                "xGBuildup90": xg_buildup90
                            }
                        else:
                            record = {
                                "Player": player_name,
                                "Team": team_name,
                                "Minutes": minutes,
                                "xA90": xa90,
                                "NPxG90_xA90": npxg90_xa90,
                                "xGChain90": xg_chain90,
                                "xGBuildup90": xg_buildup90
                            }
                        
                        page_players.append(record)
                        
                    except Exception as e:
                        logging.warning(f"Error processing row {row_idx} on page {page_number}: {e}")
                        continue
                
                all_players.extend(page_players)
                logging.info(f"Page {page_number}: Extracted {len(page_players)} players (total: {len(all_players)})")
                
                # Navigate to next page using the pattern from your codegen
                next_page = page_number + 1
                
                try:
                    # Pattern: pages 2-3 use nth(4), pages 4+ use nth(2)
                    nth_values_to_try = [4, 2, 1, 0] if next_page <= 3 else [2, 4, 1, 0]
                    
                    next_page_clicked = False
                    
                    for nth_val in nth_values_to_try:
                        try:
                            page_link = page.locator("a").filter(has_text=re.compile(f"^{next_page}$"))
                            
                            if page_link.count() > nth_val:
                                page_link.nth(nth_val).click()
                                time.sleep(1)
                                
                                # Wait for new content
                                page.wait_for_selector("#league-players table tbody tr", timeout=5000)
                                
                                # Verify page change
                                new_rows = page.locator("#league-players table tbody tr")
                                if new_rows.count() > 0:
                                    new_first_player = new_rows.nth(0).locator("td").nth(1).inner_text(timeout=1000)
                                    old_first_player = page_players[0]["Player"] if page_players else ""
                                    
                                    if new_first_player != old_first_player:
                                        logging.info(f"✓ Page {next_page} loaded (first: {new_first_player})")
                                        next_page_clicked = True
                                        break
                            
                        except Exception:
                            continue
                    
                    if not next_page_clicked:
                        logging.info(f"End of pagination reached at page {page_number}")
                        break
                    
                    page_number = next_page
                    
                except Exception as e:
                    logging.info(f"Pagination ended: {e}")
                    break
                    
            except Exception as e:
                logging.error(f"Error on page {page_number}: {e}")
                break
        
        logging.info(f"Scraping completed. Total players: {len(all_players)} across {page_number} pages")
        return all_players

    def scrape_understat_data(self, data_type="both"):
        """Main scraping function"""
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                # Navigate to understat EPL page
                logging.info("Navigating to understat.com...")
                page.goto("https://understat.com/league/EPL")
                
                # Wait for players table
                page.wait_for_selector("#league-players table", timeout=15000)
                
                # Configure table to show all columns
                self.configure_table_columns(page)
                
                if data_type in ["both", "season"]:
                    logging.info("=== SCRAPING SEASON DATA ===")
                    season_players = self.scrape_players_table(page, is_season_data=True)
                    
                    if season_players:
                        season_columns = ["Player", "Team", "Minutes", "NpGI90", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]
                        self.save_to_csv(season_players, "data/season_stats.csv", season_columns)
                        logging.info(f"Season data saved: {len(season_players)} players")
                    else:
                        logging.warning("No season data extracted")
                
                if data_type in ["both", "form"]:
                    logging.info("=== SCRAPING FORM DATA (5 games) ===")
                    
                    # Switch to 5 games view
                    all_buttons = page.get_by_text("All")
                    if all_buttons.count() > 3:
                        all_buttons.nth(3).click()
                        time.sleep(1)
                        
                        # Select 5 games
                        page.get_by_role("listitem").filter(has_text="5").first.click()
                        time.sleep(2)
                        
                        logging.info("Switched to 5 games view")
                        
                        # Click the filter button to apply the view change
                        try:
                            filter_button = page.locator("#players-filter")
                            if filter_button.count() > 0:
                                filter_button.click()
                                time.sleep(2)
                                logging.info("Clicked players filter button")
                            else:
                                logging.warning("Players filter button not found")
                        except Exception as e:
                            logging.warning(f"Could not click players filter button: {e}")
                        
                        form_players = self.scrape_players_table(page, is_season_data=False)
                        
                        if form_players:
                            form_columns = ["Player", "Team", "Minutes", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]
                            self.save_to_csv(form_players, "data/form_stats.csv", form_columns)
                            logging.info(f"Form data saved: {len(form_players)} players")
                        else:
                            logging.warning("No form data extracted")
                    else:
                        logging.warning("Could not find 'All' button for games filter")
                
            except Exception as e:
                logging.error(f"Scraping failed: {e}")
                return False
            finally:
                browser.close()
        
        return True

def main():
    """Main function"""
    log_filename = setup_logging()
    
    logging.info("=" * 60)
    logging.info("FPL UNIFIED SCRAPER STARTING")
    logging.info("=" * 60)
    
    scraper = FPLScraper()
    
    try:
        # Scrape both season and form data
        success = scraper.scrape_understat_data(data_type="both")
        
        if success:
            logging.info("=" * 60)
            logging.info("SCRAPING COMPLETED SUCCESSFULLY")
            logging.info("=" * 60)
            
            # Verify output files
            if os.path.exists("data/season_stats.csv"):
                logging.info("✓ data/season_stats.csv: Created successfully")
            else:
                logging.warning("✗ data/season_stats.csv: File not created")
            
            if os.path.exists("data/form_stats.csv"):
                logging.info("✓ data/form_stats.csv: Created successfully")  
            else:
                logging.warning("✗ data/form_stats.csv: File not created")
                
        else:
            logging.error("Scraping failed")
            
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        return False
    
    logging.info(f"Log saved to: {log_filename}")
    return True

if __name__ == "__main__":
    main()