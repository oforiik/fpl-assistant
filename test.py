import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

def player_stats():
    # Set up SQLAlchemy engine for PostgreSQL connection
    conn_str = os.getenv("DATABASE_URL")
    engine = create_engine(conn_str)

    league = "EPL"
    year = "2024"
    table_name = f'public."{year}_{league}_stats"'  # Explicitly target the `public` schema

    # Sample player data dictionary with correct types
    player_data = {
        'Player': 'Wilson Odobert',
        'Team': 'Tottenham',
        'Minutes': 167,            # Ensure integer type for Minutes
        'NpGI90': 0.0,             # Ensure float type for Goals + Assists per 90
        'xA90': 0.03,
        'NPxG90_xA90': 0.43,
        'xGChain90': 0.84,
        'xGBuildup90': 0.43
    }

    # Step 1: Create the table if it doesn’t exist
    with engine.begin() as conn:
        try:
            # Drop the table if it exists
            print(f"Attempting to drop table {table_name} if it exists.")
            conn.execute(text(f'DROP TABLE IF EXISTS {table_name}'))
            print(f"Table {table_name} dropped (if it existed).")

            # Create the table
            print(f"Attempting to create table {table_name}.")
            conn.execute(text(f'''
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    Player VARCHAR(255),
                    Team VARCHAR(255),
                    Minutes INT,
                    NpGI90 DECIMAL(10, 3),  -- Goals + Assists per 90
                    xA90 DECIMAL(10, 3),
                    NPxG90_xA90 DECIMAL(10, 3),
                    xGChain90 DECIMAL(10, 3),
                    xGBuildup90 DECIMAL(10, 3)
                )
            '''))
            print(f"Table {table_name} created successfully.")
        except SQLAlchemyError as e:
            print(f"Error creating table: {e}")

    # Step 2: Insert sample player data into the table
    def insert_player_data(data):
        """Insert player data into the PostgreSQL table."""
        with engine.connect() as conn:
            try:
                # Explicit transaction to ensure commit
                with conn.begin() as transaction:
                    sql = text(f'''INSERT INTO {table_name} 
                                   (Player, Team, Minutes, NpGI90, xA90, NPxG90_xA90, xGChain90, xGBuildup90) 
                                   VALUES (:Player, :Team, :Minutes, :NpGI90, :xA90, :NPxG90_xA90, :xGChain90, :xGBuildup90)''')
                    conn.execute(sql, data)
                    print("Sample player data inserted successfully.")
            except SQLAlchemyError as e:
                print("Error inserting data:", e)

    # Insert the test data
    insert_player_data(player_data)

    # Step 3: Verify insertion by querying the table
    with engine.connect() as conn:
        try:
            result = conn.execute(text(f'SELECT * FROM {table_name} LIMIT 1'))
            row = result.fetchone()
            if row:
                print("Inserted row:", row)
            else:
                print("No data found in the table.")
        except SQLAlchemyError as e:
            print("Error accessing inserted data:", e)

player_stats()
