import re
import os
import time
import mysql.connector
from playwright.sync_api import Playwright, sync_playwright

def player_stats():
    # Step 1: Connect to the MySQL database
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        # database=os.getenv("DB_NAME")
    )
    
    cursor = conn.cursor()

    # Create the database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS stats")
    cursor.execute("USE stats")
    
    league = "EPL"
    year = "2024"
    
    cursor.execute(f'''
    DROP TABLE IF EXISTS {year}_{league}_stats
    ''')

    # Create the table for player stats if it doesn't exist
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {year}_{league}_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        Player VARCHAR(255),
        Team VARCHAR(255),
        Minutes INT,
        NpGI90 DECIMAL(10, 3),  # Goals + Assists per 90
        xA90 DECIMAL(10, 3),
        NPxG90_xA90 DECIMAL(10, 3),
        xGChain90 DECIMAL(10, 3),
        xGBuildup90 DECIMAL(10, 3)
    )
    ''')

    def insert_player_data(player_data):
        """Insert player data into the MySQL table."""
        sql = f'''INSERT INTO {year}_{league}_stats (Player, Team, Minutes, NpGI90, xA90, NPxG90_xA90, xGChain90, xGBuildup90) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'''
        values = (
            str(player_data["Player"]),
            str(player_data["Team"]),
            int(player_data["Minutes"]),
            float(player_data["NpGI90"]),
            float(player_data["xA90"]),
            float(player_data["NPxG90_xA90"]),
            float(player_data["xGChain90"]),
            float(player_data["xGBuildup90"])
        )
        cursor.execute(sql, values)
        conn.commit()

    def run(playwright: Playwright) -> None:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to the page
        page.goto("https://understat.com/league/EPL")
        
        # Perform necessary steps to filter and display the columns
        page.evaluate("document.querySelector('#league-players').scrollIntoView();")
        page.locator("#league-players").get_by_role("button").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div > .row-display > label").first.click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(6) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(7) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(11) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(14) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(15) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(18) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(19) > .row-display > label").click()
        page.locator("div:nth-child(20) > .row-display > label").click()
        page.locator("#league-players > .table-popup > .table-popup-body > .table-options > div:nth-child(9) > .row-display > label").click()
        # (Additional clicks for filters go here as needed)
        
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
                # Convert data types
                player = row.locator("td:nth-child(1)").inner_text(timeout=5000)
                team = row.locator("td:nth-child(2)").inner_text(timeout=5000)
                minutes = row.locator("td:nth-child(4)").inner_text(timeout=5000)
                npg = row.locator("td:nth-child(5)").inner_text(timeout=5000)
                assists = row.locator("td:nth-child(6)").inner_text(timeout=5000)
                xA90 = row.locator("td:nth-child(8)").inner_text(timeout=5000)
                nPxG90xA90 = row.locator("td:nth-child(9)").inner_text(timeout=5000)
                xgchain90 = row.locator("td:nth-child(10)").inner_text(timeout=5000)
                xgbuildup90 = row.locator("td:nth-child(11)").inner_text(timeout=5000)
                
                # Calculate NpGI90 (Goals + Assists per 90 minutes)
                

                # Append player data
            
                if player != "":
                    players.append({
                        "Player": player,
                        "Team": team,
                        "Minutes": minutes,
                        "NpGI90": npg + assists,
                        "xA90": xA90,
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
    conn.close()

player_stats()
