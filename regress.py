import pandas as pd
import numpy as np
import os
import streamlit as st
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
import mysql.connector
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.graphics.gofplots import qqplot

# # Establish connection to MySQL
# conn = mysql.connector.connect(
#     host=os.getenv("DB_HOST"),
#     user=os.getenv("DB_USER"),
#     password=os.getenv("DB_PASSWORD"),
#     database=os.getenv("DB_NAME")
# )

# Vercel Setup
conn_str = os.getenv("DATABASE_URL")

# Create an SQLAlchemy engine
engine = create_engine(conn_str)

st.title('Goal Involvement OLS Model')

# Load the table using a SQL query
query = "SELECT * FROM 2024_EPL_stats"
df = pd.read_sql_query(query, con=engine)
threshold = df['Minutes'].max() * 0.6
df = df[df['Minutes'] >= threshold]

# Data preprocessing
df['xGChain_xGBuildup'] = df['xGChain90'] - df['xGBuildup90']
df['SP_Chain_Buildup'] = (df['NPxG90_xA90'] - df['xGChain_xGBuildup']) / df['NPxG90_xA90']
df['SP_Chain_Buildup_sq'] = df['SP_Chain_Buildup'] ** 2

df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna()

# Dependent variable (Y)
y = df['NpGI90']

# Independent variables (X)
X = df[['xGChain_xGBuildup', 'SP_Chain_Buildup','xA90']]

# Add constant to the independent variables
X = sm.add_constant(X)

# Fit the model
model = sm.OLS(y, X).fit()
st.write(model.summary())

st.divider()

# Plotting section
st.header('OLS Model Graphs')

# Fitted vs Actual Plot
# st.subheader('Fitted vs Actual Values')
fitted_values = model.fittedvalues
residuals = model.resid

plt.figure(figsize=(10, 6))
sns.scatterplot(x=fitted_values, y=y)
plt.xlabel('Fitted Values (Predicted NpGI90)')
plt.ylabel('Actual Values (NpGI90)')
plt.title('Fitted vs Actual Values')
with st.expander('Fitted vs Actual Values'):
    st.pyplot(plt)

# Residual Plot
# st.subheader('Residual Plot')
plt.figure(figsize=(10, 6))
sns.scatterplot(x=fitted_values, y=residuals)
plt.axhline(0, color='red', linestyle='--')
plt.xlabel('Fitted Values (Predicted NpGI90)')
plt.ylabel('Residuals')
plt.title('Residual Plot')
with st.expander('Residual Plot'):
    st.pyplot(plt)

# QQ Plot
# st.subheader('QQ Plot')
plt.figure(figsize=(10, 6))
qqplot(residuals, line='s')
plt.title('QQ Plot of Residuals')
with st.expander('QQ Plot of Residuals'):
    st.pyplot(plt)

st.divider()

# Input fields for user to enter new explanatory variables
st.header('Goal Involvement Calculator')
xgchain = st.number_input('Enter xGChain90:', min_value=0.0, step=0.01)
xgbuildup = st.number_input('Enter xGBuildup90:', min_value=0.0, step=0.01)
npxG90 = st.number_input('Enter npxG90:', min_value=0.0, step=0.01)
xA90 = st.number_input('Enter xA90:', min_value=0.0, step=0.01)
npxG90_xA90 = npxG90 + xA90
Sp_Chain = 0
if npxG90_xA90 != 0:
    Sp_Chain = (npxG90_xA90 - xgchain + xgbuildup)/npxG90_xA90
    


# Create a DataFrame for the input
input_data = pd.DataFrame({
    'const': [1],  # Adding constant for the intercept
    'xGChain_xGBuildup': [xgchain - xgbuildup],
    'SP_Chain_Buildup': [Sp_Chain],
    'xA90': [xA90]
})

# When the user inputs values, use the model to predict NpGI90
if st.button('Predict NpGI90'):
    predicted_npgi = model.predict(input_data)[0]  # Use the regression model for prediction
    st.success(f'The predicted NpGI90 is: {predicted_npgi:.2f}')


import pandas as pd
import streamlit as st
import statsmodels.api as sm
import mysql.connector

# MySQL connection setup
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="Ihavesevenas123",
    database="stats"
)

st.divider()
st.subheader('Player Ranking Based on Predicted Goal Involvements')


# Query the database to get player stats
query = "SELECT * FROM form_stats"
df = pd.read_sql_query(query, con=conn)
df = df.drop_duplicates(subset=['Player'], keep='first')
# Compute npxG90 (non-penalty expected goals per 90 Minutes)
df['npxG90'] = df['NPxG90_xA90'] - df['xA90']  # Derived as NPxG90 - xA90
df['xGChain_xGBuildup'] = df['xGChain90'] - df['xGBuildup90']
df['SP_Chain_Buildup'] = (df['NPxG90_xA90'] - df['xGChain_xGBuildup']) / df['NPxG90_xA90']

df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna()

# Prepare independent variables (X) for OLS model
X = df[['xGChain_xGBuildup', 'SP_Chain_Buildup', 'xA90']]

# Add constant term for the OLS model
X = sm.add_constant(X)

# Dependent variable (Y) is NpGI90 (assumed to be in the dataset)
y = df['NPxG90_xA90']  # NpGI90 can be predicted using xGChain, xGBuildup, xA

# Fit the OLS model
model = sm.OLS(y, X).fit()

# Use the model to predict NpGI90 for each player
df['NPGI Per 90'] = model.predict(X)

# Rank players based on predicted NpGI90
df['Rank'] = df['NPGI Per 90'].rank(ascending=False)

# Sort the players by rank
df_ranked = df.sort_values(by='Rank')

# Show only selected columns in a scrollable table
columns_to_display = ['Rank', 'Player', 'Team', 'NPGI Per 90', 'npxG90', 'xA90', 'xGChain90', 'xGBuildup90']
st.dataframe(df_ranked[columns_to_display], height=600)  # Set a fixed height for scrollability
