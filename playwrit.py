import re
import time
import pandas as pd
from playwright.sync_api import Playwright, sync_playwright

def form_stats():
    # Define the CSV file path (using a relative path for GitHub compatibility)
    csv_file_path = "data/form_stats.csv"  # Ensure the `data` directory exists or adjust the path

    # Define column names
    columns = ["Player", "Team", "xA90", "NPxG90_xA90", "xGChain90", "xGBuildup90"]

    # Create the CSV file with headers if it doesn't exist
    try:
        pd.DataFrame(columns=columns).to_csv(csv_file_path, index=True)
    except Exception as e:
        print(f"Error initializing CSV file: {e}")

    # Function to save player data to CSV
    def save_to_csv(data):
        """Save player data to CSV, replacing any existing content."""
        df = pd.DataFrame(data, columns=columns)
        df.to_csv(csv_file_path, index=False)  # Replace the CSV content with the new data

    def run(playwright: Playwright) -> None:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to the page
        page.goto("https://understat.com/league/EPL")
        
        # Perform the necessary steps to filter and display the columns
        page.evaluate("document.querySelector('#league-players').scrollIntoView();")
        page.locator("#league-players").get_by_role("button").click()
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
        time.sleep(1)  # Wait for the table to be updated
        page.locator("#league-players").get_by_text("Apply").click()
        page.locator("div").filter(has_text=re.compile(r"^All games$")).click()
        page.locator("li").filter(has_text="5 games").click()
        page.locator("#players-filter").click()

        # Wait until the table rows are visible
        page.wait_for_selector("#league-players > table > tbody > tr")
        page.wait_for_timeout(3000) 

        # Scrape the table data
        players = []
        rows = page.locator("#league-players > table > tbody > tr")

        # Pagination handling
        page_number = 1
        while True:
            print(f"Scraping page {page_number}...")

            # Scrape data from the current page
            row_count = rows.count()
            for i in range(row_count):
                row = rows.nth(i)
                player = row.locator("td:nth-child(1)").inner_text(timeout=5000)  # Column: Player
                team = row.locator("td:nth-child(2)").inner_text(timeout=5000)  # Column: Team
                xA90 = row.locator("td:nth-child(6)").inner_text(timeout=5000)  # Column: xA90
                nPxG90xA90 = row.locator("td:nth-child(7)").inner_text(timeout=5000)  # Column: NPxG90_xA90
                xgchain90 = row.locator("td:nth-child(8)").inner_text(timeout=5000)  # Column: xGChain90
                xgbuildup90 = row.locator("td:nth-child(9)").inner_text(timeout=5000)  # Column: xGBuildup90
                
                if player != "":
                    players.append({
                        "Player": player,
                        "xA90": float(xA90),
                        "Team": team,
                        "NPxG90_xA90": float(nPxG90xA90),
                        "xGChain90": float(xgchain90),
                        "xGBuildup90": float(xgbuildup90)
                    })

            # Try to go to the next page
            next_button = page.locator("#league-players a").get_by_text(f"{page_number + 1}", exact=True)
            if next_button.count() > 0:
                next_button.click()
                page.wait_for_selector("#league-players > table > tbody > tr")
                time.sleep(1)  # Wait for page change
                page_number += 1
            else:
                break

        # Print or process the extracted data
        save_to_csv(players)
        print("form_stats.csv data saved")

        # Close the browser
        context.close()
        browser.close()

    # Run the script using Playwright
    with sync_playwright() as playwright:
        run(playwright)

form_stats()