import mysql.connector
from understatapi import UnderstatClient
import asyncio
import schedule
import time

league = input("League: ")
year = input("League Season: ")

def run_season_stats():
    # Step 1: Connect to the MySQL database
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Ihavesevenas123",
        # database="{year}_{league}_stats2_db"  # Ensure you're connecting to the correct database
    )

    cursor = conn.cursor()

    # Create the database if it doesn't exist
    cursor.execute("CREATE DATABASE IF NOT EXISTS stats")
    cursor.execute("USE stats")
    
    league = "EPL"
    year = "2024"

    # Step 2: Drop the table if it exists and recreate it
    cursor.execute(f'''
    DROP TABLE IF EXISTS {year}_{league}_stats
    ''')

    # Create table for player stats if it doesn't exist
    cursor.execute(f'''
    CREATE TABLE IF NOT EXISTS {year}_{league}_stats (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255),
        team VARCHAR(255),
        minutes INT,
        npGI_per_90 DECIMAL(10, 3),
        xGChain90 DECIMAL(10, 3),
        xGBuildup90 DECIMAL(10, 3),
        xGChain_xGBuildup DECIMAL(10, 3),
        npxGI90 DECIMAL(10, 3),
        SP_Chain_Buildup DECIMAL(10, 3),
        npG90 DECIMAL(10, 3),
        npxG90 DECIMAL(10, 3),
        shots90 DECIMAL(10, 3),
        assist90 DECIMAL(10, 3),
        xA_per_90 DECIMAL(10, 3),
        key_pass90 DECIMAL(10, 3),
        npGI DECIMAL(10, 3)
    )
    ''')

    # Step 3: Fetch player data without async with
    async def fetch_player_data():
        understat = UnderstatClient()  # Correct instantiation of UnderstatClient without async with

        # Fetch players data for the 2023 EPL season
        player_data = understat.league(league=league).get_player_data(season=year)

        # Insert relevant player data into the MySQL database
        for player in player_data:

            time = float(player['time'])
            npg = float(player['npg'])
            npxG = float(player['npxG'])
            xA = float(player['xA'])
            shots = float(player['shots'])
            keyP = float(player['key_passes'])
            xGChain = float(player['xGChain'])
            xGBuildup = float(player['xGBuildup'])
            assists = float(player['assists'])

            # Calculate per 90 metrics
            npxG90 = (npxG / time) * 90
            xA90 = (xA / time) * 90
            npG90 = (npg / time) * 90
            shots90 = (shots / time) * 90
            assists90 = (assists / time) * 90
            keyP90 = (keyP / time) * 90
            xGChain90 = (xGChain / time) * 90
            xGBuildup90 = (xGBuildup / time) * 90
            npxG_plus_xA_per_90 = npxG90 + xA90
            if npxG_plus_xA_per_90 == 0:
                percentxGIBuildup = 0
            else:
                percentxGIBuildup = (npxG_plus_xA_per_90 - (xGChain90 - xGBuildup90)) / npxG_plus_xA_per_90

            # Insert data into the MySQL database
            cursor.execute(f'''
            INSERT INTO {year}_{league}_stats (name, team, minutes, npGI_per_90, xGChain90, xGBuildup90, xGChain_xGBuildup, npxGI90, SP_Chain_Buildup, npG90, npxG90, shots90, assist90, xA_per_90, key_pass90, npGI)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,%s)
            ''', (
                player['player_name'], 
                player['team_title'], 
                int(time),
                npG90 + assists90,
                xGChain90,
                xGBuildup90,
                xGChain90 - xGBuildup90,
                npxG_plus_xA_per_90,
                percentxGIBuildup,
                npG90,
                npxG90,
                shots90,
                assists90,
                xA90,
                keyP90,
                npg + assists
            ))

        conn.commit()

    # Step 4: Run the async function to fetch and store player data
    asyncio.run(fetch_player_data())

    # Step 5: Close the MySQL connection
    cursor.close()
    conn.close()

# Schedule the job to run every day at a specific time, e.g., noon(12:00)
schedule.every().day.at("11:00").do(run_season_stats)

# Keep the script running to check for scheduled jobs
while True:
    schedule.run_pending()
    time.sleep(60)  # Check every minute