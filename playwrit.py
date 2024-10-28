import re
import os
import time
import mysql.connector
import asyncio
from playwright.sync_api import Playwright, sync_playwright
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def form_stats():
    # Step 1: Set up SQLAlchemy engine for the PostgreSQL connection
    conn_str = os.getenv("DATABASE_URL")
    engine = create_engine(conn_str)

    # Create the database table if it doesn't exist
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS form_stats"))
        
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS form_stats (
                id SERIAL PRIMARY KEY,
                Player VARCHAR(255),
                xA90 DECIMAL(10, 3),
                Team VARCHAR(255),
                NPxG90_xA90 DECIMAL(10, 3),
                xGChain90 DECIMAL(10, 3),
                xGBuildup90 DECIMAL(10, 3)
            )
        '''))

    # Function to insert player data into the database
    def insert_player_data(player_data):
        """Insert player data into the form_stats table."""
        try:
            with engine.connect() as conn:
                sql = text('''INSERT INTO form_stats (Player, xA90, Team, NPxG90_xA90, xGChain90, xGBuildup90) 
                              VALUES (:Player, :xA90, :Team, :NPxG90_xA90, :xGChain90, :xGBuildup90)''')
                conn.execute(sql, **player_data)
        except SQLAlchemyError as e:
            print(f"Error inserting data: {e}")
            
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
        page.locator("li").filter(has_text="10 games").click()
        page.locator("#players-filter").click()
        time.sleep(10)

        # Wait until the table rows are visible
        page.wait_for_selector("#league-players > table > tbody > tr")

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
                        "xA90": xA90,
                        "Team": team,
                        "NPxG90_xA90": nPxG90xA90,
                        "xGChain90": xgchain90,
                        "xGBuildup90": xgbuildup90
                    })

            # Try to go to the next page
            next_button = page.locator("#league-players a").get_by_text(f"{page_number}", exact=True)
            if next_button.count() > 0:
                next_button.click()
                page.wait_for_selector("#league-players > table > tbody > tr")
                time.sleep(1)  # Wait for page change
                page_number += 1
            else:
                break

        # Print or process the extracted data
        for player in players:
            print(player)
            insert_player_data(player)

        # Close the browser
        context.close()
        browser.close()

    # Run the script using Playwright
    with sync_playwright() as playwright:
        run(playwright)

    # Close the MySQL connection
    conn_str.close()

form_stats()