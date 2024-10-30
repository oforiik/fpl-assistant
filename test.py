# import os
# from sqlalchemy import create_engine, text
# from sqlalchemy.exc import SQLAlchemyError
# import pandas as pd

# def player_stats():
#     # Set up SQLAlchemy engine for PostgreSQL connection
#     conn_str = os.getenv("DATABASE_URL")
#     engine = create_engine(conn_str)

#     league = "EPL"
#     year = "2024"
#     table_name = f'public."{year}_{league}_stats"'  # Explicitly target the `public` schema

#     # Sample player data dictionary with correct types
#     player_data = {
#         'Player': 'Wilson Odobert',
#         'Team': 'Tottenham',
#         'Minutes': 167,
#         'NpGI90': 0.0,
#         'xA90': 0.03,
#         'NPxG90_xA90': 0.43,
#         'xGChain90': 0.84,
#         'xGBuildup90': 0.43
#     }

#     # Step 1: Create the table if it doesn’t exist
#     with engine.begin() as conn:
#         try:
#             # Drop the table if it exists
#             print(f"Attempting to drop table {table_name} if it exists.")
#             conn.execute(text(f'DROP TABLE IF EXISTS {table_name}'))
#             print(f"Table {table_name} dropped (if it existed).")

#             # Create the table
#             print(f"Attempting to create table {table_name}.")
#             conn.execute(text(f'''
#                 CREATE TABLE {table_name} (
#                     id SERIAL PRIMARY KEY,
#                     Player VARCHAR(255),
#                     Team VARCHAR(255),
#                     Minutes INT,
#                     NpGI90 DECIMAL(10, 3),
#                     xA90 DECIMAL(10, 3),
#                     NPxG90_xA90 DECIMAL(10, 3),
#                     xGChain90 DECIMAL(10, 3),
#                     xGBuildup90 DECIMAL(10, 3)
#                 )
#             '''))
#             print(f"Table {table_name} created successfully.")
#         except SQLAlchemyError as e:
#             print(f"Error creating table: {e}")

#     # Step 2: Insert sample player data into the table
#     def insert_player_data(data):
#         """Insert player data into the PostgreSQL table."""
#         with engine.connect() as conn:
#             try:
#                 with conn.begin() as transaction:
#                     sql = text(f'''INSERT INTO {table_name} 
#                                    (Player, Team, Minutes, NpGI90, xA90, NPxG90_xA90, xGChain90, xGBuildup90) 
#                                    VALUES (:Player, :Team, :Minutes, :NpGI90, :xA90, :NPxG90_xA90, :xGChain90, :xGBuildup90)''')
#                     conn.execute(sql, data)
#                     print("Sample player data inserted successfully.")
#             except SQLAlchemyError as e:
#                 print("Error inserting data:", e)

#     # Insert the test data
#     insert_player_data(player_data)

#     # Step 3: Print all rows from the table
#     # with engine.connect() as conn:
#     #     try:
#     #         result = conn.execute(text(f'SELECT * FROM {table_name}'))
#     #         rows = result.fetchall()
#     #         if rows:
#     #             print("Table contents:")
#     #             for row in rows:
#     #                 print(row)
#     #         else:
#     #             print("The table is empty.")
#     #     except SQLAlchemyError as e:
#     #         print("Error accessing table data:", e)
            
            
#     with engine.connect() as conn:
#         try:
#             query = text(f'SELECT * FROM {table_name}')
#             df = pd.read_sql_query(query, conn)
#             print("Data loaded into DataFrame successfully.")
#             return df  # Returns the DataFrame for further use
#         except SQLAlchemyError as e:
#             print("Error accessing table data:", e)
#             return None


# df = player_stats()
# if df is not None:
#     print(df)

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import os
import streamlit as st

def player_stats():
    # Set up SQLAlchemy engine for PostgreSQL connection
    conn_str = os.getenv("DATABASE_URL")
    engine = create_engine(conn_str)

    league = "EPL"
    year = "2024"
    table_name = f'public."{year}_{league}_stats"'  # Explicitly target the `public` schema

    # Step 3: Load all rows from the table into a DataFrame
    with engine.begin() as conn:
        try:
            query = text(f'SELECT * FROM {table_name}')
            df = pd.read_sql_query(query, conn)
            print("Data loaded into DataFrame successfully.")
            return df  # Returns the DataFrame for further use
        except SQLAlchemyError as e:
            print("Error accessing table data:", e)
            return None

# Call the function
df = player_stats()
if df is not None:
    print(df)
